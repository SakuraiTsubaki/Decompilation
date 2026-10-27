import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "init_heap_catalog.py"
SPEC = importlib.util.spec_from_file_location("init_heap_catalog", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_cluster_order(self):
        self.assertEqual(
            MODULE.FUNCTIONS,
            ["InitHeap", "PutFirstMemBlockHeader", "PutMemBlockHeader"],
        )

    def test_unique_named_target(self):
        address_map = {"direct_calls": [
            {"name": "InitHeap", "target": "0x08000100"},
        ]}
        self.assertEqual(MODULE.unique_named_target(address_map, "InitHeap"), 0x08000100)

    def test_profiles_are_pinned(self):
        self.assertEqual(set(MODULE.PROFILES), {"emerald", "frlg"})
        self.assertTrue(all(len(item["commit"]) == 40 for item in MODULE.PROFILES.values()))


if __name__ == "__main__":
    unittest.main()
