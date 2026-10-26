import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("map_music", ROOT / "tools/map_music_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def candidate():
    words = (*MODULE.INIT_PREFIX, 0xF000, 0xF880, *MODULE.INIT_EPILOGUE)
    return struct.pack("<8H", *words) + struct.pack("<I", 0x03001234)


class MapMusicCatalogTests(unittest.TestCase):
    def test_unique_init_candidate(self):
        self.assertEqual(MODULE.unique_init_offset(b"xx" + candidate() + b"yy"), 2)

    def test_duplicates_and_non_iwram_literal_are_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_init_offset(candidate() + candidate())
        changed = bytearray(candidate())
        struct.pack_into("<I", changed, MODULE.INIT_LENGTH, 0x02000000)
        self.assertEqual(MODULE.matching_init_offsets(bytes(changed)), [])

    def test_sources_express_verified_behavior(self):
        init = MODULE.init_source()
        main = MODULE.main_source()
        self.assertIn("gDisableMusic = FALSE", init)
        self.assertIn("ResetMapMusic();", init)
        self.assertIn("switch (sMapMusicState)", main)
        self.assertIn("case 7:", main)
        self.assertIn("FadeInNewBGM", main)


if __name__ == "__main__":
    unittest.main()
