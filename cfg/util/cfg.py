from __future__ import print_function
import iniparse
import util.aconf as aconf
import contextlib
from util.log import log

@contextlib.contextmanager
def mod_ini(path):
    log.info("Editing {0}".format(path))
    with open(path, "r") as f:
        ini_data = iniparse.INIConfig(f)
    yield ini_data
    # Printing is the only way the library supports writing
    log.debug("Writing to path {0}".format(path))
    with open(path, "w") as f:
        print(ini_data, end="", file=f)

@contextlib.contextmanager
def mod_aconf(path):
    log.info("Editing {0}".format(path))
    a = aconf.ApacheHttpdConf()
    a.read_file(path)
    yield a
    log.debug("Writing to path {0}".format(path))
    a.write_file(path)

@contextlib.contextmanager
def mod_text(path):
    log.info("Editing {0}".format(path))
    with open(path, "r") as f:
        lines = list(f.readlines())
    yield lines
    log.debug("Writing to path {0}".format(path))
    with open(path, "w") as f:
        f.write("".join(lines))

class between:
    def __init__(self, start_line, end_line, func, inclusive=False):
        self.start_line = start_line
        self.end_line = end_line
        self.func = func
        self.inclusive = inclusive
        self.active = False

    def process(self, line):
        out = line

        if line == self.start_line:
            self.active = True
            if self.inclusive:
                out = self.func(line)
        elif line == self.end_line:
            self.active = False
            if self.inclusive:
                out = self.func(line)
        elif self.active:
            out = self.func(line)

        return out

@contextlib.contextmanager
def mod_between(path):
    mods = []
    yield mods
    log.debug("Applying {0} modifications to path {1}".format(len(mods), path))
    with mod_text(path) as lines:
        for lineno,line in enumerate(lines):
            for mod in mods:
                lines[lineno] = mod.process(line)
