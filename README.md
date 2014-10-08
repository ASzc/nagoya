# nagoya - Koji in Docker containers

Nagoya is a collection of tools to build and use systems of [Docker](https://www.docker.com/) images, with a focus on the requirements of [Koji](https://fedorahosted.org/koji/).

## Usage

### moromi

Example configuration:

```ini

```

Example command:

```
./moromi.py build 
```

For more information, run `./moromi.py -h`

### toji

Example configuration:

```ini

```

Example command:

```
./toji.py init
```

For more information, run `./toji.py -h`

## Overview

### Building Images

#### Standard images

If you can easily write a `Dockerfile` to build an image, then you only need the standard build functionality. It includes some features for common files/libraries. TODO

#### Images from a temporary container system

The best way to ensure minimal lead time when initalising some containers is to include as much of the application as possible in the images. While many customisations can easily be accomplished through normal image layering, some configuration is best done against a live system. Nagoya allows you to construct a temporary system of containers, execute commands against it, then save the changes into new images.

Many container systems use volumes to store data. Unfortunately, Docker's [`commit`](https://docs.docker.com/reference/commandline/cli/#commit) command doesn't include volume data in the saved image. Nagoya offers "persist" as an alternative that works around the `commit` command's limitations. Persisting a container will cause a child image to be built from the container's image, with the contents of the volumes added. Note that changes outside of the volumes won't be saved, but this shouldn't be an issue if you use [data volume containers](https://docs.docker.com/userguide/dockervolumes/#creating-and-mounting-a-data-volume-container).

### Container Systems

## Overview

###

### Name

[Koji](https://en.wikipedia.org/wiki/Aspergillus_oryzae) is the start of a Japanese beverage. A [docker](https://en.wikipedia.org/wiki/Stevedore) works in a port. [Nagoya](https://en.wikipedia.org/wiki/Port_of_Nagoya) is a major port of Japan.
