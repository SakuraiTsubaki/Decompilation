import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("display_interrupts", ROOT / "tools/display_interrupt_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate(template):
    words = list(template)
    masked_index = 0
    for index, value in enumerate(template):
        if value is None:
            words[index] = 0xF000 if masked_index % 2 == 0 else 0xF800
            masked_index += 1
    return struct.pack(f"<{len(words)}H", *words)


class DisplayInterruptCatalogTests(unittest.TestCase):
    def test_each_profile_template_has_one_candidate(self):
        for profile in ("rs", "emerald", "frlg"):
            for name, template in zip(("HBlankIntr", "VCountIntr", "SerialIntr"), MODULE.profile_templates(profile)):
                self.assertEqual(MODULE.unique_offset(b"xx" + candidate(template) + b"yy", template, name), 2)

    def test_duplicate_and_wrong_flag_are_rejected(self):
        data = candidate(MODULE.COMMON_HBLANK)
        with self.assertRaises(ValueError):
            MODULE.unique_offset(data + data, MODULE.COMMON_HBLANK, "HBlankIntr")
        changed = bytearray(data)
        struct.pack_into("<H", changed, 18, 0x2104)
        self.assertEqual(MODULE.matching_offsets(bytes(changed), MODULE.COMMON_HBLANK), [])

    def test_sources_preserve_family_differences(self):
        rs = MODULE.reconstructed_source("rs")
        emerald = MODULE.reconstructed_source("emerald")
        frlg = MODULE.reconstructed_source("frlg")
        self.assertIn("gMain.vcountCallback();", rs)
        self.assertNotIn("m4aSoundVSync", rs)
        self.assertIn("gMain.vcountCallback();\n    m4aSoundVSync();", emerald)
        self.assertIn("sVcountAtIntr = (uint8_t)REG_VCOUNT;", frlg)
        self.assertNotIn("gMain.vcountCallback();", frlg)


if __name__ == "__main__":
    unittest.main()
