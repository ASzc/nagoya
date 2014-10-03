import logging
import os

import nagoya.toji
import nagoya.temp
import nagoya.docker.container

logger = logging.getLogger("nagoya.build")

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

    def commit(self, container):
        self.to_commit.append(container)

    def persist(self, container):
        self.to_persist.append(container)

    def volume_include(self, container, src_path, container_dir, executable=False):
        if not container in self.temp_vol_dirs:
            self.temp_vol_dirs[container] = dict()
        if not container_dir in self.temp_vol_dirs[container]:
            vd = nagoya.temp.TempDirectory()
            container.volumes.append(nagoya.docker.container.VolumeLink(vd, container_dir))
            # TODO ^^^ host volumes working on Fedora depends on Docker#5910
            self.temp_vol_dirs[container][container_dir] = vd

        basename = os.path.basename(src_path)
        self.temp_vol_dirs[container][container_dir].include(src_path, basename, executable)

        container_path = os.path.join(container_dir, basename)
        return container_path

    def _run(self):
        # TODO start system, wait until root is done, stop system
        pass

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
