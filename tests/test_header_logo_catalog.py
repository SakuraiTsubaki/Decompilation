import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/header_logo_catalog.py";S=importlib.util.spec_from_file_location("header_logo_catalog",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class TCase(unittest.TestCase):
 def test_constants(self):self.assertEqual((M.LOGO_OFFSET,M.LOGO_SIZE,M.WIDTH,M.HEIGHT,M.SCALE),(4,156,104,16,4))
 def test_short_logo(self):
  with self.assertRaises(ValueError):M.decode_logo(b"short")
 def test_png_chunk(self):self.assertEqual(M.chunk(b"IEND",b"")[:8],bytes.fromhex("0000000049454e44"))
if __name__=="__main__":unittest.main()
