from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("thumb_call_targets", ROOT / "tools" / "thumb_call_targets.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ThumbCallTargetTests(unittest.TestCase):
    def test_groups_repeated_targets(self):
        cfg = {"rom_base": 0x08000000, "source_size": 0x1000, "source_sha256": "a", "start_address": 0x08000010,
               "calls": [{"source": 0x08000012, "target": 0x08000080}, {"source": 0x08000020, "target": 0x08000080}, {"source": 0x08000024, "target": 0x08000100}]}
        result = module.summarize(cfg)
        self.assertEqual((result["call_sites"], result["unique_targets"], result["repeated_targets"]), (3, 2, 1))
        self.assertEqual(result["targets"][0]["source_addresses"], [0x08000012, 0x08000020])

    def test_marks_target_outside_rom(self):
        result = module.summarize({"source_size": 0x20, "calls": [{"source": 0x08000000, "target": 0x02000000}]})
        self.assertFalse(result["targets"][0]["in_rom"])
        self.assertIsNone(result["targets"][0]["target_offset"])

    def test_rejects_odd_target(self):
        with self.assertRaisesRegex(ValueError, "halfword"):
            module.summarize({"source_size": 0x20, "calls": [{"source": 0x08000000, "target": 0x08000001}]})


if __name__ == "__main__":
    unittest.main()
