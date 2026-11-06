override SHELL := bash
override .SHELLFLAGS := -eu -o pipefail -c
override .DEFAULT_GOAL := help

unexport DOCKER_CONTEXT
unexport DOCKER_CONTEXT_INPUT
unexport DOCKER_CONTEXT_INPUT_ORIGIN
unexport CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT
override export DOCKER_CONTEXT_INPUT_ORIGIN := $(origin DOCKER_CONTEXT)
ifeq ($(origin DOCKER_CONTEXT),command line)
override DOCKER_CONTEXT_INPUT := $(value DOCKER_CONTEXT)
export DOCKER_CONTEXT_INPUT
endif

# Docker context selection is owned by executing launchers, never Make parsing.
# Target completion, --print-data-base, --question and --dry-run must not open
# /dev/tty or inspect Docker. Runtime scripts share the selected endpoint with
# their children through CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT.

unexport NETWORK_INTERFACE
unexport NETWORK_INTERFACE_INPUT
unexport NETWORK_INTERFACE_INPUT_ORIGIN
override export NETWORK_INTERFACE_INPUT_ORIGIN := $(origin NETWORK_INTERFACE)
ifeq ($(origin NETWORK_INTERFACE),command line)
override NETWORK_INTERFACE_INPUT := $(value NETWORK_INTERFACE)
export NETWORK_INTERFACE_INPUT
endif
unexport WHEELHOUSE
unexport WHEELHOUSE_INPUT
unexport WHEELHOUSE_INPUT_ORIGIN
override export WHEELHOUSE_INPUT_ORIGIN := $(origin WHEELHOUSE)
ifeq ($(origin WHEELHOUSE),command line)
override WHEELHOUSE_INPUT := $(value WHEELHOUSE)
export WHEELHOUSE_INPUT
endif

unexport OUTPUT
unexport OUTPUT_INPUT
unexport OUTPUT_INPUT_ORIGIN
override export OUTPUT_INPUT_ORIGIN := $(origin OUTPUT)
ifeq ($(origin OUTPUT),command line)
override OUTPUT_INPUT := $(value OUTPUT)
export OUTPUT_INPUT
endif

unexport ARTIFACTS
unexport ARTIFACTS_INPUT
unexport ARTIFACTS_INPUT_ORIGIN
override export ARTIFACTS_INPUT_ORIGIN := $(origin ARTIFACTS)
ifeq ($(origin ARTIFACTS),command line)
override ARTIFACTS_INPUT := $(value ARTIFACTS)
export ARTIFACTS_INPUT
endif

unexport TAG
unexport TAG_INPUT
unexport TAG_INPUT_ORIGIN
override export TAG_INPUT_ORIGIN := $(origin TAG)
ifeq ($(origin TAG),command line)
override TAG_INPUT := $(value TAG)
export TAG_INPUT
endif

.PHONY: help tests tests/repository tests/repository/quality tests/repository/runtime tests/repository/command tests/repository/provisioning
.PHONY: checks/base-image/download checks/dependencies/download checks/dependencies/check checks/image/build checks/prepare tests/unit/linux-idmap
.PHONY: packages/linux-idmap/download packages/linux-idmap/check package/build tests/package publish/prepare publish/release

help:
	@printf '%s\n' \
	  'Docker commands require DOCKER_CONTEXT=<local context>, or an interactive selection.' \
	  'make help Show maintained commands.' \
	  'make tests Run repository checks and linux-idmap tests.' \
	  'make tests/repository Run repository checks offline.' \
	  'make tests/repository/quality Run repository quality checks offline.' \
	  'make tests/repository/provisioning Run checker provisioning fixtures offline.' \
	  'make tests/repository/runtime Inspect checker container grants.' \
	  'make tests/repository/command Print the checker command.' \
	  'make tests/unit/linux-idmap Run linux-idmap tests in the checker.' \
	  'make checks/base-image/download Acquire the pinned base through Docker.' \
	  'make checks/dependencies/download WHEELHOUSE=... NETWORK_INTERFACE=... Acquire checker dependencies.' \
	  'make checks/dependencies/check WHEELHOUSE=... Verify cached dependencies.' \
	  'make checks/image/build WHEELHOUSE=... Build the checker offline.' \
	  'make checks/prepare WHEELHOUSE=... NETWORK_INTERFACE=... Prepare the checker.' \
	  'make packages/linux-idmap/download WHEELHOUSE=... NETWORK_INTERFACE=... Acquire pinned build dependencies.' \
	  'make packages/linux-idmap/check WHEELHOUSE=... Verify pinned build dependencies offline.' \
	  'make package/build WHEELHOUSE=... OUTPUT=... Build committed source into an empty private directory.' \
	  'make tests/package WHEELHOUSE=... ARTIFACTS=... Qualify the exact release artifacts.' \
	  'make publish/prepare TAG=vX.Y.Z WHEELHOUSE=... [OUTPUT=...] Prepare in release-artifacts/<tag> by default.' \
	  'make publish/release TAG=vX.Y.Z [ARTIFACTS=...] Publish the reviewed release-artifacts/<tag> by default.'

tests/unit/linux-idmap:
	bash tools/repository.sh tests/unit/linux-idmap

checks/base-image/download:
	bash tools/checker.sh base-download

checks/dependencies/download:
	bash tools/checker.sh download

checks/dependencies/check:
	bash tools/checker.sh check

checks/image/build:
	bash tools/checker.sh build

checks/prepare:
	bash tools/checker.sh prepare

# One execution shell owns the selected engine for both test campaigns.
# Running independent goals separately remains two independent operations.
tests:
	@source tools/docker_context.sh; select_docker_context; \
	  bash tools/repository.sh tests/repository; \
	  bash tools/repository.sh tests/unit/linux-idmap

tests/repository:
	bash tools/repository.sh tests/repository

tests/repository/quality:
	bash tools/repository.sh tests/repository/quality

tests/repository/provisioning:
	bash tools/repository.sh tests/repository/provisioning

tests/repository/runtime:
	bash tools/repository.sh tests/repository/runtime

tests/repository/command:
	bash tools/repository.sh --print tests/repository

packages/linux-idmap/download:
	bash tools/linux_idmap.sh download

packages/linux-idmap/check:
	bash tools/linux_idmap.sh check

package/build:
	bash tools/linux_idmap.sh build

tests/package:
	bash tools/linux_idmap.sh package

publish/prepare:
	bash tools/publish.sh prepare

publish/release:
	bash tools/publish.sh release
