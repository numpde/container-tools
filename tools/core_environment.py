"""Build the shared wheel and install its closed hash lock without networking.

Consumers install the issued wheel; only this owner
builds it. A fixed ZIP epoch makes equal source bytes produce equal wheel bytes.
"""

from tools.container_guard import require_container

require_container()

import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path

from tools.artifacts import fsync_directory, regular_file
from tools.wheelhouse import capture, digest, requirements, select_wheels, wheel_inputs_from_report


def pip_command(python):
    return [sys.executable, "-I", "-m", "pip", "--isolated", "--python", str(python)]


def install_locked(python, lock, wheels, report):
    subprocess.run(
        [*pip_command(python), "install", "--ignore-installed", "--disable-pip-version-check",
         "--no-cache-dir", "--no-index", "--no-deps", "--only-binary=:all:", "--require-hashes",
         "--no-compile", "--report", str(report), "--find-links", str(wheels), "-r", str(lock)],
        check=True,
    )
    return wheel_inputs_from_report(lock, wheels, report)


def build_candidate(source, build_lock, pool, output):
    """Freeze the build dependency and produce the wheel, source archive and lock."""
    if output.is_symlink() or not output.is_dir() or any(output.iterdir()):
        raise ValueError("Cannot build linux-idmap: output must be a private empty directory.")
    with tempfile.TemporaryDirectory(prefix="idmap-build-") as temporary:
        scratch = Path(temporary)
        frozen = scratch / "build.lock"
        shutil.copyfile(build_lock, frozen)
        requirements(frozen)
        wheels = scratch / "build"
        wheels.mkdir()
        identities = capture(frozen, pool, wheels)
        package = scratch / "package"
        if source.is_symlink() or any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError("Cannot build linux-idmap: package inputs must not contain symlinks.")
        shutil.copytree(source, package)
        (package / ".gitignore").unlink(missing_ok=True)
        document = tomllib.loads((package / "pyproject.toml").read_text())
        project = document["project"]
        version = project["version"]
        build_dependencies = requirements(frozen)
        declared = [f"{name}=={version}" for name, version in build_dependencies]
        if document["build-system"] != {"requires": declared, "build-backend": "setuptools.build_meta"}:
            raise ValueError("Cannot build linux-idmap: declared build requirements differ from the locked builder.")
        if not (project["name"] == "linux-idmap" and project["dependencies"] == []
                and type(version) is str
                and re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version) is not None):
            raise ValueError("Cannot build linux-idmap: metadata must declare a stable version and no runtime dependencies.")
        builder = scratch / "builder"
        subprocess.run([sys.executable, "-I", "-m", "venv", "--without-pip", str(builder)], check=True)
        install_locked(builder / "bin/python", frozen, wheels, scratch / "build-install.json")
        subprocess.run(
            [*pip_command(builder / "bin/python"), "wheel", "--disable-pip-version-check", "--no-cache-dir",
             "--no-index", "--no-deps", "--no-build-isolation", "--wheel-dir", str(output), str(package)],
            env=os.environ | {"SOURCE_DATE_EPOCH": "315532800"}, check=True,
        )
        subprocess.run(
            [str(builder / "bin/python"), "-I", "-B", "-c",
             "import sys; from setuptools.build_meta import build_sdist; build_sdist(sys.argv[1])", str(output)],
            cwd=package, env=os.environ | {"SOURCE_DATE_EPOCH": "315532800"}, check=True,
        )
        wheel = output / f"linux_idmap-{version}-py3-none-any.whl"
        sdist = output / f"linux_idmap-{version}.tar.gz"
        if set(output.iterdir()) != {wheel, sdist} or any(not path.is_file() or path.is_symlink() for path in (wheel, sdist)):
            raise ValueError("Cannot build linux-idmap: expected exactly its wheel and source distribution.")
        normalize_sdist(sdist)
        lock = output / f"linux_idmap-{version}-install.lock"
        lock.write_text(f"linux-idmap=={version} " + "\\\n" + f"    --hash=sha256:{digest(wheel)}\n")
        if requirements(lock) != {("linux-idmap", version): {digest(wheel)}}:
            raise ValueError("Cannot build linux-idmap: installation lock differs from the built wheel.")
    return wheel, lock, identities


def install_environment(root, lock, pool):
    """Install the exact locked wheel into a pip-free isolated environment."""
    python = root / "environment/bin/python"
    subprocess.run([sys.executable, "-I", "-m", "venv", "--without-pip", str(python.parent.parent)], check=True)
    selected = select_wheels(lock, pool)
    with tempfile.NamedTemporaryFile(prefix="idmap-install-report-", suffix=".json") as report:
        observed = install_locked(python, lock, pool, Path(report.name))
        if observed != selected:
            raise ValueError("Cannot install linux-idmap: installed wheel differs from captured inputs.")
    subprocess.run([*pip_command(python), "--no-cache-dir", "check"], check=True)
    return python


def source_inventory(source):
    inventory = {}
    for path in sorted(source.rglob("*")):
        if path == source / ".gitignore":
            continue
        if path.is_symlink():
            raise ValueError("Cannot capture package inventory: source links are not release inputs.")
        if path.is_file():
            inventory[path.relative_to(source).as_posix()] = {
                "sha256": digest(path), "size": path.stat().st_size, "mode": path.stat().st_mode & 0o777,
            }
        elif not path.is_dir():
            raise ValueError("Cannot capture package inventory: source must contain regular files and directories.")
    return inventory


def normalize_sdist(path):
    """Remove host account metadata and use the same fixed epoch as the wheel."""
    normalized = path.with_suffix(".normalized")
    with tarfile.open(path, "r:gz") as original, normalized.open("xb") as output:
        with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=315532800) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as target:
                for member in sorted(original.getmembers(), key=lambda item: item.name):
                    if not (member.isfile() or member.isdir()):
                        raise ValueError("Cannot admit source distribution: archive contains an unsupported link or special file.")
                    member.uid = member.gid = 0
                    member.uname = member.gname = ""
                    member.mtime = 315532800
                    member.pax_headers = {}
                    if member.isfile():
                        with original.extractfile(member) as content:
                            target.addfile(member, content)
                    else:
                        target.addfile(member)
    normalized.replace(path)


def release(source, build_lock, pool, output, revision):
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("Cannot build release artifacts: source revision must identify the captured Git commit.")
    inventory = source_inventory(source)
    wheel, lock, identities = build_candidate(source, build_lock, pool, output)
    prefix = wheel.name.removesuffix("-py3-none-any.whl")
    sdist = output / (prefix + ".tar.gz")
    payload = (wheel, sdist, lock)
    record = output / (prefix + "-release.json")
    record.write_text(json.dumps({
        "source_revision": revision, "dependency_inputs": identities,
        "source_files": inventory, "files": {path.name: digest(path) for path in payload},
    }, sort_keys=True, indent=2) + "\n")
    manifest = output / (prefix + "-sha256.json")
    manifest.write_text(json.dumps({path.name: digest(path) for path in (*payload, record)}, sort_keys=True, indent=2) + "\n")
    for path in (*payload, record, manifest):
        with regular_file(path) as stream:
            os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
    fsync_directory(output)
    print(json.dumps({"source_revision": revision, "wheel": wheel.name, "sha256": digest(wheel)}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    release(args.source, args.build_lock, args.pool, args.output, args.revision)


if __name__ == "__main__":
    main()
