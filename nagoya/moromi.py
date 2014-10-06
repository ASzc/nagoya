#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import logging
import os
import re
import collections

import docker

import nagoya.docker.build
import nagoya.build.consys

logger = logging.getLogger("nagoya.build")

#
# Exceptions
#

class InvalidFormat(Exception):
    pass

#
# Helpers
#

def line_split(string):
    return map(str.strip, string.split("\n"))

def optional_plural(cfg, key):
    if key in cfg:
        logger.debug("Optional config key {key} exists".format(**locals()))
        for elem in line_split(cfg[key]):
            yield elem
    else:
        logger.debug("Optional config key {key} does not exist".format(**locals()))

#
# Container system image build
#

container_system_option_names = {"volumes_from", "links", "commit"}

volume_spec_pattern = re.compile(r'^(?P<image>[^ ]+) then (discard$|persist to (?P<persist_image>[^: ]+)$)')
VolImg = collections.namedtuple("VolImg", ["image", "persist_image"])
def parse_volume_spec(spec, opt_name, image_name):
    match = volume_spec_pattern.match(spec)
    if match:
        return VolImg(**match.groupdict())
    else:
        raise InvalidFormat("Invalid {opt_name} specification '{spec}' for image {image_name}".format(**locals()))

link_spec_pattern = re.compile(r'^(?P<image>[^ ]+) alias (?P<alias>[^ ]+) then (discard$|commit to (?P<commit_image>[^: ]+)$)')
LinkImg = collections.namedtuple("LinkImg", ["image", "alias", "commit_image"])
def parse_link_spec(spec, opt_name, image_name):
    match = link_spec_pattern.match(spec)
    if match:
        return LinkImg(**match.groupdict())
    else:
        raise InvalidFormat("Invalid {opt_name} specification '{spec}' for image {image_name}".format(**locals()))

ContainerWithDest = collections.namedtuple("ContainerWithDest", ["container", "destimage"])

def build_container_system(image_name, image_config, client, quiet):
    logger.info("Creating container system for {image_name}".format(**locals()))

    with nagoya.build.consys.BuildContainerSystem(root_image=image_config["from"],
                                                  client=client,
                                                  cleanup="remove",
                                                  quiet=quiet) as bcs:

        if "commit" in image_config and image_config["commit"]:
            logger.debug("Root container {root} will be committed".format(**locals()))
            bcs.commit(bcs.root)

        if "entrypoint" in image_config:
            entrypoint_spec = image_config["entrypoint"]
            res_paths = parse_dir_spec(entrypoint_spec, "entrypoint", image_name)
            bcs.root.working_dir = res_paths.dest_dir
            bcs.volume_include(bcs.root, res_paths.src_path, res_paths.dest_path, executable=True)

        for lib_spec in optional_plural(image_config, "libs"):
            res_paths = parse_dir_spec(lib_spec, "lib", image_name)
            bcs.volume_include(bcs.root, res_paths.src_path, dest_dir.dest_path)

        for volume_spec in optional_plural(image_config, "volumes_from"):
            vol = parse_volume_spec(volume_spec, "volume_from", image_name)
            vol_container = bcs.container(image=vol.image, detach=False)
            logger.debug("Root container will have volumes from container {vol_container}".format(**locals()))
            bcs.root.add_volume_from(vol_container.name, "rw")
            if vol.persist_image is not None:
                logger.debug("Container {vol_container} will be persisted to {vol.persist_image}".format(**locals()))
                bcs.persist(vol_container, vol.persist_image)

        for link_spec in optional_plural(image_config, "links"):
            link = parse_link_spec(image_spec, "link", image_name)
            link_container = bcs.container(image=link.image, detach=True)
            logger.debug("Root container will be linked to container {link_container}".format(**locals()))
            bcs.root.add_link(link_container.name, "rw")
            if link.commit_image is not None:
                logger.debug("Container {link_container} will be committed to {vol.commit_image}".format(**locals()))
                bcs.persist(link_container, link.commit_image)

#
# Standard image build
#

dir_spec_pattern = re.compile(r'^(?P<sourcepath>.+) (?:in (?P<inpath>.+)|at (?P<atpath>.+))$')

ResPaths = collections.namedtuple("ResCopyPaths", ["src_path", "dest_path", "dest_dir"])

def parse_dir_spec(spec, opt_name, image_name):
    match = dir_spec_pattern.match(spec)
    if match:
        gd = match.groupdict()
        src_path = gd["sourcepath"]
        src_basename = os.path.basename(src_path)

        if inpath in gd:
            image_dir = gd["inpath"]
            image_path = os.path.join(image_dir, src_basename)
        elif atpath in gd:
            image_path = gd["atpath"]
            image_dir = os.path.dirname(image_path)
        else:
            raise Exception("dir_spec_pattern is broken")

        return ResPaths(src_path, image_path, image_dir)
    else:
        raise InvalidFormat("Invalid {opt_name} specification '{spec}' for image {image_name}".format(**locals()))

def build_image(image_name, image_config, client, quiet):
    logger.info("Generating files for {image_name}".format(**locals()))
    with nagoya.docker.build.BuildContext(image_name, image_config["from"], client, quiet) as context:
        context.maintainer(image_config["maintainer"])

        for port in optional_plural(image_config, "exposes"):
            context.expose(port)

        for volume in optional_plural(image_config, "volumes"):
            context.volume(volume)

        for lib_spec in optional_plural(image_config, "libs"):
            res_paths = parse_dir_spec(lib_spec, "lib", image_name)
            context.include(res_paths.src_path, res_paths.dest_path)

        previous_workdir = ""
        def add_workdir(image_dir):
            if not previous_workdir == image_dir:
                context.workdir(image_dir)
                previous_workdir = image_dir

        for run_spec in optional_plural(image_config, "runs"):
            res_paths = parse_dir_spec(run_spec, "run", image_name)
            context.include(res_paths.src_path, res_paths.dest_path, executable=True)
            add_workdir(res_paths.dest_dir)
            context.run(res_paths.dest_path)

        if "entrypoint" in image_config:
            entrypoint_spec = image_config["entrypoint"]
            res_paths = parse_dir_spec(entrypoint_spec, "entrypoint", image_name)
            context.include(res_paths.src_path, res_paths.dest_path, executable=True)
            add_workdir(res_paths.dest_dir)
            context.entrypoint(res_paths.dest_path)

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
