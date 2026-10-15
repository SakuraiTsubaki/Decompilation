import importlib.util,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/build_rng_catalog_evidence.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_file_hash(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'x';p.write_bytes(b'abc');self.assertEqual(M.file_hash(p),'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
if __name__=='__main__':unittest.main()
