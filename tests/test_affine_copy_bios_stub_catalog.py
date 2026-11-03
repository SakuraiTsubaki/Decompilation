import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/affine_copy_bios_stub_catalog.py";S=importlib.util.spec_from_file_location("affine_copy_bios_stub_catalog",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class TCase(unittest.TestCase):
 def test_signatures(self):self.assertEqual({k:v["swi"]for k,v in M.FUNCTIONS.items()},{"BgAffineSet":14,"CpuFastSet":12,"ObjAffineSet":15})
 def test_locate(self):
  signature=M.FUNCTIONS["ObjAffineSet"]["signature"];self.assertEqual(M.locate(b"x"+signature,signature),[1])
 def test_layouts(self):self.assertEqual(M.LZ_RELATIVE["rs"]["ObjAffineSet"],[8]);self.assertEqual(M.LZ_RELATIVE["emerald"]["ObjAffineSet"],[16]);self.assertEqual(M.LZ_RELATIVE["frlg"]["BgAffineSet"],[-16,-12])
if __name__=="__main__":unittest.main()
