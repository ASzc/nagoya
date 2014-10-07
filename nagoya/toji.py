#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import logging
import sys
try:
    import concurrent.futures as futures
except:
    # Fall back to local download
    import futures

import docker
import toposort

import nagoya.docker.container

logger = logging.getLogger("nagoya.toji")

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
        containers = [nagoya.docker.container.Container.from_dict(name, sub) for name,sub in d.items()]
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
        return self._container(nagoya.docker.container.Container, *args, **kwargs)

    # Run against containers in order of dependency groups
    def containers_exec(self, func, group_ordering=lambda x: x):
        # Modify run method on Python 2
        # concurrent.futures.thread only imports sys in Python 2
        if (hasattr(futures.thread, "sys")
            and not futures.thread._WorkItem.run.__code__.co_code == cft_run.__code__.co_code):
            futures.thread._WorkItem.run = cft_run

        mw = max(map(len, self.container_sync_groups))
        with futures.ThreadPoolExecutor(max_workers=mw) as pool:
            for container_group in group_ordering(self.container_sync_groups):
                fs = [pool.submit(func, c) for c in container_group]
                for future in futures.as_completed(fs):
                    ex = future.exception()
                    if ex is not None:
                        # Work around Python 2 truncating the traceback upon rethrowing
                        # _exc_info is added to exception by modified futures run method
                        if hasattr(ex, "_exc_info"):
                            ei = ex._exc_info
                            # Work around SyntaxError on Python 3
                            exec("raise ei[0], ei[1], ei[2]")
                        raise ex

    def init_containers(self):
        self.containers_exec(nagoya.docker.container.Container.init)

    def start_containers(self):
        self.containers_exec(nagoya.docker.container.Container.start)

    def stop_containers(self):
        self.containers_exec(nagoya.docker.container.Container.stop, group_ordering=reversed)

    def remove_containers(self):
        self.containers_exec(nagoya.docker.container.Container.remove, group_ordering=reversed)

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
        if cleanup is None:
            self.cleanup = self.cleanup_nothing
        elif isinstance(cleanup, str):
            if cleanup in ["nothing", "stop", "remove"]:
                self.cleanup = getattr(self, "cleanup_" + cleanup)
            else:
                ValueError("Cleanup function for str {cleanup} is not available".format(**locals()))
        else:
            self.cleanup = cleanup

        super(TempToji, self).__init__(containers=containers, client=client)

    def container(self, *args, **kwargs):
        return self._container(nagoya.docker.container.TempContainer, *args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup(self)
