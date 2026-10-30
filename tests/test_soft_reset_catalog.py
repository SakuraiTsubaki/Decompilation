import importlib.util,pathlib,unittest
TOOL=pathlib.Path(__file__).parents[1]/"tools/soft_reset_catalog.py";S=importlib.util.spec_from_file_location("soft_reset_catalog",TOOL);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_wrapper(self):
  b=bytes.fromhex("034b00221a7003498d4601df00df000008020004007f0003");d=M.decode_wrapper(b,0);self.assertEqual(d["reset_stack_pointer"],"0x03007F00");self.assertTrue(d["nonreturning"])
 def test_rejects_wrong_swi(self):
  b=bytearray(bytes.fromhex("034b00221a7003498d4601df00df000008020004007f0003"));b[10]=2;self.assertIsNone(M.decode_wrapper(bytes(b),0))
 def test_named_target(self):self.assertEqual(M.named_target({"calls":[{"name":"SoftReset","target":"0x08001234"}]}),0x08001234)
if __name__=="__main__":unittest.main()

