import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("interrupt_init", ROOT / "tools/interrupt_init_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate(template):
    words = list(template)
    masked = 0
    for index, value in enumerate(words):
        if value is None:
            words[index] = 0xF000 if masked % 2 == 0 else 0xF800
            masked += 1
    return struct.pack(f"<{len(words)}H", *words)


class InterruptInitCatalogTests(unittest.TestCase):
    def test_profiles_locate_unique_init(self):
        for profile in ("rs", "emerald", "frlg"):
            data = b"xx" + candidate(MODULE.init_template(profile)) + b"yy"
            self.assertEqual(MODULE.unique_init_offset(data, profile), 2)

    def test_duplicate_and_bad_loop_count_are_rejected(self):
        data = candidate(MODULE.RS_INIT)
        with self.assertRaises(ValueError):
            MODULE.unique_init_offset(data + data, "rs")
        changed = bytearray(data)
        struct.pack_into("<H", changed, 10, 0x210C)
        self.assertEqual(MODULE.matching_init_offsets(bytes(changed), "rs"), [])

    def test_sources_preserve_profile_differences(self):
        rs = MODULE.reconstructed_source("rs")
        emerald = MODULE.reconstructed_source("emerald")
        frlg = MODULE.reconstructed_source("frlg")
        self.assertIn("REG_DISPSTAT = DISPSTAT_VBLANK_INTR", rs)
        self.assertNotIn("EnableInterrupts", rs)
        self.assertIn("EnableInterrupts(INTR_FLAG_VBLANK)", emerald)
        self.assertIn("RestoreSerialTimer3IntrHandlers", emerald)
        self.assertIn("EnableInterrupts(INTR_FLAG_VBLANK)", frlg)
        self.assertNotIn("RestoreSerialTimer3IntrHandlers", frlg)
        for source in (rs, emerald, frlg):
            self.assertIn("i < 14", source)
            self.assertIn("sizeof(IntrMain_Buffer) / 4", source)


if __name__ == "__main__":
    unittest.main()
