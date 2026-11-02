#!/usr/bin/env bash
set -euo pipefail
python3 - "$@" <<'PY'
"""Verify an extracted archive against Git's committed blobs and modes."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys


def verify(root: Path, revision: str, archive: Path, paths: list[str]) -> None:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(root), *args])

    algorithm = git("rev-parse", "--show-object-format").strip().decode("ascii")
    entries = git("ls-tree", "-rz", "--full-tree", revision, "--", *paths)
    expected = set()
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split(b" ")
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise ValueError(f"Unsupported committed source entry: {os.fsdecode(name)!r}")
        relative = Path(os.fsdecode(name))
        expected.add(relative)
        target = archive / relative
        if target.is_symlink() or not target.is_file():
            raise ValueError(f"Committed source missing from archive: {relative}")
        data = target.read_bytes()
        digest = hashlib.new(algorithm, b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        executable = bool(target.stat().st_mode & 0o111)
        if digest.encode() != oid or executable != (mode == b"100755"):
            raise ValueError(f"Archive differs from committed source: {relative}")
    actual = {path.relative_to(archive) for path in archive.rglob("*") if not path.is_dir() or path.is_symlink()}
    if actual != expected:
        raise ValueError("Archive contains entries outside the committed source inventory")


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4:])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f"Cannot verify committed source archive: {error}")

PY
