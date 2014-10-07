#!/usr/bin/env python2

import util.cred as cred
import os
from util.log import log

log.info("Creating Koji shared volume")
subdirs = ["/mnt/koji/" + sub for sub in "packages", "repos", "work", "scratch"]
for subdir in subdirs:
    os.makedirs(subdir)

# Should be standard for EL6, as set by httpd package
apache_uid = 48
apache_gid = 48
# Set owner to apache:apache
for subdir in subdirs:
    os.chown(subdir, apache_uid, apache_gid)

log.info("Done")
