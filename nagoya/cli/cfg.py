import os
try:
    import ConfigParser as configparser
except ImportError:
    import configparser

def read_config(paths, default_paths, boolean_options=[]):
    # Provided as a workaround to argparse's append appending to defaults
    if paths == []:
        paths = default_paths

    config = configparser.ConfigParser()
    successful_paths = config.read(map(os.path.expanduser, paths))

    # Convert to dict, as 2.x configparser doesn't implement MutableMapping
    dictionary = dict()
    for section in config.sections():
        dictionary[section] = dict()
        for option in config.options(section):
            # Convert specified booleans
            if option in boolean_options:
                value = config.getboolean(section, option)
            else:
                value = config.get(section, option)
            dictionary[section][option] = value

    return (dictionary, successful_paths)
