import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("enable_vcount", ROOT / "tools/enable_vcount_intr_evidence.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate():
    words = (0xB500, 0x2004, 0xF000, 0xF800, *MODULE.MIDDLE, 0xF000, 0xF800, 0x2004, 0xF000, 0xF800, *MODULE.EPILOGUE)
    return struct.pack("<20H", *words)


class EnableVCountIntrEvidenceTests(unittest.TestCase):
    def test_unique_candidate(self):
        self.assertEqual(MODULE.unique_function_offset(b"xx" + candidate() + b"yy"), 2)

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_function_offset(candidate() + candidate())

    def test_rejects_wrong_compare_line(self):
        changed = bytearray(candidate())
        changed[12] ^= 1
        self.assertEqual(MODULE.matching_offsets(bytes(changed)), [])

    def test_source_expresses_verified_behavior(self):
        source = MODULE.reconstructed_source()
        self.assertIn("VCOUNT_COMPARE_LINE = 150", source)
        self.assertIn("DISPSTAT_VCOUNT_INTR = 1 << 5", source)
        self.assertIn("EnableInterrupts(INTR_FLAG_VCOUNT)", source)


if __name__ == "__main__":
    unittest.main()
