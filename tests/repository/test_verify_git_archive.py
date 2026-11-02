"""Committed source verification detects omissions and altered blob bytes."""

from tools.container_guard import require_container

require_container()

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class GitArchiveTests(unittest.TestCase):
    def test_archive_must_match_committed_blob_and_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            (source / "package").mkdir(parents=True)
            item = source / "package" / "file"
            item.write_bytes(b"committed\n")
            digest = hashlib.sha1(b"blob 10\0committed\n").hexdigest()
            fake_bin = Path("tests/fixtures/git-tree-tools").resolve()
            verifier = Path("tools/verify_git_archive.sh").resolve()
            def verify():
                return subprocess.run(["bash", str(verifier), str(root), "HEAD", str(source), "package"],
                                      env={**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
                                           "GIT_TREE_TEST_DIGEST": digest},
                                      capture_output=True, text=True, check=False)
            self.assertEqual(0, verify().returncode)
            item.write_bytes(b"substituted\n")
            result = verify()
            self.assertNotEqual(0, result.returncode)
            self.assertIn("differs from committed source", result.stderr)
            item.write_bytes(b"committed\n")
            item.chmod(0o755)
            result = verify()
            self.assertNotEqual(0, result.returncode)
            self.assertIn("differs from committed source", result.stderr)
            item.unlink()
            result = verify()
            self.assertNotEqual(0, result.returncode)
            self.assertIn("missing from archive", result.stderr)


if __name__ == "__main__":
    unittest.main()
