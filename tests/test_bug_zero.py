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
GENVI_FIELDNAMES = [
    "id", "scope", "category", "name", "reported_versions",
    "verification", "source",
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

    def make_genvi_registry(self, root: Path, rows: list[dict[str, str]]) -> Path:
        path = root / "genvi-defects.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=GENVI_FIELDNAMES)
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

    def genvi_row(self, *, scope: str = "XY", verification: str = "CLOSED"):
        return {
            "id": "GENVI-TEST-001",
            "scope": scope,
            "category": "battle",
            "name": "synthetic Generation VI defect",
            "reported_versions": "test",
            "verification": verification,
            "source": "unit-test",
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

    def test_generation_vi_xy_scope_applies_to_x(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.make_target(root)
            registry = self.make_genvi_registry(root, [self.genvi_row(scope="XY")])
            self.assertEqual(check_bug_zero.validate("X", config, registry), [])

    def test_generation_vi_oras_scope_does_not_apply_to_x(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.make_target(root)
            registry = self.make_genvi_registry(root, [self.genvi_row(scope="ORAS")])
            errors = check_bug_zero.validate("X", config, registry)
            self.assertTrue(any("no registry entries apply" in error for error in errors))

    def test_generation_vi_public_seed_blocks_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.make_target(root)
            registry = self.make_genvi_registry(
                root,
                [self.genvi_row(scope="XY+ORAS", verification="public_seed_unverified")],
            )
            errors = check_bug_zero.validate("Omega Ruby", config, registry)
            self.assertTrue(any("REPRODUCTION_NEEDED_ON_LATEST" in error for error in errors))

    def test_generation_vi_official_fix_still_requires_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.make_target(root)
            registry = self.make_genvi_registry(
                root,
                [self.genvi_row(scope="XY", verification="officially_fixed")],
            )
            errors = check_bug_zero.validate("Y", config, registry)
            self.assertTrue(any("UPSTREAM_FIXED_VERIFY" in error for error in errors))

    def test_generation_vi_default_registry_selection(self):
        self.assertEqual(
            check_bug_zero.default_registry_for("Alpha Sapphire"),
            Path("manifests/generation-vi-known-defects.csv"),
        )
        self.assertEqual(
            check_bug_zero.default_registry_for("Violet"),
            Path("manifests/generation-ix-known-defects.csv"),
        )


if __name__ == "__main__":
    unittest.main()
