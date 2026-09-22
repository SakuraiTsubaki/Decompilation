from __future__ import annotations
import importlib.util,struct,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location("thumb_cfg",ROOT/"tools"/"thumb_cfg.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ThumbCfgTests(unittest.TestCase):
 def pack(self,*values):return struct.pack("<"+"H"*len(values),*values)
 def test_conditional_paths_reach_return(self):
  r=m.trace_thumb_function(self.pack(0xD001,0x2000,0xBD00,0x4770),0);self.assertEqual(len(r["returns"]),2);self.assertEqual({e["kind"] for e in r["edges"]},{"conditional-taken","conditional-fallthrough"})
 def test_bl_is_recorded_but_not_followed(self):
  r=m.trace_thumb_function(self.pack(0xF000,0xF800,0x4770),0);self.assertEqual(r["calls"][0]["target"],0x08000004);self.assertEqual(r["returns"],[0x08000004])
 def test_unconditional_branch_skips_data(self):
  r=m.trace_thumb_function(self.pack(0xE001,0xFFFF,0xFFFF,0x4770),0);self.assertEqual(r["instruction_halfwords"],2)
 def test_missing_return_is_recorded(self):
  r=m.trace_thumb_function(self.pack(0x2000,0x2000),0,max_span=4);self.assertFalse(r["return_observed"]);self.assertEqual(r["scan_limit_address"],0x08000004)
if __name__=="__main__":unittest.main()

