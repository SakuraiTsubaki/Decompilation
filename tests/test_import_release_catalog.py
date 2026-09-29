from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("import_release_catalog", ROOT / "tools" / "import_release_catalog.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def source(prefix: str = "AXV", valid: bool = True) -> str:
    return json.dumps({
        "game_code_prefix": prefix,
        "language_priority": ["Japanese", "English"],
        "observed_files": 2,
        "unique_identities": 1,
        "releases": [{
            "id": "axv-j-rev0-retail", "language": "Japanese", "revision": 0,
            "build_kind": "retail", "sha1": "1" * 40, "sha256": "2" * 64,
            "header": {"game_code": "AXVJ"},
            "validation": {key: valid for key in (
                "nintendo_logo_valid", "fixed_value_valid", "reserved_area_valid", "header_checksum_valid"
            )},
        }],
    }, indent=2) + "\n"


class ImportReleaseCatalogTests(unittest.TestCase):
    def test_import_preserves_verified_identities_and_provenance(self):
        text = source()
        result = module.import_catalog(text, "AXV", "owner/source", "analysis/ruby-global-release-catalog.json")
        self.assertEqual(result["origin_reference"], "Japanese")
        self.assertEqual(result["unique_identities"], 1)
        self.assertEqual(result["releases"][0]["header"]["game_code"], "AXVJ")
        self.assertEqual(len(result["source"]["sha256"]), 64)

    def test_rejects_mismatch_and_failed_validation(self):
        with self.assertRaisesRegex(ValueError, "prefix mismatch"):
            module.import_catalog(source("AXP"), "AXV", "owner/source", "analysis/source.json")
        with self.assertRaisesRegex(ValueError, "failed validation"):
            module.import_catalog(source(valid=False), "AXV", "owner/source", "analysis/source.json")

    def test_output_hash_is_manifest_ready(self):
        result = module.import_catalog(source(), "AXV", "owner/source", "analysis/source.json")
        text = json.dumps(result, indent=2) + "\n"
        self.assertEqual(len(module.hashlib.sha256(text.encode("utf-8")).hexdigest()), 64)


if __name__ == "__main__":
    unittest.main()
