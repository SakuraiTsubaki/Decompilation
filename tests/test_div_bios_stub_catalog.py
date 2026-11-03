import unittest
from tools import div_bios_stub_catalog as M
class DivBiosStubCatalogTests(unittest.TestCase):
 def test_signature(self):self.assertEqual(M.SIGNATURE,bytes.fromhex("06df7047"))
 def test_locate(self):self.assertEqual(M.locate(b"x"+M.SIGNATURE),[1])
 def test_layout(self):self.assertEqual(M.LZ_RELATIVE,-4)
if __name__=="__main__":unittest.main()
