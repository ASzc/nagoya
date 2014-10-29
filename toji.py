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

import sys
import os

import nagoya.cli.args
import nagoya.cli.log
import nagoya.cli.cfg
import nagoya.toji

default_config_paths = ["cfg/containers.cfg"]
boolean_config_options = ["multiple", "detach", "run_once"]

# So any local callback modules referenced in the cfg can be loaded
def _add_cfg_dirs_to_path(cfg_paths):
    for cfg_path in cfg_paths:
        cfg_dir = os.path.dirname(cfg_path)
        sys.path.append(cfg_dir)

def _config_dict(args):
    d, successful_paths = nagoya.cli.cfg.read_config(args.config, default_config_paths, boolean_config_options)
    _add_cfg_dirs_to_path(successful_paths)
    return d

def sc_init(args):
    toji = nagoya.toji.Toji.from_dict(_config_dict(args))
    toji.init_containers()

def scargs_init(parser):
    parser.description = "Create and start the containers defined in the configuration"

def sc_start(args):
    toji = nagoya.toji.Toji.from_dict(_config_dict(args))
    toji.start_containers()

def scargs_start(parser):
    parser.description = "Start the already created containers defined in the configuration"

def sc_stop(args):
    toji = nagoya.toji.Toji.from_dict(_config_dict(args))
    toji.stop_containers()

def scargs_stop(parser):
    parser.description = "Stop any started containers defined in the configuration"

def sc_remove(args):
    toji = nagoya.toji.Toji.from_dict(_config_dict(args))
    toji.remove_containers()

def scargs_remove(parser):
    parser.description = "Remove any created containers defined in the configuration"

if __name__ == "__main__":
    parser = nagoya.cli.args.create_default_argument_parser(description="Manage Docker container systems")
    nagoya.cli.args.add_subcommand_subparsers(parser)
    nagoya.cli.args.attempt_autocomplete(parser)
    args = parser.parse_args()

    nagoya.cli.log.setup_logger(args.quiet, args.verbose)

    nagoya.cli.args.run_subcommand_func(args, parser)
