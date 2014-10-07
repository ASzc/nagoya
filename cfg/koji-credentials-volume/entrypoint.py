#!/usr/bin/env python2

import util.cred as cred
from util.log import log
import util.openssl as openssl

log.info("Creating CA credentials")
koji_ca = openssl.CA(cred.ca_key, cred.ca_crt, cred.ca_serial)

log.info("Creating user credentials")
for n,u in cred.user.items():
    openssl.make_user_certificate(u, koji_ca)

log.info("Done")
