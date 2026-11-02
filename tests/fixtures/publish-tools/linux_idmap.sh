#!/usr/bin/env bash
# Stand in for the package owner; exercise the host publication workflow.
set -euo pipefail
printf 'package %s\n' "$*" >> "$PUBLISH_TEST_TRACE"
[[ $# == 1 ]] || exit 97
if [[ $1 == build ]]; then
    artifacts=$OUTPUT_INPUT
    printf 'qualified wheel\n' > "$artifacts/linux_idmap-0.2.0-py3-none-any.whl"
    printf 'qualified source\n' > "$artifacts/linux_idmap-0.2.0.tar.gz"
    printf 'closed lock\n' > "$artifacts/linux_idmap-0.2.0-install.lock"
    printf '{"source_revision":"%040d"}\n' 1 > "$artifacts/linux_idmap-0.2.0-release.json"
    printf '{}\n' > "$artifacts/linux_idmap-0.2.0-sha256.json"
elif [[ $1 == package ]]; then
    for file in "$ARTIFACTS_INPUT/"*; do
        printf 'QUALIFIED_SHA256 %s %s\n' "$(sha256sum "$file" | cut -d ' ' -f1)" "${file##*/}"
    done
else
    exit 97
fi
