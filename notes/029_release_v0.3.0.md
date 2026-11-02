# linux-idmap 0.3.0

`linux-idmap` reads Linux UID/GID maps and translates identities between the
inside and outside coordinates of a map. It can also inspect the host-visible
maps of a local Docker image before deployment.

- Read UID and GID map rows for a process and translate IDs in either direction.
  Inverse translation refuses an ID covered by multiple ranges.
- Use `observe_host_process` for checked host-coordinate observations, or
  `probe_identity` to measure an already-local image on a selected Docker
  engine. The image probe returns maps only after confirming retirement of its
  container and the processes it observes.
- Use `linux-idmap-probe` to probe an image and obtain its maps or translate
  inside IDs from a shell. Inverse translation is available through the Python API.

The package requires Linux and Python 3.11 or newer and has no third-party
runtime dependencies. Image probing requires a local Unix Docker socket, Docker
CLI, readable host `/proc`, initial user and PID namespaces, and an already-local
image without declared volumes. The image must contain a Python interpreter
executable by the requested user. It does not pull images or change filesystem
permissions. An uncertain outcome returns no usable maps: reconcile the reported
engine, token, and container before retrying.

The Python and repository test suites have been exercised, including package
qualification on a rootless Docker engine. This qualification does not establish
image-probe behavior on the intended rootful and rootless engines and provider
images. NMRPeak and NMRNet adapter patches in this repository are
historical candidates, not released integrations.

Installation and usage are documented in the package README.
