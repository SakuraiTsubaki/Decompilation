from pathlib import Path
import tempfile
import unittest

from scripts.check_repository import REQUIRED_PATHS, ROM_BINARY_SUFFIXES, validate


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

    def test_rom_binary_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_valid_tree(root)
            suffix = sorted(ROM_BINARY_SUFFIXES)[0]
            (root / f"sample{suffix}").write_bytes(b"not a real ROM")
            self.assertTrue(any("blocked ROM binary" in item for item in validate(root)))

    def test_trailing_whitespace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_valid_tree(root)
            (root / "README.md").write_text("bad \n", encoding="utf-8")
            self.assertTrue(any("trailing whitespace" in item for item in validate(root)))

    def test_graphics_data_requires_png(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_valid_tree(root)
            graphics = root / "artifacts" / "graphics" / "example"
            graphics.mkdir(parents=True)
            (graphics / "palette.json").write_text("{}\n", encoding="utf-8")
            self.assertTrue(any("no PNG preview" in item for item in validate(root)))

    def test_graphics_data_with_png_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_valid_tree(root)
            graphics = root / "artifacts" / "graphics" / "example"
            graphics.mkdir(parents=True)
            (graphics / "palette.json").write_text("{}\n", encoding="utf-8")
            (graphics / "preview.png").write_bytes(b"PNG fixture")
            self.assertEqual(validate(root), [])


if __name__ == "__main__":
    unittest.main()
