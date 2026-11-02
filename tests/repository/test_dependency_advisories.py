"""Keep the advisory snapshot tied to the exact build dependency lock."""

from tools.container_guard import require_container

require_container()

import hashlib
import json
import unittest
from datetime import datetime

from tests.repository.quality.sources import ROOT
from tools.wheelhouse import requirements


class DependencyAdvisoryTests(unittest.TestCase):
    def test_snapshot_identifies_the_current_lock_and_all_its_packages(self):
        lock = ROOT / "requirements/linux-idmap-build.lock"
        record = json.loads((ROOT / "requirements/linux-idmap-build-advisories.json").read_text())
        self.assertIsNotNone(datetime.fromisoformat(record["checked_at"]).utcoffset())
        self.assertEqual({"requirements/linux-idmap-build.lock": hashlib.sha256(lock.read_bytes()).hexdigest()},
                         record["inputs_sha256"])
        packages = record["packages"]
        identities = [(entry["name"], entry["version"]) for entry in packages]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(set(requirements(lock)), set(identities))
        for entry in packages:
            self.assertEqual(f"https://pypi.org/pypi/{entry['name']}/{entry['version']}/json", entry["url"])
            self.assertIsInstance(entry["vulnerabilities"], list)


if __name__ == "__main__":
    unittest.main()
