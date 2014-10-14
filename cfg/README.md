# Nagoya Koji Configuration

## Koji Components

```
             .---------.     .------------.
             |   UI    |     |  Database  |
 Browser---->| kojiweb |  .->| postgresql |
             .---------.--'  '------------'
             |   API   |
koji CLI---->| kojihub |<------------.
             '---------'             |
                  |                  |
         .--------'-----.            |
         |              |            |
      RW v           RO v            |
   .-----------..---------------.    |
   |  Topdir   ||  Credentials  |    |
   | /mnt/koji || /etc/pki/koji |    |
   '-----------''---------------'    |
      RO ^           RW ^      .----------.
         |              |      | Builders |
         '---------------------|  n-many  |
                               '----------'
```

## Images

This is a set of basic images that will create a functional (but mostly blank) instance of Koji when put together.

The images are built using `moromi`'s standard build capability. Extending the basic images can be accomplished either through normal Docker image layering (e.g. if you would like to override some code or configuration), or by using `moromi`'s commit/persist build with a temporary container system (e.g. if you would like to run some `koji` CLI commands then save the state).

The `util/` directory includes common Python modules that are used by the setup (build-time) and entrypoint (run-time) scripts. `kojicallbacks.py` contains some extra convenience features (updating a profile for `koji` CLI, printing addresses, etc.) for when `toji`'s CLI is used to control a system.

**Note:** Docker host volumes currently don't work on systems with selinux when it is in enforcing mode. This breaks the callback that copies the credentials onto the host. Fix is pending in [Docker Pull #5910](https://github.com/docker/docker/pull/5910).

### koji-hub

Runs HTTPD. Contains the `kojiweb` and `kojihub` components, which are served by a HTTP server alongside the contents of topdir. `kojira` (the repository generation scheduler) is also run by the entrypoint of this image.

Communicates to koji-database via TCP, waits for the database server to be active at startup.

### koji-database

Runs PostgreSQL, storing the database in-image without a volume.

### koji-builder

Runs `kojid`, which polls `kojihub` for tasks. When a koji-builder container is first started, it automatically generates credentials for itself and registers `kojihub`.

Communicates with koji-hub via XMLRPC over HTTPS, waits for the HTTP server to be active at startup.

### koji-credentials-volume

Data-only, only needs to be run once. Contains credential files (user/TLS/CA certificates, private keys, etc.) in a volume. The basic files are created when a koji-credentials-volume container is first started, so they are unique to each instance. Mounted at `/etc/pki/koji`.

### koji-top-volume

Data-only, only needs to be run once. Contains Koji's output files (packages, repos, etc.). Blank except for the simple directory structure in the base image. Mounted at `/mnt/koji`.
