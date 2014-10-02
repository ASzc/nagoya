try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

classifiers = [
    "Development Status :: 4 - Beta",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3.3",
    "Programming Language :: Python :: 3.4",
    "Operating System :: POSIX :: Linux",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
    "Topic :: Software Development :: Libraries",
    "Topic :: Utilities",
]

install_requires = [
    "docker-py==0.5.0",
    "toposort==1.1",
]

if sys.version_info[0] < 3:
    install_requires.append("futures>=2.2.0")

with open("nagoya/version.py", "r") as fp:
    exec(fp.read())

with open("README.md", "r") as fp:
    long_description = fp.read()

setup(
    name="nagoya",
    version=version,
    description="Koji in Docker containers",
    keywords = ["docker", "koji"],
    url="https://github.com/ASzc/nagoya",
    packages=["nagoya"],
    author="Alex Szczuczko",
    author_email="aszczucz@redhat.com",
    install_requires=install_requires,
    long_description=long_description,
    classifiers=classifiers,
)
