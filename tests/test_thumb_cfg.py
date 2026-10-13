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
 def test_pop_then_bx_same_register_is_return(self):
  r=m.trace_thumb_function(self.pack(0xBC01,0x4700,0xF000,0xF800),0)
  self.assertEqual(r["returns"],[0x08000002]);self.assertEqual(r["range_end"],0x08000004);self.assertEqual(r["calls"],[])
 def test_pop_then_bx_different_register_is_not_return(self):
  r=m.trace_thumb_function(self.pack(0xBC01,0x4708,0x4770),0)
  self.assertEqual(r["returns"],[0x08000004])
 def test_agbcc_absolute_word_jump_table(self):
  # cmp r1,#2; bhi default; lsls r0,r1,#2; load table address; index it;
  # load an absolute code address; mov pc,r0. Literal data must not be decoded.
  code=bytearray(0x34)
  struct.pack_into("<7H",code,0,0x2902,0xD815,0x0088,0x4902,0x1840,0x6800,0x4687)
  struct.pack_into("<I",code,0x10,0x08000018)
  struct.pack_into("<3I",code,0x18,0x08000028,0x0800002A,0x0800002C)
  struct.pack_into("<3H",code,0x28,0x4770,0x4770,0x4770)
  struct.pack_into("<H",code,0x30,0x4770)
  r=m.trace_thumb_function(bytes(code),0,max_span=len(code))
  jump=next(i for i in r["instructions"] if i["kind"]=="jump-table-branch")
  self.assertEqual(jump["table_address"],0x08000018)
  self.assertEqual(jump["targets"],[0x08000028,0x0800002A,0x0800002C])
  self.assertEqual({e["case"] for e in r["edges"] if e["kind"]=="jump-table"},{0,1,2})
  self.assertNotIn(0x08000018,{i["address"] for i in r["instructions"]})
  self.assertEqual(r["returns"],[0x08000028,0x0800002A,0x0800002C,0x08000030])
 def test_publishable_report_omits_halfwords(self):
  report={"instructions":[{"address":0x08000000,"halfword":0x4770,"kind":"return"}],"edges":[]}
  clean=m.omit_raw_halfwords(report)
  self.assertNotIn("halfword",clean["instructions"][0]);self.assertTrue(clean["raw_halfwords_omitted"])
  self.assertIn("halfword",report["instructions"][0])
if __name__=="__main__":unittest.main()
