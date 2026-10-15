import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rng_evidence", ROOT / "tools/rng_evidence.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def put_halfwords(data, offset, values):
    struct.pack_into(f"<{len(values)}H", data, offset, *values)


class RngEvidenceTests(unittest.TestCase):
    def test_standard_variant(self):
        data = bytearray(128)
        put_halfwords(data, 0, MODULE.RANDOM_PATTERNS["standard"])
        struct.pack_into("<III", data, 20, 0x03001234, MODULE.MULTIPLIER, MODULE.INCREMENT)
        put_halfwords(data, 32, MODULE.SEED_PATTERNS["standard"])
        struct.pack_into("<I", data, 44, 0x03001234)
        result = MODULE.analyze(data, 0, 32, "standard")
        self.assertEqual(result["globals"], {"gRngValue": "0x03001234"})
        self.assertEqual(result["functions"]["Random"]["rom_code_range"]["length"], 18)

    def test_emerald_variant_tracks_counter_and_reset_byte(self):
        data = bytearray(160)
        put_halfwords(data, 0, MODULE.RANDOM_PATTERNS["emerald"])
        struct.pack_into("<IIII", data, 28, 0x03005678, MODULE.MULTIPLIER, MODULE.INCREMENT, 0x02001234)
        put_halfwords(data, 48, MODULE.SEED_PATTERNS["emerald"])
        struct.pack_into("<II", data, 64, 0x03005678, 0x02001230)
        result = MODULE.analyze(data, 0, 48, "emerald")
        self.assertEqual(result["globals"]["sRandCount"], "0x02001234")
        self.assertEqual(result["globals"]["sUnknown"], "0x02001230")
        self.assertEqual(result["functions"]["SeedRng"]["rom_code_range"]["length"], 16)

    def test_rejects_wrong_lcg_constant(self):
        data = bytearray(128)
        put_halfwords(data, 0, MODULE.RANDOM_PATTERNS["standard"])
        struct.pack_into("<III", data, 20, 0x03001234, 1, MODULE.INCREMENT)
        put_halfwords(data, 32, MODULE.SEED_PATTERNS["standard"])
        struct.pack_into("<I", data, 44, 0x03001234)
        with self.assertRaisesRegex(ValueError, "LCG constants"):
            MODULE.analyze(data, 0, 32, "standard")


if __name__ == "__main__":
    unittest.main()
