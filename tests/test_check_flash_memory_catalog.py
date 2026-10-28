import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "check_flash_memory_catalog.py"
SPEC = importlib.util.spec_from_file_location("check_flash_memory_catalog", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CheckFlashMemoryCatalogTests(unittest.TestCase):
    def test_profiles_pin_primary_references(self):
        self.assertEqual(set(MODULE.PROFILES), {"rs", "emerald", "frlg"})
        self.assertTrue(all(len(item["commit"]) == 40 for item in MODULE.PROFILES.values()))

    def test_unique_named_target(self):
        address_map = {"direct_calls": [{"name": "CheckForFlashMemory", "target": "0x08001234"}]}
        self.assertEqual(MODULE.unique_named_target(address_map, "CheckForFlashMemory"), 0x08001234)

    def test_validate_accepts_expected_shape(self):
        cfg = {
            "start_address": 0x08000100, "range_end": 0x08000126,
            "instruction_halfwords": 17, "calls": [{}, {}], "returns": [{}],
            "edges": [
                {"kind": "conditional-taken"},
                {"kind": "conditional-fallthrough"},
                {"kind": "branch"},
            ],
        }
        MODULE.validate(cfg, "release")

    def test_validate_rejects_changed_shape(self):
        cfg = {
            "start_address": 0, "range_end": 38, "instruction_halfwords": 16,
            "calls": [{}, {}], "returns": [{}], "edges": [{}, {}, {}],
        }
        with self.assertRaisesRegex(ValueError, "structural signature"):
            MODULE.validate(cfg, "release")


if __name__ == "__main__":
    unittest.main()
