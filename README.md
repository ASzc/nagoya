# nagoya - Koji in Docker containers

Nagoya is a collection of tools to build and use systems of [Docker](https://www.docker.com/) images, with a focus on the requirements of [Koji](https://fedorahosted.org/koji/).

## Usage

### moromi

Example configuration:

```ini
[DEFAULT]
from = centos:centos6
maintainer = M. A. Intainer <maintainer@example.com>
libs = {cfgdir}/util in /tmp
       {secdir}/custom.py at /tmp/blah.py

[some-volume-image]
volumes = /var/lib/example
runs = {secdir}/setup.py in /tmp

[some-regular-image]
runs = {secdir}/setup.py in /tmp
entrypoint = {secdir}/entrypoint.py in /tmp
exposes = 80
          443
```

Example command:

    ./moromi.py -c example.cfg build some-volume-image some-regular-image

For more information, run `./moromi.py -h` or see the [Overview section](#building-images-with-moromi).

### toji

Example configuration:

```ini
[volcontainer]
detach = no
run_once = yes
image = some-volume-image:latest

[regcontainer]
image = some-regular-image:latest
volumes_from = volcontainer:rw
```

Example command:

    ./toji.py init

For more information, run `./toji.py -h` or see the [Overview section](#container-systems-with-toji).

### Detailed Example

A full set of files for Koji is available in the `cfg` directory.

## Overview

### Dependencies

Nagoya will run on Python 2.7 or Python 3.3 and above.

TODO deps.py

If you have [argcomplete](https://github.com/kislyuk/argcomplete) configured, tab completion will be available for both `moromi` and `toji`.

### Building Images With `moromi`

#### Standard images

If you can easily write a `Dockerfile` to build an image, then you only need the standard build functionality. It includes some features for common files/libraries. TODO

#### Images from a temporary container system

The best way to ensure minimal lead time when initalising containers is to include as much of the application as possible in the images. While many customisations can easily be accomplished through normal image layering, some configuration is best done against a live system. Nagoya allows you to construct a temporary system of containers, execute commands against it, then save the changes into new images.

Many container systems use volumes to store data. Unfortunately, Docker's [`commit`](https://docs.docker.com/reference/commandline/cli/#commit) command doesn't include volume data in the saved image. Nagoya offers "persist" as an alternative that works around the `commit` command's limitations. Persisting a container will cause a child image to be built from the container's image, with the contents of the volumes added. Note that changes outside of the volumes won't be saved, but this shouldn't be an issue if you use [data volume containers](https://docs.docker.com/userguide/dockervolumes/#creating-and-mounting-a-data-volume-container).

#### Configuration file format

The basic format of the moromi configation file is [INI](https://en.wikipedia.org/wiki/INI_file), as understood by Python's default [configparser](https://docs.python.org/3.3/library/configparser.html). In addition, some variables are available to be substituted in option values: TODO table/list of available variables.

Options with pluralised key names allow to to specify multiple values, seperated by newlines.

### Container Systems With `toji`

TODO Automatic docker-level (links, volumes, etc.) dependency order via topological sorting. If a service running inside a container needs a service in another container, then that level of guarantee is not provided by toji.

#### TODO

#### Callbacks

#### Configuration file format

### Other Topics

#### Name

[Koji](https://en.wikipedia.org/wiki/Aspergillus_oryzae) is the start of a Japanese beverage. A [docker](https://en.wikipedia.org/wiki/Stevedore) works in a port. [Nagoya](https://en.wikipedia.org/wiki/Port_of_Nagoya) is a major port of Japan.
