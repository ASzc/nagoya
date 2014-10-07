#!/usr/bin/env python2

import util.cleanup as cleanup
import util.tail as tail
import util.system as system
import util.remote as remote
from util.log import log

kojidatabase_name = "kojidatabase"
remote.require_container(kojidatabase_name)
remote.wait_if_not_up(kojidatabase_name, 5432)

services = ["httpd", "kojira"]

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
