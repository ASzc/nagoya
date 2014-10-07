import os
import pwd
from util.log import log

def to_id(user_uid, user_gid):
    def set_ids():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return set_ids

def get_user_ids(username):
    user_info = pwd.getpwnam(username)
    uid = user_info.pw_uid
    gid = user_info.pw_gid
    return (uid, gid)

# Run subprocess as a user, being already root
# Pass to preexec_fn argument
def to_username(username):
    uid, gid = get_user_ids(username)
    log.debug("Creating function to demote to user {0}, uid {1}, gid {2}".format(username, uid, gid))
    return to_id(uid, gid)
