#!/usr/bin/env python2

# References:
# https://fedoraproject.org/wiki/Koji/ServerHowTo
# https://github.com/sbadakhc/kojak/blob/master/scripts/install/install

import util.cfg as cfg
import util.system as system
import util.pkg as pkg
import util.aconf as aconf
import util.cred as cred
from util.log import log
from os.path import basename
from os import rename

#
# Setup
#

log.info("General update")
pkg.clean()
pkg.update()

log.info("Install EPEL")
pkg.install("https://dl.fedoraproject.org/pub/epel/6/x86_64/epel-release-6-8.noarch.rpm")

log.info("Modify initscripts' checkpid")
# checkpid doesn't handle defunct processes, alter so it does
with cfg.mod_text("/etc/init.d/functions") as f:
    checkpid_start = f.index("checkpid() {\n")
    checkpid_end = f.index("}\n", checkpid_start)
    test_index = f.index('\t\t[ -d "/proc/$i" ] && return 0\n', checkpid_start, checkpid_end)
    f[test_index] = '\t\t[ -e "/proc/$i/exe" ] && return 0\n'

# Note that the /etc/hosts file is not writable in docker images/containers
# Use this instead: https://docs.docker.com/userguide/dockerlinks/#container-linking

#
# Koji-Hub
#

log.info("Install Koji-Hub")
pkg.install(["koji-hub", "httpd", "mod_ssl", "mod_wsgi"])

log.info("Configure Koji-Hub")
with cfg.mod_aconf("/etc/httpd/conf.d/kojihub.conf") as a:
    s = aconf.SectionNode()
    s.name = "Location"
    argument = aconf.Argument()
    argument.text = "/kojihub/ssllogin"
    s.arguments.append(argument)
    s["SSLVerifyClient"] = "require"
    s["SSLVerifyDepth"] = "10"
    s["SSLOptions"] = "+StdEnvVars"
    a.nodes.append(s)
    found_section = False
    for d in a.nodes_with_name("Directory"):
        if isinstance(d, aconf.SectionNode) and d.arguments[0].text == "/mnt/koji":
            d["Options"] = ["Indexes", "FollowSymLinks"]
            found_section = True
            break
    if not found_section:
        raise Exception("Did not find section")

with cfg.mod_aconf("/etc/httpd/conf.d/ssl.conf") as a:
    vh = a["VirtualHost"]
    vh["SSLCertificateFile"] = [cred.user["kojihub"].crt]
    vh["SSLCertificateKeyFile"] = [cred.user["kojihub"].key]
    vh["SSLCertificateChainFile"] = [cred.ca_crt]
    vh["SSLCACertificateFile"] = [cred.ca_crt]
    vh["SSLVerifyClient"] = ["require"]
    vh["SSLVerifyDepth"] = ["10"]

koji_url = dict()
koji_url["web"] = "http://localhost/koji"
koji_url["top"] = "http://localhost/kojifiles"
koji_url["hub"] = "http://localhost/kojihub"

with cfg.mod_ini("/etc/koji-hub/hub.conf") as ini:
    ini.hub.DBHost = "kojidatabase"
    ini.hub.DNUsernameComponent = "CN"
    ini.hub.ProxyDNs = str(cred.user["kojiweb"].subject)
    ini.hub.KojiWebURL = koji_url["web"]
    ini.hub.DisableNotifications = True
    ini.hub.EnableMaven = True

# /mnt/koji filesystem is handled by docker as a docker volume

# selinux is disabled in the official CentOS docker images

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

#
# Koji-Web
#

log.info("Install Koji-Web")
pkg.install("koji-web")

log.info("Configure Koji-Web")

with cfg.mod_aconf("/etc/httpd/conf.d/kojiweb.conf") as a:
    s = aconf.SectionNode()
    s.name = "Location"
    argument = aconf.Argument()
    argument.text = "/koji/login"
    s.arguments.append(argument)
    s["SSLVerifyClient"] = ["require"]
    s["SSLVerifyDepth"] = ["10"]
    s["SSLOptions"] = ["+StdEnvVars"]
    a.nodes.append(s)

    # Serve some certificates from / so users can easily install them in their browsers
    for pki_file in [cred.ca_crt, cred.user["kojiadmin"].p12]:
        alias = aconf.DirectiveNode()
        alias.name = "Alias"
        for argtext in ["/" + basename(pki_file), pki_file]:
            argument = aconf.Argument()
            argument.text = argtext
            alias.arguments.append(argument)
        a.nodes.append(alias)

# /etc/httpd/conf.d/ssl.conf has required modifications done by koji-hub config

with cfg.mod_ini("/etc/kojiweb/web.conf") as i:
    i.web.KojiHubURL = koji_url["hub"]
    i.web.KojiFilesURL = koji_url["top"]
    i.web.WebCert = cred.user["kojiweb"].pem
    i.web.ClientCA = cred.ca_crt
    i.web.KojiHubCA = cred.ca_crt
    i.web.Secret = system.random_secret()

# filesystem configuration already done in /etc/httpd/conf.d/kojihub.conf

with cfg.mod_aconf("/etc/httpd/conf/httpd.conf") as a:
    a["ServerName"] = ["koji"]

#
# Kojira
#

log.info("Install Kojira")
pkg.install("koji-utils")

log.info("Configure Kojira")

# Kojira koji user added in database image

with cfg.mod_ini("/etc/kojira/kojira.conf") as i:
    i.kojira.server = koji_url["hub"]
    i.kojira.cert = cred.user["kojira"].pem
    i.kojira.ca = cred.ca_crt
    i.kojira.serverca = cred.ca_crt

kojira_service = "kojira"
#system.service(kojira_service, "start")
#system.chkconfig(kojira_service, "on")

pkg.clean()
