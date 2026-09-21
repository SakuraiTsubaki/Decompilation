from __future__ import annotations
import importlib.util,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location("gba_entrypoint",ROOT/"tools"/"gba_entrypoint.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class GbaEntrypointTests(unittest.TestCase):
 def test_ruby_entry_branch(self):
  r=m.decode_entry_word(0xEA000032);self.assertEqual(r["mnemonic"],"b");self.assertEqual(r["target_address"],0x080000D0);self.assertEqual(r["displacement"],0xC8);self.assertEqual(m.encode_branch(r["target_address"]),r["instruction_word"])
 def test_emerald_entry_branch(self):
  r=m.decode_entry_word(0xEA00007F);self.assertEqual(r["target_address"],0x08000204);self.assertEqual(m.encode_branch(r["target_address"]),r["instruction_word"])
 def test_negative_displacement(self):
  self.assertEqual(m.decode_entry_word(0xEAFFFFFF)["target_address"],0x08000004)
 def test_non_branch_rejected(self):
  with self.assertRaisesRegex(ValueError,"not an ARM"):m.decode_entry_word(0)
 def test_unaligned_and_out_of_range_targets_are_rejected(self):
  with self.assertRaisesRegex(ValueError,"word-aligned"):m.encode_branch(0x08000001)
  with self.assertRaisesRegex(ValueError,"out of range"):m.encode_branch(0x0c000008)
 def test_hash_gate(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"x.gba";p.write_bytes((0xEA000032).to_bytes(4,"little"))
   with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):m.analyze_rom(p,"00"*32)
if __name__=="__main__":unittest.main()
