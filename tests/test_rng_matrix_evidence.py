import importlib.util,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'));S=importlib.util.spec_from_file_location('m',ROOT/'tools/rng_matrix_evidence.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_locates_one_even_pattern(self):
  p=(0x1234,0xabcd);d=bytearray(20);d[6:10]=struct.pack('<2H',*p);self.assertEqual(M.locate_pattern(bytes(d),p),6)
 def test_rejects_duplicate_pattern(self):
  p=(0x1234,);d=struct.pack('<3H',0x1234,0,0x1234)
  with self.assertRaises(ValueError):M.locate_pattern(d,p)
 def test_rejects_absent_pattern(self):
  with self.assertRaises(ValueError):M.locate_pattern(b'\0'*8,(0x1234,))
 def test_lists_duplicate_patterns_for_pairing(self):
  p=(0x1234,);d=struct.pack('<3H',0x1234,0,0x1234);self.assertEqual(M.locate_patterns(d,p),[0,4])
if __name__=='__main__':unittest.main()
