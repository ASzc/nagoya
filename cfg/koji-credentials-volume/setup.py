#!/usr/bin/env python2

import util.pkg as pkg
from util.log import log

log.info("Installing dependency")
pkg.install("pyOpenSSL")
pkg.clean()
