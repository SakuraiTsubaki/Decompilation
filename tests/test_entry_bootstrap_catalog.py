import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "entry_bootstrap_catalog.py"
SPEC = importlib.util.spec_from_file_location("entry_bootstrap_catalog", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_edge_kind_counts_are_sorted(self):
        edges = [
            {"kind": "branch"}, {"kind": "conditional-taken"},
            {"kind": "branch"},
        ]
        self.assertEqual(
            MODULE.edge_kinds(edges),
            {"branch": 2, "conditional-taken": 1},
        )

    def test_semantic_source_has_no_encoded_word(self):
        source = MODULE.semantic_entry_source()
        self.assertIn("b ArmBootstrap", source)
        self.assertNotIn(".word", source)
        self.assertNotIn("0x", source)


if __name__ == "__main__":
    unittest.main()
