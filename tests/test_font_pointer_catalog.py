import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "font_pointer_catalog.py"
SPEC = importlib.util.spec_from_file_location("font_pointer_catalog", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_cluster_order(self):
        self.assertEqual(MODULE.FUNCTIONS, ["SetDefaultFontsPointer", "SetFontsPointer"])

    def test_profiles_capture_distinct_default_tables(self):
        self.assertEqual(MODULE.PROFILES["emerald"]["default_table"], "sFontInfos")
        self.assertEqual(MODULE.PROFILES["frlg"]["default_table"], "gFontInfos")

    def test_unique_named_target(self):
        address_map = {"direct_calls": [
            {"name": "SetDefaultFontsPointer", "target": "0x08000100"},
        ]}
        self.assertEqual(
            MODULE.unique_named_target(address_map, "SetDefaultFontsPointer"),
            0x08000100,
        )


if __name__ == "__main__":
    unittest.main()
