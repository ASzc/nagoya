import subprocess
import os
import binascii
import platform
import socket
import util.demote
from util.log import log

def service(name, target):
    log.debug("Service {0} to target {1}".format(name, target))
    subprocess.check_call(["service", name, target])

def chkconfig(name, state):
    log.debug("Service {0} to startup state {1}".format(name, state))
    subprocess.check_call(["chkconfig", name, target])

def add_system_user(username):
    log.debug("Adding system user: {0}".format(username))
    subprocess.check_call(["useradd", "-r", username])

def run_as(username, cmd):
    log.debug("Calling {0} as user {1}".format(username, cmd))
    subprocess.check_call(cmd, preexec_fn=util.demote.to_username(username))

def random_secret():
    return binascii.b2a_hex(os.urandom(30)).decode("UTF-8")

def hostname():
    return platform.node()

def host_ipv4_address():
    return socket.gethostbyname(os.environ["HOSTNAME"])
