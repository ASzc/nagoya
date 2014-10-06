import importlib
import logging
import uuid

import docker

logger = logging.getLogger("nagoya.docker")

class ContainerExitError(Exception):
    def __init__(self, code, logs):
        self.code = code
        self.logs = logs
        message = "Error code {0}, Logs:\n{1}".format(code, logs)
        super(ContainerExitError, self).__init__(message)

class VolumeLink(object):
    def __init__(self, host_path, container_path):
        self.host_path = host_path
        self.container_path = container_path

    @classmethod
    def from_text(cls, text):
        s = text.split(":")
        if len(s) == 1:
            h = None
            c, = s
        else:
            h, c = s
        return cls(h, c)

    def api_formatted(self):
        if self.host_path is None:
            self.container_path
        else:
            return self.host_path + ":" + self.container_path

    def __str__(self):
        return self.api_formatted()

class VolumeFromLink(object):
    def __init__(self, container_name, mode):
        self.container_name = container_name
        self.mode = mode

    @classmethod
    def from_text(cls, text):
        c, m = text.split(":")
        return cls(c, m)

    def api_formatted(self):
        return self.container_name + ":" + self.mode

    def __str__(self):
        return self.api_formatted()

class NetworkLink(object):
    def __init__(self, container_name, alias):
        self.container_name = container_name
        self.alias = alias

    @classmethod
    def from_text(cls, text):
        c, a = text.split(":")
        return cls(c, a)

    def api_formatted(self):
        return (self.container_name, self.alias)

    def __str__(self):
        return ":".join(self.api_formatted())

class ProvidedCallbacks(object):
    @staticmethod
    def show_network(container):
        container_info = container.client.inspect_container(container=container.name)
        try:
            net = container_info["NetworkSettings"]
            a = net["IPAddress"]
            p = ", ".join(net["Ports"].keys())
            logger.info("Container {0} at Address: {1} Ports: {2}".format(container, a, p))
        except KeyError as e:
            logger.error("Could not read network information for container {0}: {1}".format(container, e))

class Callspec(object):
    valid_events = {"init", "create", "start", "stop", "remove"}
    valid_event_parts = {"pre", "post"}

    def __init__(self, event_part, event, callback_func):
        if not event_part in self.valid_event_parts:
            ValueError("Event part '{0}' is not valid".format(event_part))
        if not event in self.valid_events:
            ValueError("Event '{0}' is not valid".format(event))

        self.event_part = event_part
        self.event = event
        self.callback_func = callback_func

    @classmethod
    def from_text(cls, text):
        event_spec, cb_coord = text.split(":")
        event_part, event = event_spec.split("_")

        # Qualified coordinate
        if "." in cb_coord:
            if cb_coord.startswith("."):
                raise ValueError("Qualified callback coordinate '{0}' cannot be relative".format(cb_coord))
            else:
                module, cb_name = cb_coord.rsplit(".", 1)
                cb_module = importlib.import_module(module)
                callback_func = getattr(cb_module, cb_name)
        # Unqualified => Provided
        else:
            if cb_coord.startswith("_"):
                raise ValueError("Unqualified callback coordinate '{0}' cannot start with an underscore".format(cb_coord))
            else:
                callback_func = getattr(ProvidedCallbacks, cb_coord)

        return cls(event_part, event, callback_func)

class Container(object):
    @staticmethod
    def random_name():
        return str(uuid.uuid4())

    def __init__(self, image, name=None, detach=True, volumes=None,
                 volumes_from=None, links=None, multiple=False, run_once=False,
                 entrypoint=None, working_dir=None, callbacks=None):

        # For mutable defaults
        def mdef(candidate, default):
            return candidate if candidate is not None else default

        self.name = mdef(name, self.random_name())
        self.image = image
        self.detach = detach
        self.volumes = mdef(volumes, [])
        self.volumes_from = mdef(volumes_from, [])
        self.links = mdef(links, [])
        self.multiple = multiple
        self.run_once = run_once
        self.entrypoint = entrypoint
        self.working_dir = working_dir
        self.callbacks = mdef(callbacks, [])

    @classmethod
    def from_dict(cls, name, d):
        params = dict()

        params["name"] = name
        for required in ["image"]:
            params[required] = d[required]

        for optional in ["multiple", "detach", "volumes_from", "links",
                         "run_once", "volumes", "entrypoint", "working_dir",
                         "callbacks"]:
            if optional in d:
                value = d[optional]

                if optional in ["volumes", "volumes_from", "links", "callbacks"]:
                    lines = map(str.strip, value.split("\n"))
                    types = {"volumes" : VolumeLink,
                              "volumes_from" : VolumeFromLink,
                              "links" : NetworkLink,
                              "callbacks" : Callspec}
                    t = types[optional]
                    params[optional] = [t.from_text(l) for l in lines]
                else:
                    params[optional] = value

        return cls(**params)

    @property
    def client(self):
        if not hasattr(self, "_client"):
            self._client = docker.Client(timeout=10)
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    def _process_callbacks(self, event_part, event):
        for callspec in self.callbacks:
            if callspec.event_part == event_part and callspec.event == event:
                callspec.callback_func(self)

    def init(self):
        self._process_callbacks("pre", "init")
        logger.debug("Initializing container {0}".format(self))
        self.create()
        self.start()
        self._process_callbacks("post", "init")

    def create(self, exists_ok=True):
        try:
            self._process_callbacks("pre", "create")
            logger.debug("Attempting to create container {0}".format(self))
            self.client.create_container(name=self.name,
                                         image=self.image,
                                         detach=self.detach, # Doesn't seem to do anything
                                         volumes=self.volumes_api_formatted(),
                                         entrypoint=self.entrypoint,
                                         working_dir=self.working_dir,
                                         command=[""])
            logger.info("Created container {0}".format(self))
            self._process_callbacks("post", "create")
        except docker.errors.APIError as e:
            if exists_ok and e.response.status_code == 409:
                logger.debug("Container {0} already exists".format(self))
            else:
                raise

    def start(self):
        def start():
            self._process_callbacks("pre", "start")
            logger.debug("Attempting to start container {0}".format(self))
            self.client.start(container=self.name,
                              links=self.links_api_formatted(),
                              volumes_from=self.volumes_from_api_formatted())
            if not self.detach:
                logger.info("Waiting for container {0} to finish".format(self))
                status_code = self.wait(error_ok=False)
                logger.info("Container {0} exited ok".format(self))
            else:
                logger.info("Started container {0}".format(self))
            self._process_callbacks("post", "start")

        if self.run_once:
            container_info = self.client.inspect_container(container=self.name)
            if container_info["State"]["StartedAt"] == "0001-01-01T00:00:00Z":
                start()
            else:
                logger.debug("Container {0} is configured to run only once and has been started before".format(self))
        else:
            start()

    def stop(self, not_exists_ok=True):
        logger.debug("Attempting to stop container {0}".format(self))

        try:
            container_info = self.client.inspect_container(container=self.name)
            pid = container_info["State"]["Pid"]
            if pid == 0:
                logger.debug("Container {0} is not running".format(self))
            else:
                self._process_callbacks("pre", "stop")
                self.client.kill(container=self.name, signal=15)
                try:
                    self.wait(timeout=20, error_ok=True)
                    logger.info("Stopped container {0}".format(self))
                except requests.exceptions.Timeout:
                    self.client.kill(container=self.name, signal=9)
                    try:
                        self.wait(timeout=20, error_ok=True)
                        logger.info("Killed container {0}".format(self))
                        self._process_callbacks("post", "stop")
                    except requests.exceptions.Timeout as e:
                        logger.error("Unable to kill container {0}: {1}".format(self, e))
        except docker.errors.APIError as e:
            if not_exists_ok and e.response.status_code == 404:
                logger.debug("Container {0} does not exist".format(self))
            else:
                raise

    def remove(self, not_exists_ok=True):
        try:
            self._process_callbacks("pre", "remove")
            logger.debug("Attempting to remove container {0}".format(self))
            self.client.remove_container(self.name, force=True)
            logger.info("Removed container {0}".format(self))
            self._process_callbacks("post", "remove")
        except docker.errors.APIError as e:
            if not_exists_ok and e.response.status_code == 404:
                logger.debug("Container {0} doesn't exist".format(self))
            else:
                raise

    def wait(self, timeout=None, error_ok=False):
        url = self.client._url("/containers/{0}/wait".format(self.name))
        res = self.client._post(url, timeout=timeout)
        self.client._raise_for_status(res)
        d = res.json()
        status = d["StatusCode"] if "StatusCode" in d else -1
        if error_ok or status == 0:
            return status
        else:
            raise ContainerExitError(status, self.client.logs(self.name))

    def dependency_names(self):
        deps = set()

        for link in self.links:
            deps.add(link.container_name)

        for vf in self.volumes_from:
            deps.add(vf.container_name)

        return deps

    def volumes_api_formatted(self):
        return [v.api_formatted() for v in self.volumes]

    def volumes_from_api_formatted(self):
        return [v.api_formatted() for v in self.volumes_from]

    def links_api_formatted(self):
        return [l.api_formatted() for l in self.links]

    def add_volume(self, *args, **kwargs):
        link = VolumeLink(*args, **kwargs)
        self.volumes.append(link)
        return link

    def add_volume_from(self, *args, **kwargs):
        link = VolumeFromLink(*args, **kwargs)
        self.volumes_from.append(link)
        return link

    def add_link(self, *args, **kwargs):
        link = NetworkLink(*args, **kwargs)
        self.links.append(link)
        return link

    def __str__(self):
        return self.name

class TempContainer(Container):
    def __init__(self, image, name=None, **kwargs):
        image_name = image.split(":")[0]
        if name is None:
            name = image_name + "." + self.random_name()[:8]
        super(TempContainer, self).__init__(image, name=name, **kwargs)
