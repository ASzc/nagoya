import logging
import os
import collections

import nagoya.toji
import nagoya.temp
import nagoya.docker.container

logger = logging.getLogger("nagoya.build")

ContrainerAndDest = collections.namedtuple("ContainerAndDest", ["container", "dest_image"])

class BuildContainerSystem(nagoya.toji.TempToji):
    """
    Succinctly construct a system of containers and produce images from them in
    multiple ways.
    """

    def __init__(self, root_image, containers=None, client=None, cleanup=None):
        super(BuildContainerSystem, self).__init__(containers=containers, client=client, cleanup=cleanup)
        self.root = self._root(root_image)
        self.to_commit = []
        self.to_persist = []
        self.temp_vol_dirs = dict()

    def _root(self, image_name):
        root = self.container(image=image_name, detach=False)
        self.containers.append(root)
        return root

    def commit(self, container, dest_image):
        self.to_commit.append(ContrainerAndDest(container, dest_image))

    def persist(self, container, dest_image):
        self.to_persist.append(ContrainerAndDest(container, dest_image))

    def volume_include(self, container, src_path, container_path, executable=False):
        container_dir = os.path.dirname(container_path)

        if not container in self.temp_vol_dirs:
            self.temp_vol_dirs[container] = dict()
        if not container_dir in self.temp_vol_dirs[container]:
            vd = nagoya.temp.TempDirectory()
            container.volumes.append(nagoya.docker.container.VolumeLink(vd, container_dir))
            # TODO ^^^ host volumes working on Fedora depends on Docker#5910
            self.temp_vol_dirs[container][container_dir] = vd

        dest_basename = os.path.basename(container_path)
        self.temp_vol_dirs[container][container_dir].include(src_path, dest_basename, executable)

    def _run(self):
        # TODO start system, wait until root is done, stop system
        logger.info("Starting temporary container system")
        self.init_containers()

        logger.info("Waiting for the root container to finish")
        self.root.wait(error_ok=False)

        logger.info("Stopping temporary container system")
        self.stop_containers()

    def _build(self):
        # TODO process commit containers

        # TODO process persist containers

        pass

    def __exit__(self, exc, value, tb):
        try:
            try:
                if exc is None:
                    self._run()
            finally:
                for temp_dirs in self.temp_vol_dirs.values():
                    for temp_dir in temp_dirs.values():
                        temp_dir.cleanup()

            if exc is None:
                self._build()
        finally:
            super(BuildContainerSystem, self).__exit__(exc, value, tb)
