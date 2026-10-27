import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "main_callback_catalog.py"
SPEC = importlib.util.spec_from_file_location("main_callback_catalog", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_unique_named_target(self):
        address_map = {"direct_calls": [
            {"name": "A", "target": "0x08000100"},
            {"name": "A", "target": "0x08000100"},
            {"name": "B", "target": "0x08000200"},
        ]}
        self.assertEqual(MODULE.unique_named_target(address_map, "A"), 0x08000100)

    def test_ambiguous_named_target_is_rejected(self):
        address_map = {"direct_calls": [
            {"name": "A", "target": "0x08000100"},
            {"name": "A", "target": "0x08000200"},
        ]}
        with self.assertRaisesRegex(ValueError, "one target"):
            MODULE.unique_named_target(address_map, "A")

    def test_profiles_cover_three_families(self):
        self.assertEqual(set(MODULE.PROFILES), {"rs", "emerald", "frlg"})


if __name__ == "__main__":
    unittest.main()
