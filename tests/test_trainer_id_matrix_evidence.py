import importlib.util,unittest
from pathlib import Path
R=Path(__file__).parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/trainer_id_matrix_evidence.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_unique_aligned_signature(self):self.assertEqual(M.unique_offset(b'xxABCDyy',b'ABCD'),2)
 def test_rejects_duplicate_or_unaligned_signature(self):
  with self.assertRaises(ValueError):M.unique_offset(b'ABCDxxABCD',b'ABCD')
  with self.assertRaises(ValueError):M.unique_offset(b'xABCD',b'ABCD')
 def test_function_slugs_cover_variants(self):self.assertEqual(M.SLUGS['GetTrainerId'],'get-trainer-id');self.assertEqual(M.SLUGS['copy_word_to_mem'],'copy-word')
if __name__=='__main__':unittest.main()
