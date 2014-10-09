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

import tempfile
import shutil
import logging
import os
import stat

logger = logging.getLogger("nagoya.temp")

class RelativePathError(Exception):
    pass

class FileTypeError(Exception):
    pass

class TempDirectory(object):
    """
    Something roughly similar to Python 3's tempfile.TemporaryDirectory, plus
    an include method for files and directories.
    """

    def __init__(self, suffix="", prefix=tempfile.template, dir=None):
        self._closed = False
        self.name = None
        self.name = tempfile.mkdtemp(suffix, prefix, dir)

    def __repr__(self):
        return "<{0} {1!r}>".format(self.__class__.__name__, self.name)

    def __enter__(self):
        # Returns self instead of self.name
        return self

    def cleanup(self):
        if self.name is not None and not self._closed:
            shutil.rmtree(self.name)
            self._closed = True

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def include(self, source_path, temp_rel_path, executable=False):
        if ".." in temp_rel_path:
            raise RelativePathError("Relative path '{temp_rel_path}' contains ..".format(**locals()))

        temp_abs_path = os.path.join(self.name, temp_rel_path.lstrip("/"))

        def make_parents(path):
            dirname = os.path.dirname(path)
            # Doing this without catching exceptions since Python 2 doesn't throw OS-independent exceptions for os module functions
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        if os.path.isfile(source_path):
            logger.debug("Resource {source_path} is a file".format(**locals()))
            make_parents(temp_abs_path)
            shutil.copyfile(source_path, temp_abs_path)
        elif os.path.isdir(source_path):
            logger.debug("Resource {source_path} is a directory".format(**locals()))
            make_parents(temp_abs_path)
            shutil.copytree(source_path, temp_abs_path)
        else:
            raise FileTypeError("Resource {source_path} is not a directory or a file".format(**locals()))

        if executable:
            logger.debug("Setting copy of resource {source_path} executable".format(**locals()))
            # equiv. of chmod +x
            mode = os.stat(temp_abs_path).st_mode
            os.chmod(temp_abs_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
