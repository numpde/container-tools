"""Publication preserves authored notes, inspected routing and qualified bytes.

Ports the release-only cases from pay-to-play-wire 4c92a3b test_publish.py.
Fixture Git/GitHub/Make tools model host effects; real installed-artifact proof
belongs to tests/package, which qualified the issued release independently.
"""

from tools.container_guard import require_container

require_container()

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("tools/publish.sh", "tools/inference_native.sh", "tools/wheelhouse_path.sh"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(name, target)
        fixture = Path("tests/fixtures/publish-tools/linux_idmap.sh")
        shutil.copyfile(fixture, self.root / "tools/linux_idmap.sh")
        (self.root / "tools/docker_context.sh").write_text('''select_docker_context() {
    if [[ $PUBLISH_TEST_MODE == note-after-admission ]]; then
        printf 'changed after admission\\n' > "$PUBLISH_TEST_WORKTREE_NOTE"
    fi
}
''')
        self.note = self.root / "notes/005_release_v0.2.0.md"
        self.note.parent.mkdir()
        self.note.write_text("# Authored fixture release\n\nThe reader-facing change.\n")
        self.inputs = self.root / "inputs"
        self.inputs.mkdir(mode=0o700)
        artifacts = self.inputs / "artifacts"
        artifacts.mkdir()
        contents = {
            "linux_idmap-0.2.0-py3-none-any.whl": b"qualified wheel",
            "linux_idmap-0.2.0.tar.gz": b"qualified source",
            "linux_idmap-0.2.0-install.lock": b"qualified lock",
                        "linux_idmap-0.2.0-release.json": json.dumps({"source_revision": "0" * 39 + "1"}).encode(),
            "linux_idmap-0.2.0-sha256.json": b"{}",
        }
        for name, content in contents.items():
            (artifacts / name).write_bytes(content)
        self.receipts = "".join(f"QUALIFIED_SHA256 {hashlib.sha256(content).hexdigest()} {name}\n" for name, content in contents.items())
        (self.inputs / "release-test.log").write_text(self.receipts)
        (self.inputs / "release-build.log").write_text("qualified build\n")
        shutil.copyfile(self.note, self.inputs / "release-notes.md")
        shutil.copyfile(self.note, self.inputs / "committed-note.md")
        self.trace = self.root / "calls"
        self.bin = Path("tests/fixtures/publish-tools").resolve()

    # silent-defaults: allow-contract -- Existing tests exercise explicit paths; new release-layout tests request the documented per-tag default.
    def run_publisher(self, scenario, action, *, default_paths=False, path_overrides=None):
        environment = {"PATH": str(self.bin) + os.pathsep + os.defpath, "TMPDIR": str(self.root),
                       "TAG_INPUT_ORIGIN": "command line", "TAG_INPUT": "v0.2.0",
                       "ARTIFACTS_INPUT_ORIGIN": "command line", "ARTIFACTS_INPUT": str(self.inputs),
                       "OUTPUT_INPUT_ORIGIN": "command line", "OUTPUT_INPUT": str(self.root / "prepared"),
                       "WHEELHOUSE_INPUT_ORIGIN": "command line", "WHEELHOUSE_INPUT": str(self.root / "pool"),
                       "PUBLISH_TEST_COMMITTED_NOTE": str(self.inputs / "committed-note.md"),
                       "PUBLISH_TEST_WORKTREE_NOTE": str(self.note),
                       "PUBLISH_TEST_MODE": scenario, "PUBLISH_TEST_TRACE": str(self.trace)}
        if default_paths:
            for name in ("OUTPUT_INPUT_ORIGIN", "OUTPUT_INPUT", "ARTIFACTS_INPUT_ORIGIN", "ARTIFACTS_INPUT"):
                del environment[name]
        if path_overrides is not None:
            environment.update(path_overrides)
        return subprocess.run(
            ["bash", str(self.root / "tools/publish.sh"), action], cwd=self.root,
            env=environment,
            capture_output=True, text=True, timeout=15, check=False,
        )

    def test_default_release_directory_is_private_versioned_and_reused_by_publication(self):
        (self.root / "pool").mkdir()
        prepared = self.run_publisher("publish", "prepare", default_paths=True)
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        directory = self.root / "release-artifacts/v0.2.0"
        self.assertEqual(0o700, directory.parent.stat().st_mode & 0o777)
        self.assertEqual(0o700, directory.stat().st_mode & 0o777)
        self.assertEqual(self.note.read_bytes(), (directory / "release-notes.md").read_bytes())
        self.assertEqual(5, len(list((directory / "artifacts").iterdir())))
        self.assertIn("make publish/release TAG=v0.2.0", prepared.stdout)
        self.assertNotIn("ARTIFACTS=", prepared.stdout)
        published = self.run_publisher("publish", "release", default_paths=True)
        self.assertEqual(0, published.returncode, published.stdout + published.stderr)
        self.assertIn("gh release edit", self.trace.read_text())

    def test_default_preparation_refuses_stale_outputs_and_unsafe_parents(self):
        (self.root / "pool").mkdir()
        location = self.root / "release-artifacts"
        location.mkdir(mode=0o700)
        version = location / "v0.2.0"
        version.mkdir(mode=0o700)
        sentinel = version / "keep-me.txt"
        sentinel.write_text("existing evidence")
        first = self.run_publisher("publish", "prepare", default_paths=True)
        self.assertEqual(2, first.returncode)
        self.assertIn("empty", first.stderr)
        self.assertEqual("existing evidence", sentinel.read_text())
        sentinel.unlink()
        version.rmdir()
        location.chmod(0o755)
        exposed = self.run_publisher("publish", "prepare", default_paths=True)
        self.assertEqual(2, exposed.returncode)
        self.assertFalse(version.exists())
        location.rmdir()
        external = self.root / "external"
        external.mkdir(mode=0o700)
        location.symlink_to(external, target_is_directory=True)
        linked = self.run_publisher("publish", "prepare", default_paths=True)
        self.assertEqual(2, linked.returncode)
        self.assertFalse((external / "v0.2.0").exists())

    def test_default_publication_never_creates_missing_release_outputs(self):
        missing = self.run_publisher("publish", "release", default_paths=True)
        self.assertEqual(2, missing.returncode)
        self.assertFalse((self.root / "release-artifacts").exists())
        if self.trace.exists():
            self.assertNotIn("gh ", self.trace.read_text())

    def test_explicit_empty_release_paths_do_not_fall_back_to_default(self):
        (self.root / "pool").mkdir()
        for action, variable in (("prepare", "OUTPUT_INPUT"), ("release", "ARTIFACTS_INPUT")):
            with self.subTest(action=action):
                result = self.run_publisher("publish", action, path_overrides={variable: ""})
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertFalse((self.root / "release-artifacts").exists())

    def test_prepare_keeps_authored_note_and_qualified_files_without_github_access(self):
        (self.root / "prepared").mkdir(mode=0o700)
        (self.root / "pool").mkdir()
        result = self.run_publisher("publish", "prepare")
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertEqual(self.note.read_bytes(), (self.root / "prepared/release-notes.md").read_bytes())
        self.assertEqual(5, len(list((self.root / "prepared/artifacts").iterdir())))
        self.assertIn("make publish/release TAG=v0.2.0 ARTIFACTS=", result.stdout)
        self.assertNotIn("gh ", self.trace.read_text())

    def test_missing_duplicate_or_symlinked_authored_note_blocks_preparation(self):
        for scenario in ("missing", "duplicate", "symlink"):
            with self.subTest(scenario=scenario):
                if scenario == "missing":
                    self.note.unlink()
                elif scenario == "duplicate":
                    duplicate = self.note.with_name("006_release_v0.2.0.md")
                    duplicate.write_text("second note\n")
                else:
                    self.note.unlink()
                    self.note.symlink_to(self.inputs / "release-notes.md")
                result = self.run_publisher("publish", "prepare")
                self.assertEqual(2, result.returncode, msg=result.stderr)
                self.assertIn("exactly one authored", result.stderr)
                if self.trace.exists():
                    self.assertNotIn("gh ", self.trace.read_text())
                if scenario == "duplicate":
                    duplicate.unlink()
                else:
                    self.note.unlink(missing_ok=True)
                    self.note.write_text("# Authored fixture release\n\nThe reader-facing change.\n")

    def test_modified_prepared_note_cannot_reach_github(self):
        (self.inputs / "release-notes.md").write_text("changed note\n")
        result = self.run_publisher("publish", "release")
        self.assertEqual(2, result.returncode, msg=result.stderr)
        self.assertIn("prose differs", result.stderr)
        self.assertNotIn("gh ", self.trace.read_text())

    def test_uncommitted_note_cannot_be_prepared_even_if_status_is_clean(self):
        result = self.run_publisher("uncommitted-note", "prepare")
        self.assertEqual(2, result.returncode, msg=result.stderr)
        self.assertIn("regular file in the committed source", result.stderr)
        self.assertNotIn("gh ", self.trace.read_text())

    def test_different_or_unreadable_committed_note_cannot_be_prepared(self):
        for scenario in ("different-committed-note", "git-show-error"):
            with self.subTest(scenario=scenario):
                result = self.run_publisher(scenario, "prepare")
                self.assertEqual(2, result.returncode, msg=result.stderr)
                self.assertIn("must match the file committed", result.stderr)
                self.assertNotIn("gh ", self.trace.read_text())

    def test_committed_symlink_cannot_supply_a_regular_worktree_note(self):
        result = self.run_publisher("committed-symlink", "prepare")
        self.assertEqual(2, result.returncode, msg=result.stderr)
        self.assertIn("regular file in the committed source", result.stderr)
        self.assertNotIn("gh ", self.trace.read_text())

    def test_preparation_captures_committed_note_if_worktree_changes_after_admission(self):
        (self.root / "prepared").mkdir(mode=0o700)
        (self.root / "pool").mkdir()
        result = self.run_publisher("note-after-admission", "prepare")
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertNotEqual(self.note.read_bytes(), (self.inputs / "committed-note.md").read_bytes())
        self.assertEqual((self.inputs / "committed-note.md").read_bytes(),
                         (self.root / "prepared/release-notes.md").read_bytes())

    def test_matching_url_rewrite_or_unreadable_configuration_stops_before_github(self):
        for scenario in ("matching", "config-error"):
            with self.subTest(scenario=scenario):
                self.trace.unlink(missing_ok=True)
                result = self.run_publisher(scenario, "release")
                self.assertEqual(2, result.returncode, msg=result.stderr)
                calls = self.trace.read_text()
                self.assertRegex(result.stderr, "Git URL rewrite|Git URL routing")
                self.assertNotIn("gh ", calls)
                self.assertNotIn("git push", calls)

    def test_existing_release_and_uncertain_api_result_never_push(self):
        for scenario in ("existing", "api-error"):
            with self.subTest(scenario=scenario):
                self.trace.unlink(missing_ok=True)
                result = self.run_publisher(scenario, "release")
                self.assertEqual(2, result.returncode, msg=result.stderr)
                calls = self.trace.read_text()
                self.assertIn("gh api --hostname github.com --include", calls)
                self.assertNotIn(":refs/tags/v0.2.0", calls)
                self.assertNotIn("gh release create", calls)

    def test_existing_tag_at_another_commit_cannot_be_pushed(self):
        result = self.run_publisher("wrong-tag", "release")
        self.assertEqual(2, result.returncode, msg=result.stderr)
        self.assertIn("existing local tag identifies another", result.stderr)
        calls = self.trace.read_text()
        self.assertNotIn("git push", calls)
        self.assertNotIn("gh release create", calls)

    def test_duplicate_malformed_or_incomplete_receipts_never_reach_github(self):
        for receipts in (self.receipts + self.receipts.splitlines()[0] + "\n", self.receipts.replace("QUALIFIED_SHA256 ", "QUALIFIED_SHA256 broken ", 1), ""):
            with self.subTest(receipts=receipts):
                (self.inputs / "release-test.log").write_text(receipts)
                self.trace.unlink(missing_ok=True)
                result = self.run_publisher("publish", "release")
                self.assertEqual(2, result.returncode, msg=result.stderr)
                self.assertRegex(result.stderr, "artifact receipt|artifact name|all five artifact hashes")
                self.assertNotIn("gh ", self.trace.read_text())

    def test_downloaded_artifact_change_leaves_the_release_draft(self):
        result = self.run_publisher("corrupt", "release")
        self.assertEqual(2, result.returncode, msg=result.stderr)
        calls = self.trace.read_text()
        self.assertIn("gh release download", calls)
        self.assertNotIn("gh release edit", calls)

    def test_only_byte_verified_assets_are_made_public(self):
        result = self.run_publisher("publish", "release")
        self.assertEqual(0, result.returncode, msg=result.stderr)
        calls = self.trace.read_text()
        self.assertLess(calls.index("gh release download"), calls.index("gh release edit"))
        self.assertIn("0" * 39 + "1:refs/tags/v0.2.0", calls)
        self.assertEqual(7, len(list(Path(str(self.trace) + ".uploads").iterdir())))
        self.assertEqual((self.inputs / "committed-note.md").read_bytes(),
                         Path(str(self.trace) + ".notes").read_bytes())
        self.assertIn("--draft=false", calls)

    def test_unknown_native_retirement_stops_before_any_tag_or_draft_effect(self):
        (self.root / "tools/inference_native.sh").write_text("""inference_native() {
    local operation=$1 status=0
    shift 3
    if ! "$inference_retirement_confirmed"; then
        printf 'continued after unknown retirement\\n' >> "$PUBLISH_TEST_TRACE"
        return 97
    fi
    "$@" || status=$?
    if [[ $operation == 'existing GitHub release inspection' ]]; then
        inference_retirement_confirmed=false
        return 1
    fi
    return "$status"
}
""")
        result = self.run_publisher("publish", "release")
        self.assertEqual(1, result.returncode, msg=result.stderr)
        calls = self.trace.read_text()
        self.assertIn("gh api --hostname github.com --include", calls)
        self.assertNotIn("continued after unknown retirement", calls)
        self.assertNotIn("gh release create", calls)
        self.assertNotIn(":refs/tags/v0.2.0", calls)

    def test_failed_git_status_cannot_be_treated_as_clean_source(self):
        result = self.run_publisher("status-error", "release")
        self.assertEqual(2, result.returncode, msg=result.stderr)
        self.assertIn("Cannot inspect Git checkout status", result.stderr)
        calls = self.trace.read_text()
        self.assertNotIn("git rev-parse", calls)
        self.assertNotIn("gh ", calls)
