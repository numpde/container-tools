override SHELL := bash
override .SHELLFLAGS := -eu -o pipefail -c
override .DEFAULT_GOAL := help

unexport DOCKER_CONTEXT
unexport DOCKER_CONTEXT_INPUT
unexport DOCKER_CONTEXT_INPUT_ORIGIN
unexport NMR_SELECTED_DOCKER_ENDPOINT
override export DOCKER_CONTEXT_INPUT_ORIGIN := $(origin DOCKER_CONTEXT)
ifeq ($(origin DOCKER_CONTEXT),command line)
override DOCKER_CONTEXT_INPUT := $(value DOCKER_CONTEXT)
export DOCKER_CONTEXT_INPUT
endif

# Select once for every Docker goal in this invocation. Help
# uses no Docker; child processes inherit the captured endpoint.
ifneq ($(strip $(filter-out help,$(MAKECMDGOALS))),)
ifeq ($(origin DOCKER_CONTEXT),command line)
docker_context_quote = '$(subst ','"'"',$(1))'
override export NMR_SELECTED_DOCKER_ENDPOINT := $(shell env -u NMR_SELECTED_DOCKER_ENDPOINT -u DOCKER_CONTEXT_INPUT -u DOCKER_CONTEXT_INPUT_ORIGIN DOCKER_CONTEXT_INPUT_ORIGIN='command line' DOCKER_CONTEXT_INPUT=$(call docker_context_quote,$(value DOCKER_CONTEXT)) bash tools/docker_context.sh --endpoint)
else
override export NMR_SELECTED_DOCKER_ENDPOINT := $(shell env -u NMR_SELECTED_DOCKER_ENDPOINT -u DOCKER_CONTEXT_INPUT -u DOCKER_CONTEXT_INPUT_ORIGIN bash tools/docker_context.sh --endpoint)
endif
ifeq ($(strip $(NMR_SELECTED_DOCKER_ENDPOINT)),)
$(error Select a local Docker context for this operation)
endif
endif

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

.PHONY: help tests tests/repository tests/repository/quality tests/repository/runtime tests/repository/command tests/repository/provisioning
.PHONY: checks/base-image/download checks/dependencies/download checks/dependencies/check checks/image/build checks/prepare tests/unit/linux-idmap

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
	  'make checks/prepare WHEELHOUSE=... NETWORK_INTERFACE=... Prepare the checker.'

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

tests: tests/repository tests/unit/linux-idmap

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

