#!/usr/bin/env python2

import util.cleanup as cleanup
import util.tail as tail
import util.system as system
from util.log import log

services = ["postgresql"]

def shutdown(*args):
    for service in reversed(services):
        log.info("Stopping {0}".format(service))
        system.service(service, "stop")

cleanup.register_excepthook(shutdown)
cleanup.register_sig_handler(shutdown)

for service in services:
    log.info("Starting {0}".format(service))
    system.service(service, "start")

log.info("Monitoring postgresql log")
log_files = []
for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
    log_files.append("/var/lib/pgsql/data/pg_log/postgresql-{0}.log".format(day))
tail.watch(log_files)
