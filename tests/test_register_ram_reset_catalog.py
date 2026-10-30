import importlib.util,pathlib,unittest
TOOL=pathlib.Path(__file__).parents[1]/"tools/register_ram_reset_catalog.py";SPEC=importlib.util.spec_from_file_location("register_ram_reset_catalog",TOOL);M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
class RegisterRamResetCatalogTests(unittest.TestCase):
 def test_wrapper(self):
  self.assertEqual(M.decode_wrapper(bytes.fromhex("01df7047"),0)["software_interrupt"],1)
  self.assertIsNone(M.decode_wrapper(bytes.fromhex("00df7047"),0))
 def test_named_target(self):
  self.assertEqual(M.named_target({"direct_calls":[{"name":"RegisterRamReset","target":"0x08001234"}]}),0x08001234)
 def test_profiles_are_pinned(self):
  self.assertTrue(all(len(x["commit"])==40 for x in M.PROFILES.values()))
if __name__=="__main__":unittest.main()

