from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
import unittest

from scripts.inventory_switch_target import inventory


class InventorySwitchTargetTests(unittest.TestCase):
    def test_single_file_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "sample.bin"
            target.write_bytes(b"abc")
            result = inventory(target, "sample")

        self.assertEqual(result["input_type"], "file")
        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["total_size"], 3)
        self.assertEqual(result["label"], "sample")
        self.assertEqual(result["files"][0]["path"], "sample.bin")
        self.assertEqual(
            result["files"][0]["sha256"], hashlib.sha256(b"abc").hexdigest()
        )

    def test_directory_inventory_is_sorted_and_recursive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b.bin").write_bytes(b"b")
            (root / "sub").mkdir()
            (root / "sub" / "a.bin").write_bytes(b"aa")
            result = inventory(root)

        self.assertEqual(result["input_type"], "directory")
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["total_size"], 3)
        self.assertEqual(
            [entry["path"] for entry in result["files"]],
            ["b.bin", "sub/a.bin"],
        )


if __name__ == "__main__":
    unittest.main()
