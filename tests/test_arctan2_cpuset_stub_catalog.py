import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/arctan2_cpuset_stub_catalog.py";S=importlib.util.spec_from_file_location("arctan2_cpuset_stub_catalog",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class TCase(unittest.TestCase):
 def test_signatures(self):self.assertEqual(M.FUNCTIONS["ArcTan2"]["swi"],10);self.assertEqual(M.FUNCTIONS["CpuSet"]["swi"],11)
 def test_duplicate_selection(self):
  sig=M.FUNCTIONS["CpuSet"]["signature"];self.assertEqual(M.locate(sig+b"x"+sig,sig),[0,5])
 def test_layouts(self):self.assertEqual(M.LZ_RELATIVE["rs"]["CpuSet"],[-4]);self.assertEqual(M.LZ_RELATIVE["emerald"]["CpuSet"],[-8]);self.assertEqual(M.LZ_RELATIVE["frlg"]["ArcTan2"],[-20,-16])
if __name__=="__main__":unittest.main()
