import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "reset_bgs_catalog.py"
SPEC = importlib.util.spec_from_file_location("reset_bgs_catalog", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_cluster_order(self):
        self.assertEqual(
            MODULE.FUNCTIONS,
            ["ResetBgs", "ResetBgControlStructs", "SetTextModeAndHideBgs"],
        )

    def test_profiles_preserve_bitfield_difference(self):
        self.assertEqual(MODULE.PROFILES["emerald"]["bitfield_base"], "uint8_t")
        self.assertEqual(MODULE.PROFILES["frlg"]["bitfield_base"], "uint16_t")

    def test_unique_named_target(self):
        address_map = {"direct_calls": [{"name": "ResetBgs", "target": "0x08000100"}]}
        self.assertEqual(MODULE.unique_named_target(address_map, "ResetBgs"), 0x08000100)


if __name__ == "__main__":
    unittest.main()
