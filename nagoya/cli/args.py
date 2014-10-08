import argparse
import sys
import os
try:
    import ConfigParser as configparser
except ImportError:
    import configparser
try:
    import argcomplete
    argcomplete_available = True
except ImportError:
    argcomplete_available = False

class ConfigSectionsCompleter(object):
    """
    Offers completion choices based on the names of sections in config files from:
        - the default list provided
        - or the argument name provided, if it is present in the arguments
    """

    def __init__(self, default_config_paths, config_arg_name="config"):
        self.default_config_paths = [os.path.expanduser(p) for p in default_config_paths]
        self.config_arg_name = config_arg_name

    def __call__(self, prefix, action, parsed_args):
        parsed_args = vars(parsed_args)
        if self.config_arg_name in parsed_args and parsed_args[self.config_arg_name]:
            config_paths = parsed_args.config
        else:
            config_paths = self.default_config_paths
        config = configparser.ConfigParser()
        config.read(config_paths)
        return config.sections()

def attempt_autocomplete(parser):
    if argcomplete_available:
        argcomplete.autocomplete(parser)

subcommand_func_prefix = "sc_"
subcommand_args_func_prefix = "scargs_"

def add_subcommand_subparsers(root_parser, module_name="__main__"):
    root_subparsers = root_parser.add_subparsers()

    main_attributes = sys.modules[module_name].__dict__
    subcommand_names = [a for a in main_attributes if a.startswith(subcommand_func_prefix)]

    subcommand_func_prefix_len = len(subcommand_func_prefix)

    for subcommand_name in subcommand_names:
        parser_name = subcommand_name[subcommand_func_prefix_len:]
        parser = root_subparsers.add_parser(parser_name)

        parser_function = main_attributes[subcommand_name]
        parser.set_defaults(func=parser_function)

        config_function_name = subcommand_args_func_prefix + parser_name
        if config_function_name in main_attributes:
            parser_config_function = main_attributes[config_function_name]
            parser_config_function(parser)

def create_default_argument_parser(with_config=True, **kwargs):
    parser = argparse.ArgumentParser(**kwargs)
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Make logging more verbose (repeatable)")
    parser.add_argument("-q", "--quiet", action="count", default=0, help="Make logging less verbose (repeatable)")
    if with_config:
        parser.add_argument("-c", "--config", action="append", default=[], help="Specify a non-default cfg file location")

    return parser

def run_subcommand_func(args, parser):
    if "func" in args:
        sys.exit(args.func(args))
    else:
        parser.print_help()
