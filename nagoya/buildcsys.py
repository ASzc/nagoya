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
import os
import collections

import nagoya.toji
import nagoya.temp
import nagoya.dockerext.container

logger = logging.getLogger("nagoya.build")

ContrainerAndDest = collections.namedtuple("ContainerAndDest", ["container", "dest_image"])

class BuildContainerSystem(nagoya.toji.TempToji):
    """
    Succinctly construct a system of containers and produce images from them in
    multiple ways.
    """

    def __init__(self, root_image, containers=None, client=None, cleanup=None, quiet=False):
        super(BuildContainerSystem, self).__init__(containers=containers, client=client, cleanup=cleanup)
        self.root = self._root(root_image)
        self.to_commit = []
        self.to_persist = []
        self.temp_vol_dirs = dict()
        self.quiet = quiet

    def _root(self, image_name):
        return self.container(image=image_name, detach=False)

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
            container.add_volume(vd.name, container_dir)
            # TODO ^^^ host volumes working on Fedora depends on Docker#5910
            self.temp_vol_dirs[container][container_dir] = vd

        dest_basename = os.path.basename(container_path)
        self.temp_vol_dirs[container][container_dir].include(src_path, dest_basename, executable)

    def _run(self):
        logger.info("Starting temporary container system")
        self.init_containers()

        logger.info("Waiting for the root container to finish")
        self.root.wait(error_ok=False)

        logger.info("Stopping temporary container system")
        self.stop_containers()

    def _build(self):
        for container, image in self.to_commit:
            logger.info("Commiting {container} container to image {image}".format(**locals()))
            self.client.commit(container, image)

        for container, image in self.to_persist:
            logger.info("Persisting {container} container to image {image}".format(**locals()))

            with nagoya.temp.TempDirectory() as tdir:
                source_volumes = self.client.inspect_container(container=container.name)["Volumes"]
                # busybox's tar won't accept file/dir arguments with a starting slash
                volume_paths = [v.lstrip("/") for v in source_volumes.keys()]

                logger.debug("Extracting files from {container} volumes".format(**locals()))
                container_volume_dir = os.path.join("/", container.random_name())
                container_tar_path = os.path.join(container_volume_dir, "extract.tar")
                host_tar_path = os.path.join(tdir.name, "extract.tar")

                extract_container = nagoya.dockerext.container.TempContainer("busybox")
                extract_container.client = self.client
                extract_container.add_volume(tdir.name, container_volume_dir)
                # TODO ^^^ host volumes working on Fedora depends on Docker#5910
                extract_container.add_volume_from(container.name, "ro")
                extract_container.entrypoint = ["tar", "-cf", container_tar_path] + volume_paths
                extract_container.init()
                extract_container.wait(error_ok=False)

                logger.info("Building image {image} with volume data from {container} container".format(**locals()))
                with nagoya.dockerext.build.BuildContext(image, container.image, self.client, self.quiet) as context:
                    context.include(host_tar_path, "/")

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
        except Exception as e:
            logger.error("Exception raised during build, running cleanup before raising")
            raise
        finally:
            super(BuildContainerSystem, self).__exit__(exc, value, tb)
