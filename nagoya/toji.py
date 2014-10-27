#
# Copyright (C) 2014 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import logging
import sys
import concurrent.futures as futures
import traceback

import docker
import toposort

import nagoya.dockerext.container

logger = logging.getLogger("nagoya.toji")

class ExecutionError(Exception):
    def __init__(self, exceptions):
        self.exceptions = exceptions
        tracebacks = "\n==========\n".join(
            ["".join(traceback.format_exception(*e._exc_info))
             for e in exceptions]
        )
        message = "Exception(s) from command execution:\n{tracebacks}".format(**locals())
        super(ExecutionError, self).__init__(message)

# Modified futures run that passes the complete exc_info as an attribute of the exception
# Have to use this to work around Python 2's limited exception handling to extract a full traceback
def cft_run(self):
    if not self.future.set_running_or_notify_cancel():
        return
    try:
        result = self.fn(*self.args, **self.kwargs)
    except BaseException:
        e = sys.exc_info()[1]
        e._exc_info = sys.exc_info()
        self.future.set_exception(e)
    else:
        self.future.set_result(result)

class Toji(object):
    """
    Manages a system of containers
    """

    @staticmethod
    def find_sync_groups(containers):
        deps = dict()
        name2container = dict()
        for container in containers:
            name2container[container.name] = container
            deps[container.name] = container.dependency_names()

        synch_groups = []
        for synch_group_names in toposort.toposort(deps):
            synch_group = set()
            for container_name in synch_group_names:
                synch_group.add(name2container[container_name])
            synch_groups.append(synch_group)

        return synch_groups

    def __init__(self, containers=None, client=None):
        self.client = client

        if containers is None:
            self.containers = []
            self.container_sync_groups = None
        else:
            self.containers = containers
            # Since containers were given, calculate now to throw any errors here
            self.container_sync_groups = self.find_sync_groups(containers)

    @classmethod
    def from_dict(cls, d, **kwargs):
        containers = [nagoya.dockerext.container.Container.from_dict(name, sub) for name,sub in d.items()]
        instance = cls(containers=containers, **kwargs)
        for container in instance.containers:
            container.client = instance.client
        return instance

    @property
    def client(self):
        if self._client is None:
            self.client = docker.Client(timeout=10)
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    @property
    def container_sync_groups(self):
        if not self._sync_groups_calculated:
            self.container_sync_groups = self.find_sync_groups(self.containers)
        return self._container_sync_groups

    @container_sync_groups.setter
    def container_sync_groups(self, value):
        self._container_sync_groups = value
        self._sync_groups_calculated = value is not None

    def _container(self, container_type, *args, **kwargs):
        c = container_type(*args, **kwargs)
        c.client = self.client
        self._sync_groups_calculated = False
        self.containers.append(c)
        return c

    def container(self, *args, **kwargs):
        return self._container(nagoya.dockerext.container.Container, *args, **kwargs)

    # Run against containers in order of dependency groups
    def containers_exec(self, func, group_ordering=lambda x: x):
        # Modify run method to provide exc_info consistently for Python 2 and 3
        if not futures.thread._WorkItem.run.__code__.co_code == cft_run.__code__.co_code:
            futures.thread._WorkItem.run = cft_run

        mw = max(map(len, self.container_sync_groups))
        with futures.ThreadPoolExecutor(max_workers=mw) as pool:
            for container_group in group_ordering(self.container_sync_groups):
                fs = [pool.submit(func, c) for c in container_group]
                exceptions = []
                for future in futures.as_completed(fs):
                    ex = future.exception()
                    if ex is not None:
                        exceptions.append(ex)
                if not exceptions == []:
                    raise ExecutionError(exceptions)
                # TODO include logs from any exited, errored, containers?

    def init_containers(self):
        self.containers_exec(nagoya.dockerext.container.Container.init)

    def start_containers(self):
        self.containers_exec(nagoya.dockerext.container.Container.start)

    def stop_containers(self):
        self.containers_exec(nagoya.dockerext.container.Container.stop, group_ordering=reversed)

    def remove_containers(self):
        self.containers_exec(nagoya.dockerext.container.Container.remove, group_ordering=reversed)

class TempToji(Toji):
    """
    Allows the use of "with ... as" blocks for a temporary Toji instance
    """

    @staticmethod
    def cleanup_nothing(toji):
        pass

    @staticmethod
    def cleanup_stop(toji):
        toji.stop_containers()

    @staticmethod
    def cleanup_remove(toji):
        toji.remove_containers()

    def __init__(self, containers=None, client=None, cleanup=None):
        self.cleanup = cleanup
        super(TempToji, self).__init__(containers=containers, client=client)

    @property
    def cleanup(self):
        return self._cleanup

    @cleanup.setter
    def cleanup(self, value):
        if value is None:
            self._cleanup = self.cleanup_nothing
        elif isinstance(value, str):
            if value in ["nothing", "stop", "remove"]:
                self._cleanup = getattr(self, "cleanup_" + value)
            else:
                ValueError("Cleanup function for str {value} is not available".format(**locals()))
        else:
            self._cleanup = value

    def container(self, *args, **kwargs):
        return self._container(nagoya.dockerext.container.TempContainer, *args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            logger.debug("Executing cleanup function")
        else:
            logger.error("Exception raised within context, cleaning up before raising")
        self.cleanup(self)
