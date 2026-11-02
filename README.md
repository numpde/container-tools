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

The [integration patches](integrations/linux-idmap/) are historical candidate adaptations for NMRPeak and NMRNet. Their pinned instructions refer to the original nmr-provider-tools repository; the [design note](notes/028_provider_deploy_design_20261031.txt) records their original context and qualification limits.
