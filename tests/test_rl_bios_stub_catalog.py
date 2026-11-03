import unittest
from tools import rl_bios_stub_catalog as M
class RlBiosStubCatalogTests(unittest.TestCase):
 def test_signatures(self):self.assertEqual({k:v["swi"] for k,v in M.FUNCTIONS.items()},{"RLUnCompVram":0x15,"RLUnCompWram":0x14})
 def test_locate(self):self.assertEqual(M.locate(b"x"+bytes.fromhex("14df7047")+b"y",bytes.fromhex("14df7047")),[1])
 def test_layouts(self):self.assertEqual(M.LZ_RELATIVE["rs"]["RLUnCompWram"],16);self.assertEqual(M.LZ_RELATIVE["emerald"]["RLUnCompVram"],20)
if __name__=="__main__":unittest.main()
