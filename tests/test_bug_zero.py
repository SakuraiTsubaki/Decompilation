from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_bug_zero.py"
SPEC = importlib.util.spec_from_file_location("check_bug_zero", MODULE_PATH)
assert SPEC and SPEC.loader
check_bug_zero = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_bug_zero)


FIELDNAMES = [
    "id", "targets", "category", "name", "affected_scope",
    "upstream_fix", "status", "source", "notes",
]


class BugZeroGateTests(unittest.TestCase):
    def make_target(self, root: Path, *, status: str = "verified", hashes=True) -> Path:
        path = root / "target.json"
        payload = {
            "identity_status": status,
            "hashes": [{"algorithm": "sha256", "value": "abc"}] if hashes else [],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def make_registry(self, root: Path, rows: list[dict[str, str]]) -> Path:
        path = root / "defects.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def row(self, *, status: str = "CLOSED", targets: str = "Scarlet|Violet"):
        return {
            "id": "SV-TEST-001",
            "targets": targets,
            "category": "battle",
            "name": "synthetic defect",
            "affected_scope": "test",
            "upstream_fix": "",
            "status": status,
            "source": "unit-test",
            "notes": "synthetic",
        }

    def test_verified_target_with_only_terminal_statuses_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.make_target(root)
            registry = self.make_registry(root, [self.row()])
            self.assertEqual(check_bug_zero.validate("Scarlet", config, registry), [])

    def test_unselected_target_blocks_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.make_target(root, status="unselected")
            registry = self.make_registry(root, [self.row()])
            errors = check_bug_zero.validate("Scarlet", config, registry)
            self.assertTrue(any("not verified" in error for error in errors))

    def test_open_defect_blocks_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.make_target(root)
            registry = self.make_registry(
                root, [self.row(status="REPRODUCTION_NEEDED_ON_LATEST")]
            )
            errors = check_bug_zero.validate("Scarlet", config, registry)
            self.assertTrue(any("blocking defect status" in error for error in errors))

    def test_target_without_hashes_blocks_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.make_target(root, hashes=False)
            registry = self.make_registry(root, [self.row()])
            errors = check_bug_zero.validate("Scarlet", config, registry)
            self.assertTrue(any("no recorded cryptographic hashes" in error for error in errors))

    def test_other_target_rows_do_not_satisfy_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.make_target(root)
            registry = self.make_registry(root, [self.row(targets="Violet")])
            errors = check_bug_zero.validate("Scarlet", config, registry)
            self.assertTrue(any("no registry entries apply" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
