import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/call_via_catalog.py";S=importlib.util.spec_from_file_location("call_via_catalog",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class TCase(unittest.TestCase):
 def test_suite(self):self.assertEqual(len(M.FUNCTIONS),15);self.assertEqual(M.SUITE_LENGTH,60);self.assertEqual(M.locate(b"x"+M.SUITE_SIGNATURE),[1])
 def test_encodings(self):self.assertEqual(M.encoding(0),bytes.fromhex("0047c046"));self.assertEqual(M.encoding(14),bytes.fromhex("7047c046"))
 def test_layout(self):self.assertEqual(M.RESET_TO_SUITE_DELTA,40);self.assertEqual(M.SQRT_SIGNATURE+M.VBLANK_SIGNATURE+M.ALIGNMENT_PADDING,bytes.fromhex("08df7047002205df70470000"))
if __name__=="__main__":unittest.main()
