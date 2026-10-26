import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("vblank_intr", ROOT / "tools/vblank_intr_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VBlankIntrCatalogTests(unittest.TestCase):
    def test_source_profiles_preserve_distinct_behavior(self):
        rs = MODULE.reconstructed_source("rs")
        emerald = MODULE.reconstructed_source("emerald")
        frlg = MODULE.reconstructed_source("frlg")
        self.assertIn("savedIme = REG_IME", rs)
        self.assertNotIn("RfuVSync", rs)
        self.assertIn("gTrainerHillVBlankCounter", emerald)
        self.assertIn("BATTLE_RNG_SUPPRESS_MASK", emerald)
        self.assertIn("sVcountBeforeSound", frlg)
        self.assertIn("sVcountAfterSound", frlg)
        for source in (emerald, frlg):
            self.assertIn("RfuVSync", source)
            self.assertIn("TryReceiveLinkBattleData", source)

    def test_profiles_have_expected_boundaries_and_calls(self):
        self.assertEqual(MODULE.PROFILES["rs"]["length"], 98)
        self.assertEqual(MODULE.PROFILES["emerald"]["length"], 164)
        self.assertEqual(MODULE.PROFILES["frlg"]["length"], 132)
        self.assertEqual(len(MODULE.CALL_NAMES["rs"]), 6)
        self.assertEqual(len(MODULE.CALL_NAMES["emerald"]), 9)
        self.assertEqual(len(MODULE.CALL_NAMES["frlg"]), 9)


if __name__ == "__main__":
    unittest.main()
