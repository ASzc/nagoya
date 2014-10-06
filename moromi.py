#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
# Will run in Python 2 or Python 3

import nagoya.cli.args
import nagoya.cli.log
import nagoya.cli.cfg
import nagoya.moromi

default_config_paths = ["images.cfg"]
boolean_config_options = ["commit"]

def sc_build(args):
    config = nagoya.cfg.read_config(args.config, default_config_paths, boolean_config_options)
    return nagoya.moromi.build_images(config, args.images, args.quiet_build)

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
