#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
# Will run in Python 2 or Python 3

import nagoya.cli.args
import nagoya.cli.log
import nagoya.cli.cfg
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
    pass

if __name__ == "__main__":
    parser = nagoya.cli.args.create_default_argument_parser(description="Build docker images")
    nagoya.cli.args.add_subcommand_subparsers(parser)
    nagoya.cli.args.attempt_autocomplete(parser)
    args = parser.parse_args()

    nagoya.cli.log.setup_logger(args.quiet, args.verbose)

    nagoya.cli.args.run_subcommand_func(args, parser)

