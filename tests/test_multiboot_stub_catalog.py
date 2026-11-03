import unittest
from tools import multiboot_stub_catalog as M
class MultiBootStubCatalogTests(unittest.TestCase):
 def test_signature(self):self.assertEqual(M.SIGNATURE,bytes.fromhex("012125df7047"));self.assertEqual(M.FUNCTION_LENGTH,6)
 def test_locate(self):self.assertEqual(M.locate(M.SIGNATURE+b"x"+M.SIGNATURE),[0,7])
 def test_layouts(self):self.assertEqual(M.LZ_RELATIVE,{"emerald":8,"frlg":8})
if __name__=="__main__":unittest.main()
