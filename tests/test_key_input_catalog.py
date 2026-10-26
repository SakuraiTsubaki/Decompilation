import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("key_input", ROOT / "tools/key_input_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate(template):
    return struct.pack(f"<{len(template)}H", *(0x1234 if value is None else value for value in template))


class KeyInputCatalogTests(unittest.TestCase):
    def test_profiles_locate_unique_functions(self):
        init = candidate(MODULE.INIT_TEMPLATE)
        for profile in ("direct", "pointer"):
            read = candidate(MODULE.read_template(profile))
            self.assertEqual(MODULE.unique_offset(b"xx" + init + b"yy", MODULE.INIT_TEMPLATE, "InitKeys"), 2)
            self.assertEqual(MODULE.unique_offset(b"xx" + read + b"yy", MODULE.read_template(profile), "ReadKeys"), 2)

    def test_duplicate_and_wrong_mask_are_rejected(self):
        template = MODULE.read_template("direct")
        data = candidate(template)
        with self.assertRaises(ValueError):
            MODULE.unique_offset(data + data, template, "ReadKeys")
        changed = bytearray(data)
        struct.pack_into("<H", changed, 64, 0x03FE)
        self.assertEqual(MODULE.matching_offsets(bytes(changed), template), [])

    def test_sources_preserve_save_access_difference(self):
        direct = MODULE.reconstructed_source("direct")
        pointer = MODULE.reconstructed_source("pointer")
        self.assertIn("gSaveBlock2.optionsButtonMode", direct)
        self.assertNotIn("gSaveBlock2Ptr", direct)
        self.assertIn("gSaveBlock2Ptr->optionsButtonMode", pointer)
        for source in (direct, pointer):
            self.assertIn("gKeyRepeatContinueDelay = 5", source)
            self.assertIn("gKeyRepeatStartDelay = 40", source)
            self.assertIn("REG_KEYINPUT ^ KEYS_MASK", source)


if __name__ == "__main__":
    unittest.main()
