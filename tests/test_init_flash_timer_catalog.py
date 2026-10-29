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
        self.assertEqual(MODULE.PROFILES["rs"]["handler_source"], "gFlashTimerIntrFunc")
        self.assertIsNone(MODULE.PROFILES["rs"]["interrupt_table_slot"])

    def test_unique_named_target(self):
        evidence = {"function": {"calls": [{"name": "InitFlashTimer", "target": "0x08000100"}]}}
        self.assertEqual(MODULE.unique_named_target(evidence, "InitFlashTimer"), 0x08000100)

    def test_operand_forms(self):
        def cfg(values):
            return {"instructions": [{"address": index * 2, "halfword": value}
                                     for index, value in enumerate(values)]}
        loaded = cfg([0xB500, 0x4803, 0x6801, 0x2002, 0xF000, 0xF800, 0xBC01, 0x4700])
        direct = cfg([0xB500, 0x4903, 0x2002, 0xF000, 0xF800, 0xBC01, 0x4700])
        self.assertEqual(MODULE.operand_form(loaded), "loaded-handler")
        self.assertEqual(MODULE.operand_form(direct), "slot-address")


if __name__ == "__main__":
    unittest.main()
