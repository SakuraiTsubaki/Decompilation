import unittest

from tools import frlg_div_variant_catalog as div


class FrlgDivVariantCatalogTests(unittest.TestCase):
    def test_locates_signature(self):
        self.assertEqual(div.locate(b"x" + div.SIGNATURE), [1])

    def test_reports_all_matches(self):
        self.assertEqual(div.locate(div.SIGNATURE * 2), [0, 4])

    def test_absence(self):
        self.assertEqual(div.locate(b"\0" * 12), [])


if __name__ == "__main__":
    unittest.main()
