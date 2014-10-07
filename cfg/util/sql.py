import tempfile
import subprocess
import util.demote
import contextlib
from util.log import log
import os
import multiprocessing

def _exec_with_tempfile_as(user, cmd, contents):
    # warning: sets uid/gid of current process
    util.demote.to_username(user)()
    # Have to create tempfile as user because of mkstemp
    with tempfile.NamedTemporaryFile("w") as f:
        f.write(contents)
        f.flush()
        cmd.append(f.name)
        subprocess.check_call(cmd)

@contextlib.contextmanager
def commands(user, database):
    sql_commands = []
    yield sql_commands
    sql = ";\n".join(sql_commands)

    log.debug("Running {0} sql commands as user {1} against database {2}".format(len(sql_commands), user, database))
    cmd = ["psql", database, user, "-f"]
    p = multiprocessing.Process(target=_exec_with_tempfile_as, args=(user, cmd, sql))
    p.start()
    p.join()
    if not p.exitcode == 0:
        raise Exception("Running sql commands failed, see above trace")

def exec_file(user, database, path):
    cmd = ["psql", database, user, "-f", path]
    log.debug("Running sql file {0} as user {1} against database {2}".format(path, user, database))
    subprocess.check_call(cmd, preexec_fn=util.demote.to_username(user))

def init_db():
    new_env = os.environ.copy()
    new_env["PGDATA"] = "/var/lib/pgsql/data"
    log.debug("Calling initdb as user postgres with PGDATA={0}".format(new_env["PGDATA"]))
    subprocess.check_call(["initdb"], env=new_env, preexec_fn=util.demote.to_username("postgres"))
