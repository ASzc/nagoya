#!/usr/bin/env python2

import util.cleanup as cleanup
import util.system as system
import util.cfg as cfg
import util.cred as cred
import util.openssl as openssl
import util.remote as remote
from util.log import log
import sys
import subprocess
import os

kojihub_name = "koji"
remote.require_container(kojihub_name)

koji_ca = openssl.CA(cred.ca_key, cred.ca_crt, cred.ca_serial)
builder_name = system.hostname()
builder_user = cred.make_user(builder_name)
if not os.path.exists(builder_user.key):
    log.info("Creating builder credentials")
    openssl.make_user_certificate(builder_user, koji_ca)

    log.info("Configure Koji Builder")
    with cfg.mod_ini("/etc/kojid/kojid.conf") as i:
        i.kojid.cert = builder_user.pem
else:
    log.info("Builder credentials already exist")

def shutdown(*args):
    log.info("Stopping")
    log.info("Attempting to disable host {0}".format(builder_name))
    subprocess.call(["koji", "-d", "disable-host", builder_name])

cleanup.register_excepthook(shutdown)
cleanup.register_sig_handler(shutdown)

remote.wait_if_not_up(kojihub_name, 80)

log.info("Configuring host data on kojihub")
# subprocess.check_output doesn't exist in RHEL 6's Python (v2.6)
cmd = ["koji", "-d", "add-host", builder_name, "i386", "x86_64"]
process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
output, unused_err = process.communicate()
retcode = process.poll()
if retcode == 0:
    log.info("Added new host {0}".format(builder_name))
    host_is_new = True
elif retcode == 1 and "is already in the database" in output:
    log.info("Host {0} already is configured".format(builder_name))
    host_is_new = False
else:
    raise subprocess.CalledProcessError(retcode, cmd)

if host_is_new:
    log.info("Configuring new host {0}".format(builder_name))
    subprocess.check_call(["koji", "-d", "add-host-to-channel", builder_name, "createrepo"])
    subprocess.check_call(["koji", "-d", "edit-host", "--capacity", "10", builder_name])
else:
    log.info("Enabling existing host {0}".format(builder_name))
    subprocess.check_call(["koji", "-d", "enable-host", builder_name])

log.info("Calling kojid")
subprocess.check_call(["kojid", "--fg", "--verbose", "--force-lock"])
