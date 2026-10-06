import importlib.util,unittest
from pathlib import Path
PATH=Path(__file__).parents[1]/'tools'/'validate_interrupt_map.py';SPEC=importlib.util.spec_from_file_location('validate_interrupt_map',PATH);MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)
def fixture():
 return {'target':{'release':'BPRJ-rev0','sha256':'a'*64},'rom_code_and_literals':{'start_offset':0x100,'end_offset_exclusive':0x160,'sha256':'b'*64,'raw_bytes_published':False},'functions':[{'name':'HBlankIntr','address':'0x08000100','range_end_exclusive':'0x08000120'},{'name':'VCountIntr','address':'0x08000130','range_end_exclusive':'0x08000150'}],'calls':[{'address':'0x08000108','target':'0x08100000','name':'callback trampoline'},{'address':'0x08000138','target':'0x08110000','name':'m4aSoundVSync'}],'proven_offsets':{'hblankCallback':16,'vcountCallback':20,'intrCheck':28}}
class Tests(unittest.TestCase):
 def test_valid_map(self):
  r=MODULE.validate(fixture());self.assertEqual(r['function_count'],2);self.assertEqual(r['call_count'],2);self.assertEqual(r['range_start'],0x08000100);self.assertFalse(r['raw_rom_bytes_included'])
 def test_identity_and_publication_guards(self):
  m=fixture();m['target']['sha256']='bad'
  with self.assertRaisesRegex(ValueError,'SHA-256'):MODULE.validate(m)
  m=fixture();m['rom_code_and_literals']['raw_bytes_published']=True
  with self.assertRaisesRegex(ValueError,'publication'):MODULE.validate(m)
 def test_ranges_and_calls(self):
  m=fixture();m['functions'][1]['address']='0x08000110'
  with self.assertRaisesRegex(ValueError,'overlap'):MODULE.validate(m)
  m=fixture();m['calls'][0]['address']='0x08000128'
  with self.assertRaisesRegex(ValueError,'outside'):MODULE.validate(m)
 def test_offsets(self):
  m=fixture();m['proven_offsets']['vcountCallback']=16
  with self.assertRaisesRegex(ValueError,'unique'):MODULE.validate(m)
if __name__=='__main__':unittest.main()

