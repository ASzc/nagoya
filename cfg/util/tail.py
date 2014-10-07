import subprocess

def watch(paths):
    if isinstance(paths, str):
        paths = [paths]
    subprocess.check_call(["tail", "-F"] + paths)
