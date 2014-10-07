import os
import OpenSSL
import util.cred as cred

filetype = OpenSSL.crypto.FILETYPE_PEM

class CA(object):
    def __init__(self, key_path, cert_path, serial_path):
        self.serial_path = serial_path
        key_exists = os.path.exists(key_path)
        cert_exists = os.path.exists(cert_path)
        serial_exists = os.path.exists(serial_path)
        if key_exists or cert_exists or serial_exists:
            if key_exists and cert_exists and serial_exists:
                with open(key_path, "r") as f:
                    self.key = OpenSSL.crypto.load_privatekey(filetype, f.read())
                with open(cert_path, "r") as f:
                    self.cert = OpenSSL.crypto.load_certificate(filetype, f.read())
                with open(serial_path, "r") as f:
                    self.serial = int(f.read())

                self.subject = cred.Subject.read_ns(self.cert.get_subject())
                self.name = self.subject.CN
            else:
                raise Exception("One of the CA files exists, but not all")
        else:
            self.name = os.path.splitext(os.path.basename(key_path))[0]
            self.subject = cred.Subject(self.name)
            self.key = create_key(key_path)
            req = create_certificate_request(self.key, self.subject)
            self.serial = 0
            self.cert = create_certificate(req, req, self.key, self.next_serial(), cert_path)

    def sign_cert_request(self, req, out_path):
        cert = create_certificate(req, self.cert, self.key, self.next_serial(), out_path)
        return cert

    def next_serial(self):
        self.serial += 1
        with open(self.serial_path, "w") as f:
            f.write(str(self.serial))
        return self.serial

def create_key(out_path):
    key = OpenSSL.crypto.PKey()
    key.generate_key(OpenSSL.crypto.TYPE_RSA, 2048)

    with open(out_path, "w") as f:
        f.write(OpenSSL.crypto.dump_privatekey(filetype, key))

    return key

def create_certificate_request(key, subject):
    req = OpenSSL.crypto.X509Req()
    subj = req.get_subject()
    subject.write_ns(subj)
    req.set_pubkey(key)
    req.sign(key, "sha256")

    return req

def create_certificate(req, issuer_cert, issuer_key, serial, out_path):
    now = 0
    ten_years = 315360000
    cert = OpenSSL.crypto.X509()
    cert.set_serial_number(serial)
    cert.gmtime_adj_notBefore(now)
    cert.gmtime_adj_notAfter(ten_years)
    cert.set_issuer(issuer_cert.get_subject())
    cert.set_subject(req.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(issuer_key, "sha256")

    with open(out_path, "w") as f:
        f.write(OpenSSL.crypto.dump_certificate(filetype, cert))

    return cert

def write_p12(key, cert, out_path):
    p12 = OpenSSL.crypto.PKCS12()
    p12.set_privatekey(key)
    p12.set_certificate(cert)
    with open(out_path, "wb") as f:
        f.write(p12.export(passphrase=""))

def combine_pem(key_path, crt_path, out_path):
    with open(key_path, "r") as k:
        key_data = k.read()
    with open(crt_path, "r") as c:
        crt_data = c.read()
    with open(out_path, "w") as o:
        o.write(crt_data)
        o.write(key_data)

def make_user_certificate(user, ca):
    key = create_key(user.key)
    req = create_certificate_request(key, user.subject)
    cert = ca.sign_cert_request(req, user.crt)
    write_p12(key, cert, user.p12)
    combine_pem(user.key, user.crt, user.pem)
