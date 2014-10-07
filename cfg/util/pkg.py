import subprocess
import contextlib
import glob
import os
import shutil
from util.log import log
import yum
try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen

def install(packages):
    if isinstance(packages, list):
        log.debug("Installing packages: {0}".format(packages))
        package_list = packages
    else:
        log.debug("Installing package: {0}".format(packages))
        package_list = [packages]

    subprocess.check_call(["yum", "-y", "install"] + package_list)

def clean():
    log.debug("Cleaning all")
    subprocess.check_call(["yum", "clean", "all"])

def update():
    log.debug("Updating all")
    subprocess.check_call(["yum", "-y", "update"])

@contextlib.contextmanager
def fetch_rpm_file(package, filepath):
    log.debug("Getting file {0} from rpm {1}".format(os.path.basename(filepath), package))
    extract_dir = "/tmp/" + package
    rpm_path = "/tmp/" + package + ".rpm"

    log.debug("Downloading")
    download_package(package, rpm_path)
    log.debug("Extracting")
    os.makedirs(extract_dir)

    # Run rpm2cpio into cpio. There is apparently no better way to do this.
    rpm2cpio_cmd = ["rpm2cpio", rpm_path]
    cpio_cmd = ["cpio", "-id"]
    rpm2cpio = subprocess.Popen(rpm2cpio_cmd, stdout=subprocess.PIPE)
    cpio = subprocess.Popen(cpio_cmd, cwd=extract_dir, stdin=rpm2cpio.stdout)
    rpm2cpio.stdout.close() # Allows rpm2cpio to exit when cpio does
    for p,cmd in [(rpm2cpio, rpm2cpio_cmd), (cpio, cpio_cmd)]:
        code = p.wait()
        if not code == 0:
            raise CalledProcessError(code, cmd)

    extracted_paths = glob.glob(extract_dir + "/" + filepath)
    if len(extracted_paths) > 1:
        log.debug("filepath glob matched more than one file: {0}".format(extracted_paths))

    yield extracted_paths[0]

    log.debug("Removing temp files")
    shutil.rmtree(extract_dir)
    os.remove(rpm_path)

def _download(url, file_path):
    log.debug("Downloading URL {0} to file {1}".format(url, file_path))
    # Python 2 urlopen is not closeable
    response = urlopen(url)
    with open(file_path, "wb") as out_file:
        shutil.copyfileobj(response, out_file)

def download_package(name, dest_file):
    yb = yum.YumBase()
    # YumBase will now load its stuff, which will output annoying startup messages I can't seem to suppress
    pkg = yb.pkgSack.returnNewestByName(name=name)[0]
    pkg_url = pkg._remote_url()
    log.debug("Found URL {0} for package {1}".format(pkg_url, name))
    _download(pkg_url, dest_file)
