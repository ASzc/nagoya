#!/usr/bin/env python2

import util.cleanup as cleanup
import util.tail as tail
import util.system as system
import util.remote as remote
from util.log import log

import sys

kojidatabase_name = "kojidatabase"
remote.require_container(kojidatabase_name)
remote.wait_if_not_up(kojidatabase_name, 5432)

with cfg.mod_ini("/etc/kojiweb/web.conf") as i:
    i.web.KojiFilesURL = "http://{addr}/kojifiles".format(addr=system.host_ipv4_address())

services = ["httpd"]
if not "nokojira" in sys.argv:
    services.append("kojira")

def shutdown(*args):
    for service in reversed(services):
        log.info("Stopping {0}".format(service))
        system.service(service, "stop")

cleanup.register_excepthook(shutdown)
cleanup.register_sig_handler(shutdown)

for service in services:
    log.info("Starting {0}".format(service))
    system.service(service, "start")

log.info("Monitoring httpd log")
tail.watch("/var/log/httpd/error_log")
