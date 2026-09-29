#!/usr/bin/env python3
"""Build a conservative Thumb-1 direct control-flow graph from a ROM function."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

def sign_extend(value:int,bits:int)->int:
 sign=1<<(bits-1);return (value^sign)-sign

def trace_thumb_function(data:bytes,start_offset:int,rom_base:int=0x08000000,max_span:int=0x4000)->dict:
 if start_offset<0 or start_offset%2:raise ValueError("start offset must be nonnegative and halfword-aligned")
 limit=min(len(data),start_offset+max_span);queue=[start_offset];visited=set();instructions={};edges=[];returns=[];calls=[]
 def add_edge(source:int,target:int,kind:str):
  if not start_offset<=target<limit or target%2:raise ValueError(f"{kind} target leaves function scan window")
  edges.append({"source":rom_base+source,"target":rom_base+target,"kind":kind});queue.append(target)
 while queue:
  offset=queue.pop()
  while offset not in visited:
   if offset==limit:break
   if not start_offset<=offset<=limit-2:raise ValueError("control flow leaves function scan window")
   visited.add(offset);h=struct.unpack_from("<H",data,offset)[0];address=rom_base+offset;item={"address":address,"halfword":h,"kind":"other"};instructions[offset]=item
   if h&0xff00==0xbd00 or h==0x4770:
    item["kind"]="return";returns.append(address);break
   if h&0xf800==0xf000:
    if offset+4>len(data):raise ValueError("truncated Thumb BL")
    h2=struct.unpack_from("<H",data,offset+2)[0]
    if h2&0xf800!=0xf800:raise ValueError("unsupported Thumb long-branch prefix")
    visited.add(offset+2);instructions[offset+2]={"address":address+2,"halfword":h2,"kind":"bl-suffix"};delta=sign_extend(((h&0x7ff)<<12)|((h2&0x7ff)<<1),23);target=address+4+delta;item.update({"kind":"call","target":target});calls.append({"source":address,"target":target});offset+=4;continue
   if h&0xf800==0xe000:
    target=offset+4+(sign_extend(h&0x7ff,11)<<1);item.update({"kind":"branch","target":rom_base+target});add_edge(offset,target,"branch");break
   if h&0xf000==0xd000 and h&0x0f00!=0x0f00:
    target=offset+4+(sign_extend(h&0xff,8)<<1);item.update({"kind":"conditional-branch","target":rom_base+target});add_edge(offset,target,"conditional-taken");edges.append({"source":address,"target":address+2,"kind":"conditional-fallthrough"});offset+=2;continue
   offset+=2
 ordered=[instructions[x] for x in sorted(instructions)];return {"schema_version":1,"rom_base":rom_base,"start_offset":start_offset,"start_address":rom_base+start_offset,"scan_limit_address":rom_base+limit,"instruction_halfwords":len(ordered),"range_start":ordered[0]["address"],"range_end":ordered[-1]["address"]+2,"return_observed":bool(returns),"instructions":ordered,"edges":edges,"calls":calls,"returns":sorted(returns)}

def analyze_rom(path:Path,start_offset:int,expected_sha256:str|None=None,max_span:int=0x4000)->dict:
 data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
 if expected_sha256 and digest.lower()!=expected_sha256.lower():raise ValueError("SHA-256 mismatch")
 result=trace_thumb_function(data,start_offset,max_span=max_span);result.update({"source_size":len(data),"source_sha256":digest});return result

def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("rom",type=Path);p.add_argument("--start-offset",type=lambda x:int(x,0),required=True);p.add_argument("--expected-sha256");p.add_argument("--max-span",type=lambda x:int(x,0),default=0x4000);p.add_argument("--output",type=Path);a=p.parse_args()
 try:r=analyze_rom(a.rom,a.start_offset,a.expected_sha256,a.max_span)
 except (OSError,ValueError) as e:p.error(str(e))
 text=json.dumps(r,indent=2)+"\n"
 if a.output:a.output.write_text(text,encoding="utf-8",newline="\n")
 else:print(text,end="")
 return 0
if __name__=="__main__":raise SystemExit(main())

