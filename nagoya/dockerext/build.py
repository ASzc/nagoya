from __future__ import print_function
import sys
import logging
import json
import re
import os

import docker

import nagoya.temp

logger = logging.getLogger("nagoya.dockerext")

class BuildFailed(Exception):
    """
    If a build fails when being watched
    """

    def __init__(self, residual_container, error_lines):
        super(BuildFailed, self).__init__()
        self.residual_container = residual_container
        self.error_lines = error_lines

# Patterns for watch_build
detail_pattern = re.compile(r'^ ---> (?P<text>.*)$')
running_in_pattern = re.compile(r'^Running in (?P<container>.*)$')
removing_pattern = re.compile(r'^Removing intermediate container (?P<container>.*)$')

def watch_build(stream, quiet):
    failed = False
    latest_container = None
    error_lines = []

    try:
        for line_json in stream:
            try:
                line_parsed = json.loads(line_json)
            except ValueError as e:
                logger.error("Invalid data read from stream: {e}".format(**locals()))
                continue

            if "error" in line_parsed:
                logger.error(line_parsed["error"])
                error_lines.append(line_parsed["error"])
                failed = True
            elif "stream" in line_parsed:
                line_text = line_parsed["stream"]
                line_text_rstrip = line_text.rstrip()

                detail = detail_pattern.match(line_text_rstrip)
                if detail:
                    logger.debug(line_text_rstrip)
                    text = detail.group("text")
                    running_in = running_in_pattern.match(text)
                    if running_in:
                        latest_container = running_in.group("container")
                else:
                    removing = removing_pattern.match(line_text_rstrip)
                    if removing:
                        logger.debug(line_text_rstrip)
                        container = removing.group("container")
                        if not latest_container == container:
                            logger.debug("Docker build removed untracked container {container}".format(**locals()))
                        latest_container = None
                    else:
                        if not quiet:
                            print(line_text, end="")
                            # Workaround lack of print flush parameter in Python 2 (even with future import)
                            sys.stdout.flush()


            elif "status" in line_parsed:
                logger.info(line_parsed["status"])
            else:
                logger.error("Unknown data: {line_parsed}".format(**locals()))
    except KeyboardInterrupt as e:
        logger.error("User interrupted build")
        failed = True

    if failed:
        raise BuildFailed(latest_container, error_lines)

def cleanup_container(docker_client, container_id):
    # Make sure container is removed
    try:
        container = docker_client.inspect_container(container_id)

        try:
            docker_client.kill(container_id, signal=9)
            docker_client.remove_container(container_id)
            logger.info("Removed container {container_id}".format(**locals()))
        except docker.errors.APIError as e:
            logger.debug("Couldn't kill/remove container {container_id}: {e}".format(**locals()))

        # Make sure any untagged image associated with the container is removed
        if "Image" in container:
            image_id = container["Image"]
            found = False
            try:
                # API's inspect_image doesn't return data with RepoTags for some unknown reason
                for image in docker_client.images():
                    if image["Id"] == image_id:
                        found = True
                        if image["RepoTags"] == ["<none>:<none>"]:
                            try:
                                docker_client.remove_image(image_id)
                                logger.info("Removed image {image_id} for container {container_id}".format(**locals()))
                            except docker.errors.APIError as e:
                                logger.debug("Couldn't remove image {image_id} for container {container_id}: {e}".format(**locals()))
                        else:
                            logger.debug("Image {image_id} for container {container_id} wasn't untagged".format(**locals()))
                        break
            except docker.errors.APIError as e:
                logger.debug("Error when listing images: {e}".format(**locals()))
            if not found:
                logger.debug("Image {image_id} for container {container_id} doesn't exist".format(**locals()))
        else:
            logger.debug("Container {container_id} doesn't have an image".format(**locals()))
    except docker.errors.APIError as e:
        logger.debug("Container {container_id} doesn't exist: {e}".format(**locals()))

class BuildContext(nagoya.temp.TempDirectory):
    """
    Succinctly construct a build context and produce an image from it. Use with
    "with ... as" blocks. Builds automatically when leaving the "with" block if
    no exception is raised.
    """

    def __init__(self, image_name, from_image_name, docker_client, quiet=False):
        self.image_name = image_name
        self.docker_client = docker_client
        self.quiet = quiet

        super(BuildContext, self).__init__()

        self.dockerfile_path = os.path.join(self.name, "Dockerfile")
        self.df = open(self.dockerfile_path, "w")
        self._from(from_image_name)

    def _write_df(self, *args):
        wrote_something = False

        for arg in args:
            if wrote_something:
                self.df.write(" ")
            self.df.write(arg)
            wrote_something = True

        if wrote_something:
            self.df.write("\n")

    def _from(self, image_name):
        self._write_df("FROM", image_name)

    def maintainer(self, maintainer):
        self._write_df("MAINTAINER", maintainer)

    def expose(self, port):
        self._write_df("EXPOSE", port)

    def volume(self, volume):
        self._write_df("VOLUME", volume)

    def workdir(self, workdir):
        self._write_df("WORKDIR", workdir)

    def add(self, context_path, image_path):
        self._write_df("ADD", context_path, image_path)

    def include(self, source_path, image_path, executable=False):
        # Include in context dir
        context_rel_path = os.path.normpath(image_path)
        super(BuildContext, self).include(source_path, context_rel_path, executable)
        # Add to image from context dir
        self.add(context_rel_path, image_path)

    def run(self, image_path, args=[]):
        self._write_df("RUN", json.dumps([image_path] + args))

    def entrypoint(self, image_path, args=[]):
        self._write_df("ENTRYPOINT", json.dumps([image_path] + args))

    def _build(self):
        try:
            logger.info("Building {self.image_name}".format(**locals()))
            build_stream = self.docker_client.build(path=self.name, tag=self.image_name, rm=True, stream=True)
            watch_build(build_stream, self.quiet)
        except BuildFailed as e:
            cleanup_container(self.docker_client, e.residual_container)
            raise

    def __exit__(self, exc, value, tb):
        try:
            self.df.close()

            if exc is None:
                self._build()
        finally:
            super(BuildContext, self).__exit__(exc, value, tb)
