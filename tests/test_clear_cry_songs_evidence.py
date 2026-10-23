import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "clear_cry_songs", ROOT / "tools/clear_cry_songs_evidence.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate(destination=0x03006E60):
    return (
        MODULE.PREFIX
        + bytes.fromhex("00f000f8")
        + MODULE.EPILOGUE
        + bytes(2)
        + struct.pack("<I", destination)
        + struct.pack("<I", MODULE.CPU_SET_MODE)
    )


class ClearCrySongsEvidenceTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual((MODULE.FUNCTION_LENGTH, MODULE.HALFWORD_COUNT, MODULE.BYTE_COUNT), (26, 52, 104))

    def test_unique_candidate(self):
        data = b"xx" + candidate() + b"yy"
        self.assertEqual(MODULE.unique_function_offset(data), 2)

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_function_offset(candidate() + candidate())

    def test_source_expresses_fixed_halfword_fill(self):
        source = MODULE.reconstructed_source()
        self.assertIn("ClearPokemonCrySongs", source)
        self.assertIn("CPU_SET_SOURCE_FIXED", source)
        self.assertIn("POKEMON_CRY_SONG_BYTES 104u", source)


if __name__ == "__main__":
    unittest.main()
