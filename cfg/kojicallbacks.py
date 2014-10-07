from __future__ import print_function
import contextlib
import os
import uuid
import tarfile
import io
import logging

import iniparse

import nagoya.docker.container

logger = logging.getLogger("kojicallbacks")

#
# Helpers
#

@contextlib.contextmanager
def mod_ini(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            ini_data = iniparse.INIConfig(f)
    else:
        ini_data = iniparse.INIConfig()

    yield ini_data

    parent_dir = os.path.dirname(path)
    if not os.path.exists(parent_dir):
        # Python 2 doesn't have the exists_ok option
        os.makedirs(parent_dir)

    with open(path, "w") as f:
        print(ini_data, end="", file=f)

# TODO Might be able to do this easier with docker exec in 1.3.0 ?
# This won't work until Docker pull #5910 (selinux host volumes) is merged
# potential workaround would be to run tar command outputting to stdout, and attaching. Doesn't seem to work however.
def vol_copy(container, container_paths, target_host_dir):
    client = container.client

    extract_container = nagoya.docker.container.TempContainer("busybox")
    container_volume_dir = "/" + extract_container.random_name()
    extract_container.client = client
    extract_container.add_volume(target_host_dir, container_volume_dir)
    # TODO ^^^ host volumes working on Fedora depends on Docker#5910
    extract_container.add_volume_from(container.name, "ro")
    extract_container.entrypoint = ["cp", "-R"] + container_paths + [target_host_dir]
    try:
        extract_container.init()
        extract_container.wait()
    finally:
        extract_container.remove()

def get_network(container):
    return container.client.inspect_container(container.name)["NetworkSettings"]

#
# Callbacks
#

local_cred_dir = os.path.expanduser("~/.koji/dockerkoji-creds")

def update_config_profile(container):
    logger.info("Updating dockerkoji profile to use {container}".format(**locals()))

    address = get_network(container)["IPAddress"]

    config_path = os.path.expanduser("~/.koji/config")
    url_prefix = "http://{address}/".format(address=address)

    local_user_pem = os.path.join(local_cred_dir, "kojiadmin.pem")
    local_ca_cert = os.path.join(local_cred_dir, "koji_ca.crt")

    logger.debug("Modifying profile in {config_path}".format(**locals()))
    with mod_ini(config_path) as i:
        i.dockerkoji.server = url_prefix + "kojihub"
        i.dockerkoji.weburl = url_prefix + "koji"
        i.dockerkoji.topurl = url_prefix + "kojifiles"
        # It isn't possible to mount the container volumes on the host without root
        # Could be done if the container system used a host dir in place of koji-top-volume
        #i.dockerkoji.topdir = "/mnt/dockerkoji"
        i.dockerkoji.cert = local_user_pem
        i.dockerkoji.ca = local_ca_cert
        i.dockerkoji.serverca = local_ca_cert


def extract_credentials(container):
    container_cred_dir = "/etc/pki/koji/"
    # Can't extract a container's volume data with API copy command (yet).
    # Alternative is to use a temp container mounting a host volume
    # TODO enable when working
    #vol_copy(container, container_cred_dir, local_cred_dir)
    pass

def cleanup_credentials(container):
    pass

def show_network(container):
    net = get_network(container)
    address = net["IPAddress"]
    p = ", ".join(net["Ports"].keys())
    logger.info("Container {container} at Address: {address} Ports: {p}".format(**locals()))

def show_kojiweb_url(container):
    net = get_network(container)
    address = net["IPAddress"]
    logger.info("Container {container} kojiweb: http://{address}/koji".format(**locals()))
