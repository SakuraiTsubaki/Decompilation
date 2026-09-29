#!/usr/bin/env python3
"""Trace the initial ARM bootstrap through its first register-indirect branch."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

def trace_bootstrap(data:bytes,start_offset:int,rom_base:int=0x08000000,max_words:int=64)->dict:
 if start_offset<0 or start_offset%4:raise ValueError("start offset must be nonnegative and word-aligned")
 if start_offset+4>len(data):raise ValueError("start offset is outside the ROM")
 loads={};instructions=[];transition=None
 for index in range(max_words):
  offset=start_offset+index*4
  if offset+4>len(data):break
  word=struct.unpack_from("<I",data,offset)[0];address=rom_base+offset;item={"address":address,"word":word,"kind":"other"}
  if word&0x0ffffff0==0x012fff10:
   register=word&15;item.update({"kind":"bx","register":register})
   source=loads.get(register)
   if source:
    value=source["value"];transition={"instruction_address":address,"register":register,"loaded_at":source["instruction_address"],"literal_address":source["literal_address"],"raw_target":value,"target_address":value&~1,"target_state":"thumb" if value&1 else "arm"}
   instructions.append(item);break
  if word&0x0e5f0000==0x041f0000 and word&(1<<20):
   register=(word>>12)&15;immediate=word&0xfff;up=bool(word&(1<<23));literal_address=address+8+(immediate if up else -immediate);literal_offset=literal_address-rom_base
   if not 0<=literal_offset<=len(data)-4:raise ValueError("literal load points outside the ROM")
   value=struct.unpack_from("<I",data,literal_offset)[0];item.update({"kind":"ldr-literal","register":register,"literal_address":literal_address,"value":value});loads[register]={"instruction_address":address,"literal_address":literal_address,"value":value}
  elif word&0x0f000000 in (0x0a000000,0x0b000000):item["kind"]="branch-immediate"
  instructions.append(item)
 if transition is None:raise ValueError("no literal-backed BX transition found within scan limit")
 return {"schema_version":1,"rom_base":rom_base,"start_offset":start_offset,"start_address":rom_base+start_offset,"instruction_count":len(instructions),"instructions":instructions,"transition":transition}

def analyze_rom(path:Path,start_offset:int,expected_sha256:str|None=None,max_words:int=64)->dict:
 data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
 if expected_sha256 and digest.lower()!=expected_sha256.lower():raise ValueError("SHA-256 mismatch")
 result=trace_bootstrap(data,start_offset,max_words=max_words);result.update({"source_size":len(data),"source_sha256":digest});return result

def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("rom",type=Path);p.add_argument("--start-offset",type=lambda x:int(x,0),required=True);p.add_argument("--expected-sha256");p.add_argument("--max-words",type=int,default=64);p.add_argument("--output",type=Path);a=p.parse_args()
 try:r=analyze_rom(a.rom,a.start_offset,a.expected_sha256,a.max_words)
 except (OSError,ValueError) as e:p.error(str(e))
 text=json.dumps(r,indent=2)+"\n"
 if a.output:a.output.write_text(text,encoding="utf-8",newline="\n")
 else:print(text,end="")
 return 0
if __name__=="__main__":raise SystemExit(main())
