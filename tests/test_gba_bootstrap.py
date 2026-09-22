from __future__ import annotations
import importlib.util,struct,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location("gba_bootstrap",ROOT/"tools"/"gba_bootstrap.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class GbaBootstrapTests(unittest.TestCase):
 def fixture(self,target:int)->bytes:
  data=bytearray(0x40);struct.pack_into("<I",data,0,0xE59F1000);struct.pack_into("<I",data,4,0xE12FFF11);struct.pack_into("<I",data,8,target);return bytes(data)
 def test_thumb_transition_from_literal(self):
  r=m.trace_bootstrap(self.fixture(0x08000101),0);self.assertEqual(r["instruction_count"],2);self.assertEqual(r["transition"]["raw_target"],0x08000101);self.assertEqual(r["transition"]["target_address"],0x08000100);self.assertEqual(r["transition"]["target_state"],"thumb")
 def test_arm_transition_from_literal(self):
  self.assertEqual(m.trace_bootstrap(self.fixture(0x08000100),0)["transition"]["target_state"],"arm")
 def test_unaligned_start_is_rejected(self):
  with self.assertRaisesRegex(ValueError,"word-aligned"):m.trace_bootstrap(bytes(16),2)
 def test_missing_transition_is_rejected(self):
  with self.assertRaisesRegex(ValueError,"no literal-backed"):m.trace_bootstrap(bytes(16),0)
if __name__=="__main__":unittest.main()
