#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
# Will run in Python 2 or Python 3

import nagoya.args
import nagoya.log
import nagoya.cfg
import nagoya.toji

default_config_paths = ["containers.cfg"]
boolean_config_options = ["multiple", "detach", "run_once"]

def _config_dict(args):
    return nagoya.cfg.read_config(args.config, default_config_paths, boolean_config_options)

def sc_init(args):
    toji = Toji.from_dict(_config_dict(args))
    toji.init_containers()

def sc_start(args):
    toji = Toji.from_dict(_config_dict(args))
    toji.start_containers()

def sc_stop(args):
    toji = Toji.from_dict(_config_dict(args))
    toji.stop_containers()

def sc_remove(args):
    toji = Toji.from_dict(_config_dict(args))
    toji.remove_containers()

if __name__ == "__main__":
    parser = nagoya.args.create_default_argument_parser(description="Manage Koji Docker container systems")
    nagoya.args.add_subcommand_subparsers(parser)
    nagoya.args.attempt_autocomplete(parser)
    args = parser.parse_args()

    nagoya.log.setup_logger(args.quiet, args.verbose)

    nagoya.args.run_subcommand_func(args, parser)
