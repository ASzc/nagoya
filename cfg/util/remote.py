from util.log import log
import socket
import time
import sys

def _attempt(hostname, port, timeout=2):
    s = socket.create_connection((hostname, port), timeout)
    s.close()

def is_up(hostname, port, timeout=2):
    log.debug("Trying connect to {0}:{1}".format(hostname, port))
    try:
        _attempt(hostname, port, timeout)
        log.debug("Connected to {0}:{1}".format(hostname, port))
        return True
    except socket.error as e:
        log.debug("Failed to connect to {0}:{1}".format(hostname, port))
        return False

def wait_up(hostname, port, attempts=10, timeout=2, wait=2):
    log.debug("Trying {0} times to connect to {1}:{2}".format(attempts, hostname, port))
    attempt = 0
    while True:
        attempt += 1
        try:
            _attempt(hostname, port, timeout)
            log.debug("Connected to {0}:{1}".format(hostname, port))
            break
        except socket.error as e:
            log.debug("Connection to {0}:{1} failed (attempt {2}/{3}): {4}".format(hostname, port, attempt, attempts, e))
            if attempt >= attempts:
                # Python 2 has wierd exception stuff, just re-raise rather than wrap in AttemptsExhausted exception
                raise
            time.sleep(wait)

def wait_if_not_up(hostname, port, attempts=10, timeout=2, wait=2):
    if not is_up(hostname, port, timeout):
        log.info("Waiting for {0} to be ready".format(hostname))
        wait_up(hostname, port, attempts, timeout, wait)

def address_in_hosts(hostname):
    with open("/etc/hosts", "r") as f:
        for line in f:
            line_parts = line.split()
            ip_address = line_parts[0]
            names = line_parts[1:]
            if hostname in names:
                return ip_address

def require_container(hostname, exit=True):
    address = address_in_hosts(hostname)
    if address is not None:
        log.info("Linked to container {0} at {1}".format(hostname, address))
        return True
    else:
        log.critical("Not linked to {0} container, exiting".format(hostname))
        if exit:
            sys.exit(11)
        else:
            return False
