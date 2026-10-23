import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "wait_for_vblank_catalog", ROOT / "tools/wait_for_vblank_catalog.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def encoded(*words):
    return struct.pack(f"<{len(words)}H", *words)


def ldr_literal(register, immediate_words):
    return 0x4800 | register << 8 | immediate_words


def halfword_access(load, register, base, byte_offset):
    return (0x8800 if load else 0x8000) | byte_offset // 2 << 6 | base << 3 | register


def and_register(destination, source):
    return 0x4000 | source << 3 | destination


def mov_immediate(register, immediate):
    return 0x2000 | register << 8 | immediate


def cmp_immediate(register, immediate):
    return 0x2800 | register << 8 | immediate


def add_immediate3(destination, source, immediate):
    return 0x1C00 | immediate << 6 | source << 3 | destination


def conditional_branch(condition, immediate):
    return 0xD000 | condition << 8 | immediate & 0xFF


def bios_call_candidate(main_address=0x030016E0, call_delta=0):
    body = encoded(
        MODULE.THUMB_PUSH_LR,
        ldr_literal(1, 5),
        halfword_access(True, 2, 1, MODULE.INTR_CHECK_OFFSET),
        ldr_literal(0, 5),
        and_register(0, 2),
        halfword_access(True, 2, 1, MODULE.INTR_CHECK_OFFSET),
        halfword_access(False, 0, 1, MODULE.INTR_CHECK_OFFSET),
        0xF000 | (call_delta >> 12 & 0x7FF),
        0xF800 | (call_delta >> 1 & 0x7FF),
        MODULE.THUMB_POP_R0,
        MODULE.THUMB_BX_R0,
    )
    return body + bytes(2) + struct.pack("<II", main_address, MODULE.VBLANK_CLEAR_MASK)


def polling_candidate(main_address=0x03002360):
    body = encoded(
        MODULE.THUMB_PUSH_LR,
        ldr_literal(2, 9),
        halfword_access(True, 1, 2, MODULE.INTR_CHECK_OFFSET),
        ldr_literal(0, 9),
        and_register(0, 1),
        halfword_access(True, 1, 2, MODULE.INTR_CHECK_OFFSET),
        halfword_access(False, 0, 2, MODULE.INTR_CHECK_OFFSET),
        halfword_access(True, 1, 2, MODULE.INTR_CHECK_OFFSET),
        mov_immediate(0, 1),
        and_register(0, 1),
        cmp_immediate(0, 0),
        conditional_branch(1, 5),
        mov_immediate(3, 1),
        halfword_access(True, 1, 2, MODULE.INTR_CHECK_OFFSET),
        add_immediate3(0, 3, 0),
        and_register(0, 1),
        cmp_immediate(0, 0),
        conditional_branch(0, -6),
        MODULE.THUMB_POP_R0,
        MODULE.THUMB_BX_R0,
    )
    return body + struct.pack("<II", main_address, MODULE.VBLANK_CLEAR_MASK)


class WaitForVBlankCatalogTests(unittest.TestCase):
    def test_bios_call_candidate(self):
        result = MODULE.unique_candidate(bios_call_candidate())
        self.assertEqual((result["offset"], result["length"], result["variant"]), (0, 22, "bios-call"))
        self.assertEqual(result["g_main_address"], 0x030016E0)

    def test_polling_candidate(self):
        result = MODULE.unique_candidate(polling_candidate())
        self.assertEqual((result["offset"], result["length"], result["variant"]), (0, 40, "volatile-poll"))
        self.assertEqual(result["mask_literal_offset"], 44)

    def test_wrong_mask_rejected(self):
        data = polling_candidate()[:-4] + struct.pack("<I", 0xFFFF)
        with self.assertRaises(ValueError):
            MODULE.unique_candidate(data)

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_candidate(polling_candidate() + polling_candidate())


if __name__ == "__main__":
    unittest.main()
