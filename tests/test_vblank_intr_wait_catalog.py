import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/vblank_intr_wait_catalog.py";S=importlib.util.spec_from_file_location("vblank_intr_wait_catalog",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class VBlankIntrWaitCatalogTests(unittest.TestCase):
 def test_wrapper(self):self.assertEqual(M.decode_wrapper(bytes.fromhex("002205df7047"),0)["software_interrupt"],5)
 def test_rejects_wrong_swi(self):self.assertIsNone(M.decode_wrapper(bytes.fromhex("002204df7047"),0))
 def test_requires_bios_call_variant(self):
  with self.assertRaises(ValueError):M.named_target({"wait":{"mode":"volatile-poll","call":None}})
if __name__=="__main__":unittest.main()

