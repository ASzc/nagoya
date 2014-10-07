import collections

UserCred = collections.namedtuple("UserCred", ["key", "crt", "pem", "p12", "subject"])

class Subject(object):
    parts = ["C", "ST", "L", "O", "OU", "CN"]

    def __init__(self, CN, C="XX", ST="XX", L="XX", O="XX", OU="XX"):
        for part in self.parts:
            setattr(self, part, locals()[part])

    @classmethod
    def read_ns(cls, namespace):
        attrs = dict()
        for part in cls.parts:
            attrs[part] = getattr(namespace, part)
        return cls(**attrs)

    def __str__(self):
        return "/" + "/".join(map(lambda p: p + "=" + getattr(self, p), self.parts))

    def write_ns(self, namespace):
        for part in self.parts:
            setattr(namespace, part, getattr(self, part))

cred_root = "/etc/pki/koji"

ca_key = "/".join([cred_root, "koji_ca.key"])
ca_crt = "/".join([cred_root, "koji_ca.crt"])
ca_serial = "/".join([cred_root, "koji_ca.serial"])

def make_user(name):
    path_prefix = "/".join([cred_root, name])
    key = path_prefix + ".key"
    crt = path_prefix + ".crt"
    pem = path_prefix + ".pem"
    p12 = path_prefix + ".p12"
    subject = Subject(name)
    return UserCred(key, crt, pem, p12, subject)

user = dict()
for u in ["kojihub", "kojiadmin", "kojira", "kojiweb"]:
    user[u] = make_user(u)
