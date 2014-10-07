#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
# Will run in Python 2 or Python 3

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

def sc_start(args):
    toji = nagoya.toji.Toji.from_dict(_config_dict(args))
    toji.start_containers()

def sc_stop(args):
    toji = nagoya.toji.Toji.from_dict(_config_dict(args))
    toji.stop_containers()

def sc_remove(args):
    toji = nagoya.toji.Toji.from_dict(_config_dict(args))
    toji.remove_containers()

if __name__ == "__main__":
    parser = nagoya.cli.args.create_default_argument_parser(description="Manage Koji Docker container systems")
    nagoya.cli.args.add_subcommand_subparsers(parser)
    nagoya.cli.args.attempt_autocomplete(parser)
    args = parser.parse_args()

    nagoya.cli.log.setup_logger(args.quiet, args.verbose)

    nagoya.cli.args.run_subcommand_func(args, parser)
