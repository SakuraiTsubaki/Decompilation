import importlib.util,struct,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/rng2_evidence.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_locate_unique_even_pattern(self):
  d=bytearray(12);d[4:8]=struct.pack('<2H',1,2);self.assertEqual(M.locate(bytes(d),(1,2)),4)
 def test_rejects_duplicates(self):
  with self.assertRaises(ValueError):M.locate(struct.pack('<3H',1,1,0),(1,))
 def test_rejects_absent(self):
  with self.assertRaises(ValueError):M.locate(b'\0'*8,(1,))
 def test_rejects_missing_adjacent_random2(self):
  data=bytearray(64);data[0:len(M.SEED_PATTERN)*2]=struct.pack(f'<{len(M.SEED_PATTERN)}H',*M.SEED_PATTERN)
  with self.assertRaises(ValueError):M.analyze(bytes(data))
if __name__=='__main__':unittest.main()
