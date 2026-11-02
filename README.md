# Container tools

This repository maintains [linux-idmap](packages/linux-idmap/README.md), a host-side Python package for Linux UID/GID maps and local Docker identity probes.

## Development

The package requires Linux and Python 3.11 or newer. Its README describes installation, usage, and direct host-side tests. The repository checker and package test lane run in a restricted container on Linux/amd64.

Select a local Docker context for every Docker operation using `DOCKER_CONTEXT=<name>` or choose one interactively. Run on the target host so bind mounts and network interfaces refer to that host. On a new host, acquire the pinned base image, then prepare the checker with an explicit wheelhouse and network interface. Replace `generic` below with the local context name:

```sh
make checks/base-image/download DOCKER_CONTEXT=generic
make checks/prepare DOCKER_CONTEXT=generic WHEELHOUSE=/path/to/wheelhouse NETWORK_INTERFACE=system
make tests DOCKER_CONTEXT=generic
```

`system` uses the selected engine’s network for dependency acquisition. Rootless engines may use a separate network namespace, so host routing and interface availability depend on the engine configuration. Preparation verifies pinned inputs and builds offline. Normal checks run offline with read-only source mounts. Run `make help` for the available commands.

## Release

Commit the package version and exactly one authored note matching the selected tag, `notes/*_release_vX.Y.Z.md`. The tag's version must match the package version. Older release notes may remain; the entire checkout must be clean. Acquire the pinned build dependency, then create an empty, caller-owned mode 0700 output directory at a canonical absolute path:

```sh
make packages/linux-idmap/download DOCKER_CONTEXT=generic WHEELHOUSE=/path/to/wheelhouse NETWORK_INTERFACE=system
mkdir -m 700 /path/to/output
```

Prepare the release using that wheelhouse and output directory:

```sh
make publish/prepare DOCKER_CONTEXT=generic TAG=vX.Y.Z WHEELHOUSE=/path/to/wheelhouse OUTPUT=/path/to/output
```

Review the five artifacts, build and test logs, and release note in that directory. To publish the reviewed files, install `gh` and `jq` on the host, configure GitHub access, and run `make publish/release TAG=vX.Y.Z ARTIFACTS=/path/to/output`. Publication checks the committed source, note, and qualification hashes, uploads a draft, downloads its files for byte comparison, and then publishes it. It does not rebuild the package.

The build dependency advisory snapshot in `requirements/linux-idmap-build-advisories.json` records an exact-version PyPI check at its stated time; it is not a current or complete security audit.
