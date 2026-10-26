import importlib.util
import struct
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "agb_main_catalog.py"
SPEC = importlib.util.spec_from_file_location("agb_main_catalog", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_target_equivalence_preserves_first_seen_classes(self):
        calls = [
            {"target": 10}, {"target": 20}, {"target": 10},
            {"target": 30}, {"target": 20},
        ]
        self.assertEqual(MODULE.target_equivalence(calls), [0, 1, 0, 2, 1])

    def test_backward_loop_edges_rejects_forward_and_conditional_edges(self):
        cfg = {"edges": [
            {"source": 20, "target": 10, "kind": "branch"},
            {"source": 10, "target": 20, "kind": "branch"},
            {"source": 30, "target": 10, "kind": "conditional-taken"},
        ]}
        self.assertEqual(MODULE.backward_loop_edges(cfg), [cfg["edges"][0]])

    def test_short_rom_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "shorter"):
            MODULE.locate_agb_main(b"\0\0\0")

    def test_non_branch_entry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "entry word"):
            MODULE.locate_agb_main(struct.pack("<I", 0))


if __name__ == "__main__":
    unittest.main()
