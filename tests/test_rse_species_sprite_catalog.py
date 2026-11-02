import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/rse_species_sprite_catalog.py";S=importlib.util.spec_from_file_location("rse_species_sprite_catalog",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class TCase(unittest.TestCase):
 def test_lz_literals(self):
  raw,used=M.decompress(bytes.fromhex("100400000041424344"),0);self.assertEqual(raw,b"ABCD");self.assertEqual(used,9)
 def test_palette(self):
  out,colors=M.palette(b"\0\0"*16);self.assertTrue(out.startswith(b"JASC-PAL\n0100\n16\n"));self.assertEqual(colors,[(0,0,0)]*16)
 def test_png(self):self.assertTrue(M.render(bytes(0x800),[(0,0,0)]*16).startswith(b"\x89PNG\r\n\x1a\n"))
if __name__=="__main__":unittest.main()
