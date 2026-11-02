import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/lz77_bios_stub_catalog.py";S=importlib.util.spec_from_file_location("lz77_bios_stub_catalog",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class TCase(unittest.TestCase):
 def test_suite(self):self.assertEqual(M.locate(b"x"+M.SUITE_SIGNATURE),[1]);self.assertEqual(M.SUITE_LENGTH,8)
 def test_bios_numbers(self):self.assertEqual(M.VRAM_SIGNATURE,bytes.fromhex("12df7047"));self.assertEqual(M.WRAM_SIGNATURE,bytes.fromhex("11df7047"))
 def test_paths(self):self.assertEqual(set(M.PATHS),{"rs","emerald","frlg"})
if __name__=="__main__":unittest.main()
