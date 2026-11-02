"""Release qualification refuses omitted source and unsafe archive membership."""

from tools.container_guard import require_container

require_container()

import io
import json
from contextlib import redirect_stdout
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools.core_environment import build_candidate
from tools.package import artifact_names, check, source_payload, unpack_source, wheel_payload
from tools.wheelhouse import digest


class PackageArtifactTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_source_archive_refuses_traversal_links_duplicate_and_special_members_before_extraction(self):
        for name, kind in (("linux_idmap-0.2.0/../../outside", tarfile.REGTYPE),
                           ("/absolute", tarfile.REGTYPE), ("linux_idmap-0.2.0/link", tarfile.SYMTYPE),
                           ("linux_idmap-0.2.0/device", tarfile.CHRTYPE), ("linux_idmap-0.2.0/duplicate", "duplicate")):
            with self.subTest(name=name, kind=kind):
                path = self.root / "source.tar.gz"
                with tarfile.open(path, "w:gz") as archive:
                    member = tarfile.TarInfo(name)
                    member.mode = 0o644
                    if kind == "duplicate":
                        archive.addfile(member, io.BytesIO())
                    else:
                        member.type = kind
                    archive.addfile(member, io.BytesIO())
                destination = self.root / "extracted"
                with self.assertRaisesRegex(ValueError, "source archive"):
                    unpack_source(path, destination, "0.2.0")
                self.assertFalse(destination.exists())

    def test_source_inventory_detects_changed_bytes_and_omitted_test_files(self):
        source = self.root / "source"
        (source / "src/linux_idmap").mkdir(parents=True)
        (source / "tests").mkdir()
        (source / "examples").mkdir()
        for name in ("README.md", "MANIFEST.in", "pyproject.toml", "src/linux_idmap/__init__.py", "tests/test_contract.py", "examples/read_self.py"):
            (source / name).write_text("authored\n")
        inventory = {path.relative_to(source).as_posix(): {"sha256": digest(path), "size": path.stat().st_size,
                     "mode": path.stat().st_mode & 0o777} for path in source.rglob("*") if path.is_file()}
        metadata = source / "src/linux_idmap.egg-info"
        metadata.mkdir()
        for name in ("PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt", "top_level.txt"):
            (metadata / name).write_text("")
        for name in ("PKG-INFO", "setup.cfg"):
            (source / name).write_text("")
        self.assertEqual({"linux_idmap/__init__.py": b"authored\n"}, source_payload(source, inventory))
        (source / "examples/read_self.py").unlink()
        with self.assertRaisesRegex(ValueError, "pre-build source inventory"):
            source_payload(source, inventory)
        (source / "examples/read_self.py").write_text("authored\n")
        (source / "tests/test_contract.py").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "pre-build source inventory"):
            source_payload(source, inventory)
        (source / "tests/test_contract.py").unlink()
        with self.assertRaisesRegex(ValueError, "pre-build source inventory"):
            source_payload(source, inventory)

    def test_wheel_payload_detects_missing_extra_or_changed_runtime_files(self):
        path = self.root / "core.whl"
        expected = {"linux_idmap/__init__.py": b"owned\n", "linux_idmap/probe.py": b"client\n"}
        for payload in ({"linux_idmap/__init__.py": b"owned\n"}, expected | {"tools/helper.py": b"leak"},
                        expected | {"linux_idmap/probe.py": b"changed"}):
            with self.subTest(payload=payload):
                with zipfile.ZipFile(path, "w") as archive:
                    for name, value in payload.items():
                        archive.writestr(name, value)
                with self.assertRaisesRegex(ValueError, "wheel"):
                    wheel_payload(path, expected, "0.2.0")

    def test_corrupt_release_manifest_refuses_before_rebuild_and_emits_no_qualification_receipt(self):
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        for name in artifact_names("0.2.0"):
            (artifacts / name).write_text("{}\n")
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaisesRegex(ValueError, "release hashes"):
            check(artifacts, "0" * 40, self.root)
        self.assertEqual("", output.getvalue())

    def test_self_consistent_artifacts_cannot_claim_another_source_revision(self):
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        prefix = "linux_idmap-0.2.0"
        for suffix in ("-py3-none-any.whl", ".tar.gz", "-install.lock"):
            (artifacts / (prefix + suffix)).write_bytes(b"fixture")
        record = {"source_revision": "0" * 40, "source_files": {"different": {}},
                  "files": {path.name: digest(path) for path in artifacts.iterdir()}}
        (artifacts / (prefix + "-release.json")).write_text(json.dumps(record))
        manifest = {path.name: digest(path) for path in artifacts.iterdir()}
        (artifacts / (prefix + "-sha256.json")).write_text(json.dumps(manifest))
        source = self.root / "committed-source"
        source.mkdir()
        (source / "pyproject.toml").write_text("committed source\n")
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaisesRegex(ValueError, "differs from the captured commit"):
            check(artifacts, "0" * 40, source)
        self.assertEqual("", output.getvalue())

    def test_declared_builder_must_match_the_captured_lock(self):
        source = self.root / "source"
        source.mkdir()
        (source / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["setuptools==1.0"]\nbuild-backend = "setuptools.build_meta"\n'
            '[project]\nname = "linux-idmap"\nversion = "0.2.0"\ndependencies = []\n'
        )
        lock = self.root / "build.lock"
        lock.write_text("setuptools==84.1.0 \\\n    --hash=sha256:" + "0" * 64 + "\n")
        output = self.root / "output"
        output.mkdir()
        with patch("tools.core_environment.capture", return_value={}), \
             self.assertRaisesRegex(ValueError, "build requirements differ"):
            build_candidate(source, lock, self.root, output)
        self.assertEqual([], list(output.iterdir()))

    def test_wheel_rejects_runtime_dependencies_and_changed_cli_entrypoint(self):
        wheel = self.root / "wheel.whl"
        payload = {"linux_idmap/__init__.py": b"owned\n"}
        metadata = b"Metadata-Version: 2.1\nName: linux-idmap\nVersion: 0.2.0\n\n"
        entrypoint = b"[console_scripts]\nlinux-idmap-probe = linux_idmap._cli:main\n"
        for contents, entry, message in (
            (metadata.replace(b"\n\n", b"\nRequires-Dist: foreign\n\n"), entrypoint, "metadata"),
            (metadata, entrypoint.replace(b"_cli:main", b"other:main"), "entrypoint"),
        ):
            with self.subTest(message=message):
                with zipfile.ZipFile(wheel, "w") as archive:
                    archive.writestr("linux_idmap/__init__.py", payload["linux_idmap/__init__.py"])
                    archive.writestr("linux_idmap-0.2.0.dist-info/METADATA", contents)
                    archive.writestr("linux_idmap-0.2.0.dist-info/entry_points.txt", entry)
                with self.assertRaisesRegex(ValueError, message):
                    wheel_payload(wheel, payload, "0.2.0")
