import os
try:
    import ConfigParser as configparser
except ImportError:
    import configparser

def read_one(path, boolean_options=[]):
    config = configparser.ConfigParser()
    # Not using the built-in multiple read functionality so we can expand format strings per-file
    successful = config.read(path)
    if successful:
        format_vars = dict()
        format_vars["cfgdir"] = os.path.dirname(path)

        d = dict()
        for section in config.sections():
            d[section] = dict()
            format_vars["section"] = section
            format_vars["secdir"] = os.path.join(format_vars["cfgdir"], section)
            for option in config.options(section):
                # Convert specified booleans
                if option in boolean_options:
                    value = config.getboolean(section, option)
                else:
                    value = config.get(section, option)
                    # Format string
                    value = value.format(**format_vars)

                d[section][option] = value

        return d
    else:
        return None

def read_config(paths, default_paths, boolean_options=[]):
    # Provided as a workaround to argparse's append appending to defaults
    if paths == []:
        paths = default_paths

    dictionary = dict()
    successful_paths = []
    for path in map(os.path.expanduser, paths):
        d = read_one(path, boolean_options)
        dictionary.update(d)
        successful_paths.append(path)

    return (dictionary, successful_paths)
