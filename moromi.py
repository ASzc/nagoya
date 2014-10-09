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

import docker

import nagoya.cli.args
import nagoya.cli.log
import nagoya.cli.cfg
import nagoya.dockerext.build
import nagoya.moromi

default_config_paths = ["cfg/images.cfg"]
boolean_config_options = ["commit"]

def sc_build(args):
    config, _ = nagoya.cli.cfg.read_config(args.config, default_config_paths, boolean_config_options)
    return nagoya.moromi.build_images(config, args.images, args.quiet_build)

def scargs_build(parser):
    parser.add_argument("-b", "--quiet-build", action="store_true", help="Do not print the builds' stdout/stderr")
    imgs = parser.add_argument("images", metavar="IMAGE", nargs="+", help="Image to build")
    if nagoya.cli.args.argcomplete_available:
        imgs.completer = nagoya.cli.args.ConfigSectionsCompleter(default_config_paths)

def sc_clean(args):
    c = docker.Client()
    nagoya.dockerext.build.clean_untagged_images(c)

if __name__ == "__main__":
    parser = nagoya.cli.args.create_default_argument_parser(description="Build docker images")
    nagoya.cli.args.add_subcommand_subparsers(parser)
    nagoya.cli.args.attempt_autocomplete(parser)
    args = parser.parse_args()

    nagoya.cli.log.setup_logger(args.quiet, args.verbose)

    nagoya.cli.args.run_subcommand_func(args, parser)

