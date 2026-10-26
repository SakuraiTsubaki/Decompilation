import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("seed_rtc", ROOT / "tools/seed_rng_with_rtc_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate(mask=MODULE.MASK_LITERAL):
    words = (0xB500, 0xF000, 0xF800, *MODULE.MIDDLE, 0xF000, 0xF800, *MODULE.EPILOGUE)
    return struct.pack("<12H", *words) + struct.pack("<I", mask)


class SeedRngWithRtcCatalogTests(unittest.TestCase):
    def test_unique_candidate(self):
        self.assertEqual(MODULE.unique_function_offset(b"xx" + candidate() + b"yy"), 2)

    def test_mask_literal_is_required(self):
        self.assertEqual(MODULE.matching_offsets(candidate(0xFFFFFFFF)), [])

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_function_offset(candidate() + candidate())

    def test_source_expresses_xor_fold(self):
        source = MODULE.reconstructed_source()
        self.assertIn("RtcGetMinuteCount", source)
        self.assertIn("(seed >> 16) ^ (seed & 0xFFFF)", source)
        self.assertIn("SeedRng((uint16_t)seed)", source)


if __name__ == "__main__":
    unittest.main()
