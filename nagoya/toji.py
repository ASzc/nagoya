#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import logging
import sys
try:
    import concurrent.futures
except:
    import futures
import docker

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

    @staticmethod
    def cleanup_nothing(toji):
        pass

    @staticmethod
    def cleanup_stop(toji):
        toji.stop_containers()

    @staticmethod
    def cleanup_remove(toji):
        toji.remove_containers()

    def __init__(self, containers, cleanup=None):
        self.containers = containers
        self.container_sync_groups = self.find_sync_groups(containers)
        self.cleanup = cleanup if cleanup is not None else self.cleanup_nothing

    @classmethod
    def from_dict(cls, d, **kwargs):
        containers = [Container.from_dict(name, sub) for name,sub in d.items()]
        instance = cls(containers=containers, **kwargs)
        for container in instance.containers:
            container.client = instance.client
        return instance

    @classmethod
    def from_config(cls, paths, **kwargs):
        config_dict = nagoya.cfg.read_config(paths, default_config_paths, boolean_config_options)
        return cls.from_dict(config_dict, **kwargs)

    @property
    def client(self):
        if not hasattr(self, "_client"):
            self._client = docker.Client(timeout=10)
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    def _container(self, container_type, *args, **kwargs):
        c = container_type(*args, **kwargs)
        c.client = self.client
        return c

    def container(self, *args, **kwargs):
        return _container(Container, *args, **kwargs)

    def temp_container(self, *args, **kwargs):
        return _container(TempContainer, *args, **kwargs)

    # Run against containers in order of dependency groups
    def containers_exec(self, func, group_ordering=lambda x: x):
        # Modify run method on Python 2
        # concurrent.futures.thread only imports sys in Python 2
        if (hasattr(concurrent.futures.thread, "sys")
            and not concurrent.futures.thread._WorkItem.run.__code__.co_code == cft_run.__code__.co_code):
            concurrent.futures.thread._WorkItem.run = cft_run

        mw = max(map(len, self.container_sync_groups))
        with concurrent.futures.ThreadPoolExecutor(max_workers=mw) as pool:
            for container_group in group_ordering(self.container_sync_groups):
                fs = [pool.submit(func, c) for c in container_group]
                for future in concurrent.futures.as_completed(fs):
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
        self.containers_exec(Container.init)

    def start_containers(self):
        self.containers_exec(Container.start)

    def stop_containers(self):
        self.containers_exec(Container.stop, group_ordering=reversed)

    def remove_containers(self):
        self.containers_exec(Container.remove, group_ordering=reversed)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup(self)
        return False

#
# Main
#

# TODO might have to put this in a seperate file outside of the module if running the module doesn't work properly

default_config_paths = ["containers.cfg"]
boolean_config_options = ["multiple", "detach", "run_once"]

def _config_dict(args):
    return nagoya.cfg.read_config(args.config, default_config_paths, boolean_config_options)

def sc_init(args):
    toji = Toji.from_dict(_config_dict(args))
    toji.init_containers()

def sc_start(args):
    toji = Toji.from_dict(_config_dict(args))
    toji.start_containers()

def sc_stop(args):
    toji = Toji.from_dict(_config_dict(args))
    toji.stop_containers()

def sc_remove(args):
    toji = Toji.from_dict(_config_dict(args))
    toji.remove_containers()

if __name__ == "__main__":
    parser = nagoya.args.create_default_argument_parser(description="Manage Koji Docker container systems")
    nagoya.args.add_subcommand_subparsers(parser)
    nagoya.args.attempt_autocomplete(parser)
    args = parser.parse_args()

    nagoya.log.setup_logger(args.quiet, args.verbose)

    nagoya.args.run_subcommand_func(args, parser)
