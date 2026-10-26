import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("play_time", ROOT / "tools/play_time_controls.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PlayTimeCounterCatalogTests(unittest.TestCase):
    def test_profiles_locate_unique_cluster(self):
        for profile in ("direct", "pointer"):
            template = MODULE.reset_template(profile)
            data = b"xx" + struct.pack(f"<{len(template)}H", *template) + b"yy"
            self.assertEqual(MODULE.unique_cluster_offset(data, profile), 2)

    def test_duplicates_are_rejected(self):
        template = MODULE.reset_template("direct")
        data = struct.pack(f"<{len(template)}H", *template)
        with self.assertRaises(ValueError):
            MODULE.unique_cluster_offset(data + data, "direct")

    def test_sources_preserve_save_access_difference(self):
        direct = MODULE.reconstructed_source("direct")
        pointer = MODULE.reconstructed_source("pointer")
        self.assertIn("gSaveBlock2.playTimeHours", direct)
        self.assertNotIn("gSaveBlock2Ptr", direct)
        self.assertIn("gSaveBlock2Ptr->playTimeHours", pointer)
        for source in (direct, pointer):
            self.assertIn("PlayTimeCounter_SetToMax();", source)
            self.assertIn("playTimeVBlanks", source)
            self.assertIn("> 999", source)

    def test_layouts_cover_all_five_functions(self):
        for profile in ("direct", "pointer"):
            functions = MODULE.LAYOUTS[profile]["functions"]
            self.assertEqual(len(functions), 5)
            self.assertEqual([item[3] for item in functions], [0, 1, 0, 1, 0])


if __name__ == "__main__":
    unittest.main()

