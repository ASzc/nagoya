#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
# Will run in Python 2 or Python 3

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

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

import os
import shutil
import tarfile
import io
import argparse
import collections
import sys
import logging

# Human readable CWD
cwd = "./"

logger = logging.getLogger("deps")

#
# Tar Download
#

def split_path(path):
    norm_path = os.path.normpath(path)
    return [p for p in norm_path.split("/") if not p == ""]

def join_path_parts(parts):
    return "/".join(parts)

def get_tar(tar_url, output_dir=cwd, member_processor=lambda x: x):
    logger.debug("Extracting parts of tar {tar_url} to {output_dir}".format(**locals()))
    response = urlopen(tar_url)
    fileobj = io.BytesIO(response.read())
    tar = tarfile.open(fileobj=fileobj)
    for member in tar.getmembers():
        member = member_processor(member)
        if member is not None:
            tar.extract(member, path=output_dir)

class Subdir(object):
    def __init__(self, path):
        self.path = path
        self.parts = split_path(self.path)
        self.depth = len(self.parts)

    def __repr__(self):
        return self.path

def get_source_dir(source, owner, repo, ref, repo_subdirs, output_dir=cwd, overwrite=False):
    non_existing_repo_subdirs = set()
    for repo_subdir in repo_subdirs:
        if not overwrite and os.path.exists(os.path.join(output_dir, os.path.basename(repo_subdir))):
            logger.debug("Directory {repo_subdir} already exists in {output_dir}".format(**locals()))
        else:
            non_existing_repo_subdirs.add(Subdir(repo_subdir))
            logger.info("Downloading directory {repo_subdir} to {output_dir}".format(**locals()))

    if not non_existing_repo_subdirs == set():
        extracted_subdirs = set()

        def rewrite_gh_tar(member):
            path_parts = split_path(member.name)

            # See if it is in a valid subdir, ignoring first directory in tar path
            trimmed_parts = path_parts[1:]
            for subdir in non_existing_repo_subdirs:
                if trimmed_parts[:subdir.depth] == subdir.parts:
                    # Rewrite name to remove first directory in tar path
                    member.name = join_path_parts(trimmed_parts)
                    # Flag for extraction
                    extracted_subdirs.add(subdir)
                    return member

        url = source.format(owner=owner, repo=repo, ref=ref)
        get_tar(url, output_dir, rewrite_gh_tar)

        non_extracted_subdirs = non_existing_repo_subdirs - extracted_subdirs
        if not non_extracted_subdirs == set():
            raise MissingSubdirsError(non_extracted_subdirs, url)

#
# File Download
#

def get_file(file_url, output_dir=cwd, overwrite=False):
    file_basename = os.path.basename(file_url)
    file_path = os.path.join(output_dir, file_basename)
    if overwrite or not os.path.exists(file_path):
        logger.info("Downloading file {file_basename} to {output_dir}".format(**locals()))
        # Python 2 urlopen is not enterable
        response = urlopen(file_url)
        with open(file_path, "wb") as file_out:
            shutil.copyfileobj(response, file_out)
    else:
        logger.debug("File {file_basename} already exists in {output_dir}".format(**locals()))

def get_source_file(source, owner, repo, ref, file_path, output_dir=cwd, overwrite=False):
    url = source.format(owner=owner, repo=repo, ref=ref, file_path=file_path)
    get_file(url, output_dir, overwrite=overwrite)

#
# Dependencies
#

class MissingSubdirsError(Exception):
    def __init__(self, subdirs, url):
        self.subdirs = subdirs
        self.url = url
        message = "Subdir(s) {0} were not found in the url {1}".format(list(subdirs), url)
        super(MissingSubdirsError, self).__init__(message)

github_tar = "https://api.github.com/repos/{owner}/{repo}/tarball/{ref}"
googlecode_tar = "https://{repo}.googlecode.com/archive/{ref}.tar.gz"
github_file = "https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{file_path}"
bitbucket_file = "https://bitbucket.org/{owner}/{repo}/raw/{ref}/{file_path}"

FileDep = collections.namedtuple("FileDep", ["source", "owner", "repo", "ref", "file_path"])
SubdirDep = collections.namedtuple("SubdirDep", ["source", "owner", "repo", "ref", "repo_subdirs"])

files = [ FileDep(bitbucket_file, "ericvsmith", "toposort", "1.1", "toposort.py"),
          FileDep(github_file, "liris", "websocket-client", "v0.11.0", "websocket.py"),
          FileDep(bitbucket_file,  "gutworth", "six", "1.8.0", "six.py") ]

dirs = [ SubdirDep(github_tar, "docker", "docker-py", "0.5.0", ["docker"]),
         SubdirDep(github_tar, "kennethreitz", "requests", "v2.2.1", ["requests"]) ]

try:
    import concurrent.futures
except ImportError as e:
    dirs.append(SubdirDep(googlecode_tar, "", "pythonfutures", "2.2.0", ["concurrent"]))

#
# Main
#

def dl(args):
    for f in files:
        get_source_file(overwrite=args.force, output_dir=args.output_dir, **f._asdict())
    for d in dirs:
        get_source_dir(overwrite=args.force, output_dir=args.output_dir, **d._asdict())

def clean(args):
    for f in files:
        path = os.path.join(args.output_dir, f.file_path)
        if os.path.exists(path):
            logger.info("Deleting file {path}".format(**locals()))
            os.remove(path)
        else:
            logger.debug("File {path} does not exist".format(**locals()))
    for d in dirs:
        for repo_subdir in d.repo_subdirs:
            path = os.path.join(args.output_dir, repo_subdir)
            if os.path.exists(path):
                logger.info("Deleting directory {path}".format(**locals()))
                shutil.rmtree(path)
            else:
                logger.debug("Directory {path} does not exist".format(**locals()))

def gitignore(args):
    def printignore(path, directory=False):
        relpath = os.path.relpath(path, args.output_dir)
        sys.stdout.write("/")
        sys.stdout.write(relpath)
        if directory:
            sys.stdout.write("/")
        sys.stdout.write("\n")

    for f in files:
        printignore(f.file_path)
    for d in dirs:
        for repo_subdir in d.repo_subdirs:
            printignore(repo_subdir, directory=True)

    sys.stdout.flush()

def create_argparser():
    parser = argparse.ArgumentParser(description="Work with local copies of module dependencies")
    parser.add_argument("-d", "--output-dir", default=cwd, help="Use this directory instead of the working directory")
    subparsers = parser.add_subparsers()

    dl_parser = subparsers.add_parser("dl", description="Download module dependencies")
    dl_parser.set_defaults(func=dl)
    dl_parser.add_argument("-f", "--force", action="store_true", help="Overwrite existing files if required")

    clean_parser = subparsers.add_parser("clean", description="Clean downloaded module dependencies")
    clean_parser.set_defaults(func=clean)

    clean_parser = subparsers.add_parser("gitignore", description="Print gitignore entries for module dependencies")
    clean_parser.set_defaults(func=gitignore)

    return parser

if __name__ == "__main__":
    parser = create_argparser()
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    if "func" in args:
        args.func(args)
    else:
        parser.print_help()
