import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "clear_dma3_requests_catalog.py"
SPEC = importlib.util.spec_from_file_location("clear_dma3_requests_catalog", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_unique_named_target(self):
        address_map = {"direct_calls": [
            {"name": "ClearDma3Requests", "target": "0x08000100"},
            {"name": "Other", "target": "0x08000200"},
        ]}
        self.assertEqual(
            MODULE.unique_named_target(address_map, "ClearDma3Requests"),
            0x08000100,
        )

    def test_ambiguous_target_is_rejected(self):
        address_map = {"direct_calls": [
            {"name": "A", "target": "0x08000100"},
            {"name": "A", "target": "0x08000200"},
        ]}
        with self.assertRaises(ValueError):
            MODULE.unique_named_target(address_map, "A")

    def test_profiles_are_pinned(self):
        self.assertEqual(set(MODULE.PROFILES), {"emerald", "frlg"})
        for profile in MODULE.PROFILES.values():
            self.assertEqual(len(profile["commit"]), 40)


if __name__ == "__main__":
    unittest.main()
