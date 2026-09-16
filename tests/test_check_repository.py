from pathlib import Path
import tempfile
import unittest

from scripts.check_repository import BLOCKED_SUFFIXES, REQUIRED_PATHS, validate


class RepositoryValidationTests(unittest.TestCase):
    def make_valid_tree(self, root: Path) -> None:
        for relative in REQUIRED_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("valid\n", encoding="utf-8")

    def test_valid_tree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_valid_tree(root)
            self.assertEqual(validate(root), [])

    def test_blocked_binary_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_valid_tree(root)
            suffix = sorted(BLOCKED_SUFFIXES)[0]
            (root / f"sample{suffix}").write_bytes(b"not a real image")
            self.assertTrue(any("blocked binary" in item for item in validate(root)))

    def test_trailing_whitespace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_valid_tree(root)
            (root / "README.md").write_text("bad \n", encoding="utf-8")
            self.assertTrue(any("trailing whitespace" in item for item in validate(root)))


if __name__ == "__main__":
    unittest.main()
