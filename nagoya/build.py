#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import logging
import sys
import os
import stat
import shutil
import tempfile
import re
import collections
import uuid

import docker

import nagoya.docker.build

logger = logging.getLogger("nagoya.build")

#
# Exceptions
#

# TODO remove / refactor these?

class BuildException(Exception):
    pass

class ContainerExitError(BuildException):
    pass

class InvalidFormat(BuildException):
    pass

#
# Helpers
#

def uuid4():
    return str(uuid.uuid4())

def line_split(string):
    return map(str.strip, string.split("\n"))

def optional_plural(cfg, key):
    if key in cfg:
        logger.debug("Optional config key {key} exists".format(**locals()))
        for elem in line_split(cfg[key]):
            yield elem
    else:
        logger.debug("Optional config key {key} does not exist".format(**locals()))

# This would inherit from tempfile.TemporaryDirectory, but Python 2 doesn't have it
class TempResourceDirectory():
    """
    Provides a temporary directory that can be used for:
        - A docker build context
        - A host directory mounted as a volume in a container
    """

    def __init__(self, suffix="", prefix=tempfile.template, dir=None, image_root="/tmp"):
        self._closed = False
        self.name = None
        self.name = tempfile.mkdtemp(suffix, prefix, dir)

        self.basenames_copied = set()
        self.image_root = image_root

    def __repr__(self):
        return "<{0} {1!r}>".format(self.__class__.__name__, self.name)

    def __enter__(self):
        return self

    def cleanup(self):
        if self.name is not None and not self._closed:
            shutil.rmtree(self.name)
            self._closed = True

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def include(self, source_path, dockerfile=None, executable=False):
        basename = os.path.basename(source_path)
        if basename in self.basenames_copied:
            raise BuildException("Resource collision for basename {basename}".format(**locals()))
        self.basenames_copied.add(basename)

        temp_path = os.path.join(self.name, basename)

        if os.path.isfile(source_path):
            logger.debug("Resource {basename} is a file".format(**locals()))
            shutil.copyfile(source_path, temp_path)
            if executable:
                logger.debug("Setting resource {basename} executable".format(**locals()))
                # equiv. of chmod +x
                mode = os.stat(temp_path).st_mode
                os.chmod(temp_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            else:
                logger.debug("Resource {basename} is not executable".format(**locals()))
        elif os.path.isdir(source_path):
            logger.debug("Resource {basename} is a directory".format(**locals()))
            shutil.copytree(source_path, temp_path)
        else:
            raise BuildException("Resource {source_path} is not file or directory".format(**locals()))

        image_path = os.path.join(self.image_root, basename)

        if dockerfile is not None:
            logger.debug("Appending ADD instruction to dockerfile for {source_path}".format(**locals()))
            dockerfile.write("ADD ./")
            dockerfile.write(basename)
            dockerfile.write(" ")
            dockerfile.write(image_path)
            dockerfile.write("\n")

        logger.debug("Included resource {source_path} for use at {image_path}".format(**locals()))

        return image_path

#
# Container system image build
#

container_system_option_names = {"volumes_from", "links", "commit"}

volume_spec_pattern = re.compile(r'^(?P<image>[^ ]+) then (discard$|persist to (?P<persistimage>[^: ]+)$)')
link_spec_pattern = re.compile(r'^(?P<image>[^ ]+) alias (?P<alias>[^ ]+) then (discard$|commit to (?P<commitimage>[^: ]+)$)')

ContainerWithDest = collections.namedtuple("ContainerWithDest", ["container", "destimage"])

def build_container_system(image_name, image_config, client, quiet):
    logger.info("Creating container system for {image_name}".format(**locals()))
    containers = []
    # Docker volumes don't work with the docker commit operation
    commit_containers = []
    # Only volume containers can be "persisted", as it is a workaround to the docker volume limitations
    persist_containers = []

    with TempResourceDirectory(image_root=os.path.join("/", uuid4()[:8])) as vol_host_dir:
        root = nagoya.toji.TempContainer(image=image_config["from"], detach=False)
        containers.append(root)
        if "commit" in image_config and image_config["commit"]:
            logger.debug("Root container {root} will be committed".format(**locals()))
            commit_containers.append(root)
        else:
            logger.debug("Root container {root} will be discarded".format(**locals()))

        # Container-time override of image's entrypoint
        if "entrypoint" in image_config:
            path = os.path.join(image_name, image_config["entrypoint"])
            root.entrypoint = vol_host_dir.include(path, executable=True)

        for lib_path in optional_plural(image_config, "libs"):
            vol_host_dir.include(lib_path)

        # Container-time override of image's working dir
        root.working_dir = vol_host_dir.image_root
        # Container-time definition of container volume
        root.volumes.append(nagoya.toji.VolumeLink(vol_host_dir.name, vol_host_dir.image_root))
        # TODO ^^^ does not work because selinux does not allow container processes access to anything outside their own data. Fix is blocked pending a release with this PR in it: https://github.com/docker/docker/pull/5910

        for volume_spec in optional_plural(image_config, "volumes_from"):
            match = volume_spec_pattern.match(volume_spec)
            if match:
                spec = match.groupdict()
                container = nagoya.toji.TempContainer(image=spec["image"], detach=False)
                logger.debug("Root container will have volumes from container {container}".format(**locals()))
                root.volumes_from.append(nagoya.toji.VolumeFromLink(container.name, "rw"))
                containers.append(container)
                if "persistimage" in spec:
                    logger.debug("Container {container} will be persisted".format(**locals()))
                    persist_containers.append(ContainerWithDest(container, spec["persistimage"]))
            else:
                raise InvalidFormat("Invalid volume from specification '{volume_spec}' for image {image_name}".format(**locals()))

        for link_spec in optional_plural(image_config, "links"):
            match = link_spec_pattern.match(link_spec)
            if match:
                spec = match.groupdict()
                container = nagoya.toji.TempContainer(image=spec["image"], detach=True)
                logger.debug("Root container will be linked to container {container}".format(**locals()))
                root.links.append(toji.NetworkLink(container.name, spec["alias"]))
                containers.append(container)
                if "commitimage" in spec:
                    logger.debug("Container {container} will be committed".format(**locals()))
                    commit_containers.append(ContainerWithDest(container, spec["commitimage"]))
            else:
                raise InvalidFormat("Invalid link specification '{link_spec}' for image {image_name}".format(**locals()))

        logger.info("Starting temporary container system")
        # TODO convert to new Toji api for with ... as
        temp_system = nagoya.toji.Toji(containers)
        temp_system.init_containers()

        logger.info("Waiting for the root container to finish")
        status_code = docker_client.wait(root.name)
        if not status_code == 0:
            raise ContainerExitError("Root container did not run sucessfully. Exit code: {status_code}".format(**locals()))

        temp_system.stop_containers()

    for container,commitimage in commit_containers:
        logger.info("Commiting {container} container to image {commitimage}".format(**locals()))
        docker_client.commit(container, commitimage)

    for container,persistimage in persist_containers:
        logger.info("Persisting {container} container to image {persistimage}".format(**locals()))
        with TempResourceDirectory(image_root=os.path.join("/", uuid4())) as extract_dest_dir:
            source_data = docker_client.inspect_container(container=container.name)
            source_volumes = source_data["Volumes"].keys()
            # busybox's tar won't accept file/dir arguments with a starting slash
            volume_paths = [v.lstrip("/") for v in source_volumes]

            logger.info("Extracting volume data from {container} container".format(**locals()))
            image_tar_path = os.path.join(extract_dest_dir.image_root, "extract.tar")
            host_tar_path = os.path.join(extract_dest_dir.name, "extract.tar")

            extract_container_name = uuid4()
            # Mount host volume in container
            volumes = [extract_dest_dir.name + ":" + extract_dest_dir.image_root]
            command = ["tar", "-cf", image_tar_path] + volume_paths
            docker_client.create_container(name=extract_container_name,
                                           image="busybox:latest",
                                           volumes=volumes,
                                           command=command)
            # Mount volumes from source container read-only
            volumes_from = [container.name + ":ro"]
            docker_client.start(container=extract_container_name,
                                volumes_from=volumes_from)
            extract_status = docker_client.wait(extract_container_name)
            if not extract_status == 0:
                raise ContainerExitError("Extract container did not run sucessfully. Exit code: {extract_status}".format(**locals()))

            with TempResourceDirectory() as docker_context:
                logger.info("Building image {persistimage} with volume data from {container} container".format(**locals()))
                build_dir = docker_context.name
                dockerfile_path = os.path.join(build_dir, "Dockerfile")
                with open(dockerfile_path, "w") as dockerfile:
                    dockerfile.write("FROM ")
                    dockerfile.write(container.image)
                    dockerfile.write("\n")

                    # tar will be unpacked by docker
                    dockerfile.write("ADD ")
                    dockerfile.write(host_tar_path)
                    dockerfile.write(" ")
                    dockerfile.write("/")
                    dockerfile.write("\n")

                try:
                    nagoya.docker.watch_build(docker_client.build(path=build_dir, tag=persistimage, rm=True, stream=True), quiet_watch)
                except BuildFailed as e:
                    nagoya.docker.cleanup_container(docker_client, e.residual_container)
                    return 2

    temp_system.remove_containers()

#
# Standard image build
#

def build_image(image_name, image_config, client, quiet):
    logger.info("Generating files for {image_name}".format(**locals()))
    with nagoya.docker.build.BuildContext(image_name, image_config["from"], client, quiet) as context:
        context.maintainer(image_config["maintainer"])
        for port in optional_plural(image_config, "exposes"):
            context.expose(port)
        for volume in optional_plural(image_config, "volumes"):
            context.volume(volume)

        for lib_spec in optional_plural(image_config, "libs"):
            at_dir = TODO # TODO get from config "util at /zxc/wer/" ?? atdir should be required in cfg?

            context.include(lib_path, )

        previous_workdir = ""
        for run_spec in optional_plural(image_config, "runs"):
            workdir = TODO # TODO get from config "asd.py in /asdqwe/wer/" ?? Workdir should be required in cfg?

            if not workdir == previous_workdir:
                context.workdir(workdir)
                previous_workdir = workdir
            context.include(TODOsource, TODOimagepath, executable=True)
            context.run(TODOimagepath)

        if "entrypoint" in image_config:
            entrypoint_spec = image_config["entrypoint"]
            # TODO
            context.include(TODOsource, TODOimagepath, executable=True)
            context.entrypoint(TODOimagepath)


    with TempResourceDirectory(image_root="/tmp") as docker_context:
        build_dir = docker_context.name
        dockerfile_path = os.path.join(build_dir, "Dockerfile")
        with open(dockerfile_path, "w") as dockerfile:
            dockerfile.write("FROM ")
            dockerfile.write(image_config["from"])
            dockerfile.write("\n")

            dockerfile.write("MAINTAINER ")
            dockerfile.write(image_config["maintainer"])
            dockerfile.write("\n")

            for port in optional_plural(image_config, "exposes"):
                dockerfile.write("EXPOSE ")
                dockerfile.write(port)
                dockerfile.write("\n")

            for volume in optional_plural(image_config, "volumes"):
                dockerfile.write("VOLUME [\"")
                dockerfile.write(volume)
                dockerfile.write("\"]\n")

            prefix = True
            for lib_path in optional_plural(image_config, "libs"):
                if prefix:
                    dockerfile.write("WORKDIR /tmp/")
                    dockerfile.write("\n")
                    prefix = False

                docker_context.include(lib_path, dockerfile)

            for executable_path in optional_plural(image_config, "runs"):
                path = os.path.join(image_name, executable_path)
                image_path = docker_context.include(path, dockerfile, True)

                dockerfile.write("RUN [\"")
                dockerfile.write(image_path)
                dockerfile.write("\"]\n")

            if "entrypoint" in image_config:
                entrypoint_path = image_config["entrypoint"]
                path = os.path.join(image_name, entrypoint_path)
                image_path = docker_context.include(path, dockerfile, True)

                dockerfile.write("ENTRYPOINT [\"")
                dockerfile.write(image_path)
                dockerfile.write("\"]\n")

        logger.info("Building {image_name}".format(**locals()))
        try:
            nagoya.docker.watch_build(docker_client.build(path=build_dir, tag=image_name, rm=True, stream=True), quiet_watch)
        except BuildFailed as e:
            nagoya.docker.cleanup_container(docker_client, e.residual_container)
            return 2

#
# Build images
#

def build_images(config, images, quiet):
    num_img = len(images)
    logger.info("Building {0} image{1}".format(num_img, "s" if num_img > 1 else ""))

    docker_client = docker.Client(timeout=5)
    docker_client.ping()

    for image in images:
        logger.debug("Processing image {image}".format(**locals()))
        image_config = config[image]

        if not container_system_option_names.isdisjoint(image_config.keys()):
            build_container_system(image, image_config, docker_client, quiet)
        else:
            build_image(image, image_config, docker_client, quiet)

    logger.info("Done")

#
# Main
#

# TODO might have to put this in a seperate file outside of the module if running the module doesn't work properly

default_config_paths = ["images.cfg"]
boolean_config_options = ["commit"]

def sc_build(args):
    config = nagoya.cfg.read_config(args.config, default_config_paths, boolean_config_options)
    return build_images(config, args.images, args.quiet_build)

def scargs_build(parser):
    parser.add_argument("-b", "--quiet-build", action="store_true", help="Do not print the builds' stdout/stderr")
    imgs = parser.add_argument("images", metavar="IMAGE", nargs="+", help="Image to build")
    if nagoya.args.argcomplete_available:
        imgs.completer = nagoya.args.ConfigSectionsCompleter(default_config_paths)

def sc_clean(args):
    pass

if __name__ == "__main__":
    parser = nagoya.args.create_default_argument_parser(description="Build docker images")
    nagoya.args.add_subcommand_subparsers(parser)
    nagoya.args.attempt_autocomplete(parser)
    args = parser.parse_args()

    nagoya.log.setup_logger(args.quiet, args.verbose)

    nagoya.args.run_subcommand_func(args, parser)
