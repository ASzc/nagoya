import sys
import logging

def setup_logger(quiet_count, verbose_count, color=None):
    color = sys.stderr.isatty() if color is None else color

    verbosity = quiet_count - verbose_count
    level = logging.INFO + (verbosity * 10)
    if level >= logging.INFO:
        form = "%(name)s %(levelname)s: %(message)s"
    else:
        form = "%(name)s.%(funcName)s %(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=form)

    if color:
        off = '\x1b[0m'
        bold = '\x1b[1m'
        blue = bold + '\x1b[34m'
        green = bold + '\x1b[32m'
        red = bold + '\x1b[31m'
        yellow = bold + '\x1b[33m'

        # Levels are CRITICAL through DEBUG
        levels = [50, 40, 30, 20, 10]
        colours = [red, red, yellow, blue, green]
        for level, color in zip(levels, colours):
            logging.addLevelName(level, "".join([color, logging.getLevelName(level), off]))

