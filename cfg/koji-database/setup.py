#!/usr/bin/env python2

import util.cfg as cfg
import util.sql as sql
import util.system as system
import util.pkg as pkg
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
# Postgre SQL
#

log.info("Install PostgreSQL Server")
pkg.install("postgresql-server")
sql.init_db()

log.info("Modify PostgreSQL initscript")
with cfg.mod_text("/etc/init.d/postgresql") as p:
    # Can't write to /proc/self/oom_adj in docker, causes error message on start, so disable
    index = p.index("PG_OOM_ADJ=-17\n")
    p[index] = "PG_OOM_ADJ=\n"

log.info("Start PostgreSQL Server")
postgresql_service = "postgresql"
system.service(postgresql_service, "start")

log.info("Create koji user")
koji_user = "koji"
koji_db_name = "koji"
system.add_system_user(koji_user)

log.info("Setup PostgreSQL Koji DB")
postgres_user = "postgres"
system.run_as(postgres_user, ["createuser", "-SDR", koji_user])
system.run_as(postgres_user, ["createdb", "-O", koji_user, koji_db_name])
log.info("Download initial schema")
# CentOS Docker image seems to sliently nuke docs, rpm cache, etc., so get schema.sql manually
with pkg.fetch_rpm_file("koji", "usr/share/doc/koji-*/docs/schema.sql") as schema_sql:
    sql.exec_file(koji_user, koji_db_name, schema_sql)

log.info("Configure PostgreSQL Auth")
with cfg.mod_text("/var/lib/pgsql/data/pg_hba.conf") as pg_hba:
    insert_index = pg_hba.index("# TYPE  DATABASE    USER        CIDR-ADDRESS          METHOD\n") + 1
    pg_hba.insert(insert_index, "host  all  all  0.0.0.0/0  trust\n")

with cfg.mod_text("/var/lib/pgsql/data/postgresql.conf") as c:
    insert_index = c.index("# - Connection Settings -\n") + 1
    c.insert(insert_index, "listen_addresses = '*'\n")

#system.service(postgresql_service, "restart")

with sql.commands(koji_user, koji_db_name) as s:
    log.info("Add Koji users into database")
    # Admin with SSL certificate authentication
    s.append("insert into users (name, status, usertype) values ('kojiadmin', 0, 0)")
    # Grant admin permission
    s.append("insert into user_perms (user_id, perm_id, creator_id) values (1, 1, 1)")

    log.info("Add Kojira user into database")
    # User with SSL certificate authentication
    s.append("insert into users (name, status, usertype) values ('kojira', 0, 0)")
    # Grant repo permission
    s.append("insert into user_perms (user_id, perm_id, creator_id) values (2, 3, 1)")

system.service(postgresql_service, "stop")
pkg.clean()
