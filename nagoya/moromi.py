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
import re
import collections
import itertools

import docker
import toposort

import nagoya.dockerext.build
import nagoya.buildcsys
import nagoya.cli.cfg

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

container_system_option_names = {"system", "commits", "persists", "root"}

dest_spec_pattern = re.compile(r'^(?P<container>[^ ]+) to (?P<image>[^ ]+)$')
ContainerDest = collections.namedtuple("ContainerDest", ["container", "image"])
def parse_dest_spec(spec, opt_name, image_name):
    match = dest_spec_pattern.match(spec)
    if match:
        return ContainerDest(**match.groupdict())
    else:
        raise InvalidFormat("Invalid {opt_name} specification '{spec}' for image {image_name}".format(**locals()))

def build_container_system(image_name, image_config, client, quiet, extra_env):
    logger.info("Creating container system for {image_name}".format(**locals()))

    sys_config = nagoya.cli.cfg.read_one(image_config["system"], ["detach", "run_once"])

    with nagoya.buildcsys.BuildContainerSystem.from_dict(sys_config, client=client) as bcs:
        bcs.cleanup = "remove"
        bcs.quiet = quiet
        bcs.root(image_config["root"])

        if "entrypoint" in image_config:
            entrypoint_spec = image_config["entrypoint"]
            res_paths = parse_dir_spec(entrypoint_spec, "entrypoint", image_name)
            bcs.root.working_dir = res_paths.dest_dir
            bcs.root.entrypoint = res_paths.dest_path
            bcs.volume_include(bcs.root, res_paths.src_path, res_paths.dest_path, executable=True)

        for lib_spec in optional_plural(image_config, "libs"):
            res_paths = parse_dir_spec(lib_spec, "lib", image_name)
            bcs.volume_include(bcs.root, res_paths.src_path, res_paths.dest_path)

        for commit_spec in optional_plural(image_config, "commits"):
            dest = parse_dest_spec(commit_spec, "commits", image_name)
            logger.debug("Container {dest.container} will be committed to {dest.image}".format(**locals()))
            bcs.commit(dest.container, dest.image)

        for persist_spec in optional_plural(image_config, "persists"):
            dest = parse_dest_spec(commit_spec, "persists", image_name)
            logger.debug("Container {dest.container} will be persisted to {dest.image}".format(**locals()))
            bcs.persist(dest.container, dest.image)

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

        if "inpath" in gd:
            image_dir = gd["inpath"]
            image_path = os.path.join(image_dir, src_basename)
        elif "atpath" in gd:
            image_path = gd["atpath"]
            image_dir = os.path.dirname(image_path)
        else:
            raise Exception("dir_spec_pattern is broken")

        return ResPaths(src_path, image_path, image_dir)
    else:
        raise InvalidFormat("Invalid {opt_name} specification '{spec}' for image {image_name}".format(**locals()))

# Workaround Python 2 not having the nonlocal keyword
class Previous(object):
    def __init__(self, initial):
        self.value = initial

    def __call__(self, new):
        if self.value == new:
            return True
        else:
            self.value = new
            return False

def build_image(image_name, image_config, client, quiet, extra_env):
    logger.info("Generating files for {image_name}".format(**locals()))
    with nagoya.dockerext.build.BuildContext(image_name, image_config["from"], client, quiet) as context:
        context.maintainer(image_config["maintainer"])

        for port in optional_plural(image_config, "exposes"):
            context.expose(port)

        for volume in optional_plural(image_config, "volumes"):
            context.volume(volume)

        for lib_spec in optional_plural(image_config, "libs"):
            res_paths = parse_dir_spec(lib_spec, "lib", image_name)
            context.include(res_paths.src_path, res_paths.dest_path)

        for env_spec in itertools.chain(optional_plural(image_config, "envs"), extra_env):
            k,v = env_spec.split("=", 1)
            context.env(k, v)

        previous_workdir = Previous("")
        def add_workdir(image_dir):
            if not previous_workdir(image_dir):
                context.workdir(image_dir)

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

def resolve_dep_order(images_config):
    # Figure out what images are provided by this config
    # Anything not provided is assumed to exist already
    provided_images = dict()
    for image_name,image_config in images_config.items():
        if container_system_option_names.isdisjoint(image_config.keys()):
            provided_images[image_name] = image_name
        else:
            provided_images[image_name] = provided
            for commit_spec in optional_plural(image_config, "commits"):
                dest = parse_dest_spec(commit_spec, "commits", image_name)
                provided_images[dest.image] = image_name
            for persist_spec in optional_plural(image_config, "persists"):
                dest = parse_dest_spec(commit_spec, "persists", image_name)
                provided_images[dest.image] = image_name

    # Figure out the images required (among those provided) by images in this config
    deps = dict()
    for image_name,image_config in images_config.items():
        req = set()
        deps[image_name] = req
        if container_system_option_names.isdisjoint(image_config.keys()):
            from_name = image_config["from"].split(":", 1)[0]
            if from_name in provided_images:
                req.add(from_name)
        else:
            sys_config = nagoya.cli.cfg.read_one(image_config["system"])
            for cont_config in sys_config.values():
                image_name = cont_config["image"].split(":", 1)[0]
                if image_name in provided_images:
                    req.add(image_name)

    # Toposort to sync groups, use original order of keys to order within groups
    image_names = []
    for group in toposort.toposort(deps):
        image_names.extend(sorted(group, key=lambda n: images_config.keys().index(n)))

    return image_names

def build_images(config, quiet, env, images=None):
    if images is None:
        logger.info("Resolving image dependency order")
        images = resolve_dep_order(config)

    num_img = len(images)
    logger.info("Building {0} image{1}".format(num_img, "s" if num_img > 1 else ""))

    docker_client = docker.Client(timeout=10)
    docker_client.ping()

    for image in images:
        logger.debug("Processing image {image}".format(**locals()))
        image_config = config[image]

        if not container_system_option_names.isdisjoint(image_config.keys()):
            build_container_system(image, image_config, docker_client, quiet, env)
        else:
            build_image(image, image_config, docker_client, quiet, env)

    logger.info("Done")
