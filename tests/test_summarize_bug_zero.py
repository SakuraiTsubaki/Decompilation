from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from scripts.summarize_bug_zero import summarize


REGISTRY = """id,targets,category,name,affected_scope,upstream_fix,status,source,notes
A,Scarlet|Violet,battle,Open bug,all,,REPRODUCED,test,
B,Scarlet,data,Closed bug,all,,CLOSED,test,
C,Violet,ui,Violet bug,all,,PATCHED,test,
D,Z-A,mission,Intentional quirk,all,,INTENDED_QUIRK,test,
"""


class SummarizeBugZeroTests(unittest.TestCase):
    def write_registry(self, root: Path) -> Path:
        path = root / "registry.csv"
        path.write_text(REGISTRY, encoding="utf-8")
        return path

    def test_scarlet_counts_open_and_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = summarize(self.write_registry(Path(directory)), "Scarlet")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["terminal"], 1)
        self.assertEqual(result["blocking"], 1)
        self.assertEqual(result["blockers"][0]["id"], "A")

    def test_violet_includes_shared_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            result = summarize(self.write_registry(Path(directory)), "Violet")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["blocking"], 2)
        self.assertEqual(set(result["status_counts"]), {"PATCHED", "REPRODUCED"})

    def test_intended_quirk_is_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            result = summarize(self.write_registry(Path(directory)), "Z-A")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["terminal"], 1)
        self.assertEqual(result["blocking"], 0)


if __name__ == "__main__":
    unittest.main()
