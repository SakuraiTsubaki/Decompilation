import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "init_flash_timer_catalog.py"
SPEC = importlib.util.spec_from_file_location("init_flash_timer_catalog", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InitFlashTimerCatalogTests(unittest.TestCase):
    def test_profiles_preserve_emerald_size_difference(self):
        self.assertEqual(MODULE.PROFILES["emerald"]["shape"], (14, 7, 1, 1, 0))
        self.assertEqual(MODULE.PROFILES["rs"]["shape"], (16, 8, 1, 1, 0))
        self.assertEqual(MODULE.PROFILES["frlg"]["shape"], (16, 8, 1, 1, 0))

    def test_unique_named_target(self):
        evidence = {"function": {"calls": [{"name": "InitFlashTimer", "target": "0x08000100"}]}}
        self.assertEqual(MODULE.unique_named_target(evidence, "InitFlashTimer"), 0x08000100)


if __name__ == "__main__":
    unittest.main()
