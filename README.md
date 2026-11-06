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

Commit the package version and exactly one authored note matching the selected tag, `notes/*_release_vX.Y.Z.md`. The tag's version must match the package version. Older release notes may remain; the checkout must be clean.

By default, `publish/prepare` creates **`release-artifacts/vX.Y.Z/` in this repository**. The parent and version directory are caller-owned, mode `0700`, excluded from Git and repository-check mounts. A previously prepared or nonempty directory is never overwritten. Acquire the pinned build dependency, then prepare:

```sh
make packages/linux-idmap/download DOCKER_CONTEXT=generic WHEELHOUSE=/path/to/wheelhouse NETWORK_INTERFACE=system
make publish/prepare DOCKER_CONTEXT=generic TAG=vX.Y.Z WHEELHOUSE=/path/to/wheelhouse
```

Review `release-artifacts/vX.Y.Z/artifacts/`, the build/test logs and the authored note. After installing `gh` and `jq` and configuring GitHub access, publish the **same reviewed directory** without rebuilding it:

```sh
make publish/release TAG=vX.Y.Z
```

Both commands accept an explicit override: `OUTPUT=/canonical/empty/private/directory` for preparation, or `ARTIFACTS=/canonical/reviewed/private/directory` for publication. Explicit paths must already exist, be caller-owned and mode `0700`. The default directory must be absent or empty for preparation and present for publication. Publication verifies committed source, qualification hashes and downloaded draft assets byte-for-byte before releasing them. Preserve local artifacts until publication is confirmed; afterward they can be removed manually.

The build dependency advisory snapshot in `requirements/linux-idmap-build-advisories.json` records an exact-version PyPI check at its stated time; it is not a current or complete security audit.
