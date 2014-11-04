#!/usr/bin/env python2

# References:
# https://fedoraproject.org/wiki/Koji/ServerHowTo
# https://github.com/sbadakhc/kojak/blob/master/scripts/install/install

import util.cfg as cfg
import util.pkg as pkg
import util.cred as cred
from util.log import log

#
# Setup
#

log.info("General update")
pkg.clean()
pkg.update()

log.info("Install EPEL")
pkg.install("https://dl.fedoraproject.org/pub/epel/6/x86_64/epel-release-6-8.noarch.rpm")

#
# Kojid (Koji Builder)
#

log.info("Install Koji Builder")
pkg.install("koji-builder")

koji_url = dict()
koji_url["web"] = "http://koji/koji"
koji_url["top"] = "http://koji/kojifiles"
koji_url["hub"] = "http://koji/kojihub"

log.info("Configure Koji Builder")
with cfg.mod_ini("/etc/kojid/kojid.conf") as i:
    i.kojid.sleeptime = 2
    i.kojid.maxjobs = 20
    i.kojid.server = koji_url["hub"]
    i.kojid.topurl = koji_url["top"]
#   i.kojid.cert is set at runtime
    i.kojid.ca = cred.ca_crt
    i.kojid.serverca = cred.ca_crt
    i.kojid.smtphost = "koji"
    i.kojid.from_addr = "Koji Build System <buildsys@kojibuilder>"

log.info("Modify mock to not mount vfs before yum is run")
with cfg.mod_text("/usr/lib/python2.6/site-packages/mockbuild/buildroot.py") as lines:
    i = lines.index("        self.mounts.mountall()\n")
    lines[i] = """
        if os.path.getsize(self.make_chroot_path("var", "log", "yum.log")) > 0:
            self.mounts.mountall()
"""

#
# Koji CLI
#

log.info("Configure Koji CLI")
with cfg.mod_ini("/etc/koji.conf") as i:
    i.koji.server = koji_url["hub"]
    i.koji.weburl = koji_url["web"]
    i.koji.topurl = koji_url["top"]
    i.koji.topdir = "/mnt/koji"
    i.koji.cert = cred.user["kojiadmin"].pem
    i.koji.ca = cred.ca_crt
    i.koji.serverca = cred.ca_crt

pkg.clean()
