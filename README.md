# nagoya - Koji in Docker containers

Nagoya is a collection of tools to build and use systems of [Docker](https://www.docker.com/) images, with a focus on the requirements of [Koji](https://fedorahosted.org/koji/).

## Usage

### `moromi`

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

### `toji`

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

Nagoya depends directly on `docker-py>=0.5.0` and `toposort>=1.1`, with some transitive dependencies. If you don't have them installed on your system:

* install them with `pip install` (note you have to run pip for each version of Python you want to use), or
* install them with your system package manager (if the correct versions are available), or
* run `./deps.py dl` to download local copies into the repo root.

If you have [argcomplete](https://github.com/kislyuk/argcomplete) configured, tab completion will be available for both `moromi` and `toji`.

### Configuration File Format

The basic format of the configation files is [INI](https://en.wikipedia.org/wiki/INI_file), as understood by Python's default [configparser](https://docs.python.org/3.3/library/configparser.html). In addition to the features that configparser provides, some extra variables are available to be substituted in option values:

Name | Value
---- | -----
`cfgdir` | The directory the configuration file is located in
`section` | The name of the current section
`secdir` | The subdirectory named `section` in `cfgdir`

Options with plural key names allow you to specify multiple values, separated by newlines.

## Building Images With `moromi`

### Standard images

Standard image builds use a normal Dockerfile build context on the backend, but some convenience features are provided to reduce code duplication. It's assumed that run/entrypoint commands always use files not already in the image to increase succinctness.

### Images from a temporary container system

The best way to ensure minimal lead time when initialising containers is to include as much of the application as possible in the images. While many customisations can easily be accomplished through normal image layering, some configuration is best done against a live system. Nagoya allows you to construct a temporary system of containers, execute commands against it, then save the changes into new images.

Many container systems use volumes to store data. Unfortunately, Docker's [`commit`](https://docs.docker.com/reference/commandline/cli/#commit) command doesn't include volume data in the saved image. Nagoya offers "persist" as an alternative that works around the `commit` command's limitations. Persisting a container will cause a child image to be built from the container's image, with the contents of the volumes added. Note that changes outside of the volumes won't be saved, but this shouldn't be an issue if you use [data volume containers](https://docs.docker.com/userguide/dockervolumes/#creating-and-mounting-a-data-volume-container).

**Note:** Docker host volumes currently don't work on systems with selinux when it is in enforcing mode. This breaks persist builds. Fix is pending in [Docker Pull #5910](https://github.com/docker/docker/pull/5910).

### Configuration

The names of the sections are what the built images will be tagged with after building.

Standard options:
Key | Value
--- | -----
From | Parent image
Maintainer | A name and email address
Runs | Files to execute on the container during the build. See [subsection](#resources)
Libs | Additional files/directories. See [subsection](#resources)
Exposes | Port numbers
Entrypoint | File to execute by default when a container starts

Container system options:
Key | Value
--- | -----
Commit | Commit the image if true. Boolean.
Entrypoint | Use a new entrypoint file. Mounts host volumes at the required paths in the container.
Libs | Same as the standard option, but mounts host volumes at the required paths in the container.
Volumes_From | See [subsection](#volumes_from)
Links | See [subsection](#links)

#### Resources

The Runs, Libs, and Entrypoint options take files/directories from the host filesystem and add them to the image. The first component of a line gives the complete host path to the source. The second component is either `at` or `in`. If `at`, then the third component must be the complete container path to copy the source to. If `in`, then the third component must be the path to the container directory to copy the source into.

#### Volumes_From

Volumes_From has some unique syntax to describe the temporary container. The first component of a line is the name of the image to create a container from. The second component is either `discard`, followed by the end of the line, or `persist to` followed by the destination image name.

#### Links

Links has some unique syntax to describe the temporary container. The first component of of a line in the name of the image to create a container from. The second component is `alias`, followed by the name of the hostname to use to represent the created container. The third component is either `discard` followed by the end of the line, or `commit to` followed by the destination image.

## Container Systems With `toji`

### Docker-level Dependencies

Dependencies between configured containers are found in the Volume_From and Link options. Commands will be executed against the group of containers with respect to this partial ordering, so that Docker doesn't produce errors.

Nagoya doesn't provide any guarantees for the ordering of dependencies inside the containers themselves. If a program running inside a container needs a program in another container, then the first program must wait for the second to be ready with its own polling or messaging system.

### Multithreading

To deliver the fastest execution time possible for the commands (particularly start), multithreading is used. Some commands on the Docker backend (like remove) use global locks, so they defeat the multithreading in the current version of Docker.

### Configuration

The names of the sections are what the containers will be named when created.

Valid options:
Key | Value
--- | -----
Image | The image to use
Detach | After starting the container, wait for it to finish if false. Boolean.
Run_Once | Ignore start commands if the container has been started previously if true. Boolean.
Working_Dir | Override the image's working directory
Entrypoint | Override the image's entrypoint
Volumes | Set volumes for the container not specified in the image
Volumes_From | Use volumes from other containers, with mode parameters
Links | Create a network link, with hostname alias
Callbacks | Execute additional functions on some events. See [section](#callbacks)

### Callbacks

Callbacks offer the ability to plug-in additional domain-specific functionality. You can register any function from any module to an event. The directory of the configuration file is added to the Python path, so you may place the plugin modules there. The function will be called with one parameter: the calling container object, as defined in `nagoya.dockerext.container`. Any exceptions thrown by the callbacks will not be caught, and will cause the program to exit.

Valid events:
Name | Description
---- | -----------
pre_init | Called before calling create
post_init | Called after calling start
pre_create | Called before executing docker command
post_create | Called after executing docker command
pre_start | Called before executing docker command
post_start | Called after the container exits if detach is false, otherwise after executing docker command.
pre_stop | Called before executing docker command, after checking if the container is running.
post_stop | Called after stopping or killing the container
pre_remove | Called before executing docker command
post_remove | Called after executing docker command

### API

`toji` also allows you to programmatically define container systems. For an example, look at how `moromi` uses it for temporary system image builds.

## Other Topics

### Name

[Koji](https://en.wikipedia.org/wiki/Aspergillus_oryzae) is the start of a Japanese beverage. A [docker](https://en.wikipedia.org/wiki/Stevedore) works in a port. [Nagoya](https://en.wikipedia.org/wiki/Port_of_Nagoya) is a major port of Japan.
