import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "set_main_callback2", ROOT / "tools/set_main_callback2_evidence.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def encoded(*words):
    return struct.pack(f"<{len(words)}H", *words)


def ldr_literal(register, words):
    return 0x4800 | register << 8 | words


def str_word(source, base, byte_offset):
    return 0x6000 | byte_offset // 4 << 6 | base << 3 | source


def mov_immediate(register, immediate):
    return 0x2000 | register << 8 | immediate


def lsl_immediate(destination, source, amount):
    return amount << 6 | source << 3 | destination


def add_register(destination, left, right):
    return 0x1800 | right << 6 | left << 3 | destination


def str_byte(source, base, byte_offset):
    return 0x7000 | byte_offset << 6 | base << 3 | source


def inline_candidate(main_address=0x03001770):
    return encoded(
        ldr_literal(1, 3),
        str_word(0, 1, 4),
        mov_immediate(0, 0x87),
        lsl_immediate(0, 0, 3),
        add_register(1, 1, 0),
        mov_immediate(0, 0),
        str_byte(0, 1, 0),
        MODULE.THUMB_BX_LR,
    ) + struct.pack("<I", main_address)


def literal_candidate(main_address=0x03001770, state_offset=0x438):
    return (
        encoded(
            ldr_literal(1, 3),
            str_word(0, 1, 4),
            ldr_literal(0, 3),
            add_register(1, 1, 0),
            mov_immediate(0, 0),
            str_byte(0, 1, 0),
            MODULE.THUMB_BX_LR,
        )
        + bytes(2)
        + struct.pack("<I", main_address)
        + struct.pack("<I", state_offset)
    )


class SetMainCallback2EvidenceTests(unittest.TestCase):
    def test_inline_state_offset_candidate(self):
        result = MODULE.unique_candidate(inline_candidate())
        self.assertEqual(
            (result["offset"], result["length"], result["variant"], result["g_main_address"]),
            (0, 16, "inline-state-offset", 0x03001770),
        )
        self.assertEqual(result["state_offset"], 0x438)

    def test_literal_state_offset_candidate(self):
        result = MODULE.unique_candidate(literal_candidate())
        self.assertEqual(
            (result["offset"], result["length"], result["variant"], result["g_main_address"]),
            (0, 14, "literal-state-offset", 0x03001770),
        )
        self.assertEqual(result["state_offset"], 0x438)

    def test_localized_literal_state_offset_candidate(self):
        result = MODULE.unique_candidate(literal_candidate(state_offset=0x43C))
        self.assertEqual(result["state_offset"], 0x43C)

    def test_invalid_state_offset_rejected(self):
        data = literal_candidate()[:-4] + struct.pack("<I", 0x123)
        with self.assertRaises(ValueError):
            MODULE.unique_candidate(data)

    def test_duplicate_candidates_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_candidate(inline_candidate() + inline_candidate())


if __name__ == "__main__":
    unittest.main()
