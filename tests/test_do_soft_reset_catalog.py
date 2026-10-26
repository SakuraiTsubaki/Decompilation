import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("do_soft_reset", ROOT / "tools/do_soft_reset_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def ldr_literal(register, immediate_words):
    return 0x4800 | register << 8 | immediate_words


def halfword_access(load, register, base, byte_offset):
    return (0x8800 if load else 0x8000) | byte_offset // 2 << 6 | base << 3 | register


def add_immediate3(destination, source, immediate):
    return 0x1C00 | immediate << 6 | source << 3 | destination


def and_register(destination, source):
    return 0x4000 | source << 3 | destination


def make_candidate(rtc=True):
    words = [
        MODULE.THUMB_PUSH_R4_LR, ldr_literal(1, 22 if rtc else 21), 0x2000,
        halfword_access(False, 0, 1, 0), 0xF000, 0xF800, 0xF000, 0xF800,
        ldr_literal(1, 19 if rtc else 18), halfword_access(True, 2, 1, 10),
        ldr_literal(3, 19 if rtc else 18), add_immediate3(0, 3, 0), and_register(0, 2),
        halfword_access(False, 0, 1, 10), halfword_access(True, 4, 1, 10),
        ldr_literal(2, 18 if rtc else 17), add_immediate3(0, 2, 0), and_register(0, 4),
        halfword_access(False, 0, 1, 10), halfword_access(True, 0, 1, 10), 0x310C,
        halfword_access(True, 4, 1, 10), add_immediate3(0, 3, 0), and_register(0, 4),
        halfword_access(False, 0, 1, 10), halfword_access(True, 4, 1, 10),
        add_immediate3(0, 2, 0), and_register(0, 4), halfword_access(False, 0, 1, 10),
        halfword_access(True, 0, 1, 10), ldr_literal(0, 11 if rtc else 10),
        halfword_access(True, 1, 0, 10), and_register(3, 1), halfword_access(False, 3, 0, 10),
        halfword_access(True, 1, 0, 10), and_register(2, 1), halfword_access(False, 2, 0, 10),
        halfword_access(True, 0, 0, 10),
    ]
    if rtc:
        words += [0xF000, 0xF800, 0x20FF, 0xF000, 0xF800]
    else:
        words += [0x20DF, 0xF000, 0xF800]
    words += [MODULE.THUMB_POP_R4, MODULE.THUMB_POP_R0, MODULE.THUMB_BX_R0]
    body = struct.pack(f"<{len(words)}H", *words)
    literals = struct.pack("<IIIII", MODULE.REG_IME, MODULE.DMA1_BASE, MODULE.DMA_CLEAR_ENABLE, MODULE.DMA_CLEAR_ALL, MODULE.DMA3_BASE)
    return body + literals


class DoSoftResetCatalogTests(unittest.TestCase):
    def test_rtc_candidate(self):
        result = MODULE.unique_candidate(make_candidate(True))
        self.assertEqual((result["length"], result["variant"], result["reset_mask"], result["rtc_protected"]), (92, "rtc-full-reset", 0xFF, True))

    def test_no_rtc_candidate(self):
        result = MODULE.unique_candidate(make_candidate(False))
        self.assertEqual((result["length"], result["variant"], result["reset_mask"], result["rtc_protected"]), (88, "no-rtc-preserve-sio", 0xDF, False))

    def test_wrong_hardware_literal_rejected(self):
        data = make_candidate(True)[:-20] + struct.pack("<IIIII", 0, MODULE.DMA1_BASE, MODULE.DMA_CLEAR_ENABLE, MODULE.DMA_CLEAR_ALL, MODULE.DMA3_BASE)
        with self.assertRaises(ValueError):
            MODULE.unique_candidate(data)

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_candidate(make_candidate(False) + make_candidate(False))


if __name__ == "__main__":
    unittest.main()
