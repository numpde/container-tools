# linux-idmap 0.3.1

Version 0.3.1 adds **host-to-container UID/GID projection to the
`linux-idmap-probe` command**. Version 0.3.0 already provided
`IdMap.translate_inverse()` in Python, alongside checked observation of a
local Docker container's UID/GID maps. This release exposes that existing
translation to shell consumers without requiring them to parse Linux maps or
manage a second Docker probe.

## Changes since 0.3.0

### Inverse projection from the CLI

Pass `--inverse` to interpret each `--uid` and `--gid` as an **outside (host)
ID** and return the corresponding **inside (container) ID**. Without this
switch, the command retains its existing inside-to-outside direction.

For example, to find which identities inside a selected local Docker engine
correspond to the host owner of a private bind mount:

```sh
linux-idmap-probe \
  --endpoint unix:///run/user/1000/docker.sock \
  --image approved-python:local \
  --interpreter /usr/local/bin/python3 \
  --user-uid 0 --user-gid 0 \
  --inverse --uid 1000 --gid 1000 --values
```

The endpoint, image and interpreter above are illustrative: select the actual
local Unix endpoint and an **already available** image with an executable
Python interpreter and no declared volumes. `--user-uid` and `--user-gid`
specify the temporary probe process's identity; `--uid` and `--gid` select
the IDs to translate. Do not assume the result will be `0:0` merely because
the engine is called rootless. Read the measured maps and use the returned
pair for the same engine and user-namespace policy.

UIDs and GIDs are translated independently, including when their maps differ.
Both options may be repeated, with duplicates and request order preserved.
In `--values` mode, successful output is a single line containing all
requested UIDs followed by all requested GIDs, separated by spaces. The JSON
mode retains its existing `mapped_uids` and `mapped_gids` fields.

### Failure, cancellation and lifecycle behavior

The new direction uses the same checked `probe_identity()` operation and
does **not** introduce another container lifecycle or mapping algorithm.
Results are returned only after the probe has confirmed retirement of its
container and observed processes. The probe's existing confinement remains:
no network, read-only root filesystem, dropped capabilities and
`no-new-privileges`. The command does not modify filesystem ownership,
permissions or ACLs and does not pull an image.

An outside ID that is absent from the relevant map, or covered ambiguously
by more than one range, is rejected. Projection is all-or-nothing: if any
requested UID or GID fails, no partial `--values` output is printed.
Failures in that mode emit structured JSON to stderr; the default mode
continues to emit structured JSON on stdout. The established exit-status
contract is unchanged:

- `0`: successful, fully projected and retired probe;
- `1`: settled operation or projection failure (including unmapped IDs);
- `2`: invalid arguments or policy before creation;
- `3`: unresolved probe resource/retirement outcome;
- `130`: cancellation.

A cancellation during inverse projection withholds success output and
restores the process's prior signal handlers. An unresolved retirement
outcome must be reconciled using the reported probe handle; the caller
must not treat its maps as usable.

## Compatibility and scope

This is an additive CLI feature. Existing commands without `--inverse`
continue to use forward translation. The public Python mapping and probe
APIs, ID-map representation, output field names, probe isolation policy
and default namespace selection are unchanged. No new runtime dependencies
were introduced. Existing Python consumers of `translate_inverse()` do
not need to change their calls.

Image probing still requires Linux, Python 3.11 or newer on the host, an
explicitly selected local Unix Docker endpoint, the Docker CLI, readable
host `/proc`, and observation from the initial user and PID namespaces.
The later workload must use the engine and namespace policy that were
probed. This release is a mapping/observation facility, not a general
filesystem-access grant or a claim of qualification for remote Docker or
VM-backed Docker mounts.

## Verification

The full `linux-idmap` unittest suite completed in GitHub Actions:
**244 tests executed; 242 passed and 2 skipped**. The two skips were
isolated-user-namespace setup cases: the hosted runner denied access to
`/proc/self/ns/user` after namespace creation (`EACCES`). These are explicit
fixture-environment limits, not passing observations. The suite otherwise
exercised the existing probe lifecycle, cleanup and failure behavior, plus
new cases for inverse JSON ordering, independent UID/GID maps, rootful and
rootless mapping examples, unmapped and ambiguous group IDs, cancellation,
and suppression of partial output.

The release's source changes are the CLI direction switch, its tests and
the documented fixture handling for restricted user-namespace hosts.
End-to-end qualification against a particular operator's rootless Docker
engine and private bind mounts remains a separate deployment check.

The [package documentation](../packages/linux-idmap/README.md) gives the
complete Python and CLI interfaces and the probe preconditions.
