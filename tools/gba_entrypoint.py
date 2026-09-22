#!/usr/bin/env python3
"""Decode and verify the ARM branch in a GBA ROM entry word."""
from __future__ import annotations
import argparse,json,struct
from pathlib import Path

def decode_entry_word(word:int,base_address:int=0x08000000)->dict:
 if word>>24 not in (0xEA,0xEB):raise ValueError("entry word is not an ARM B/BL immediate")
 displacement=word&0x00ffffff
 if displacement&0x00800000:displacement-=0x01000000
 target=(base_address+8+(displacement<<2))&0xffffffff
 return {"schema_version":1,"entry_address":base_address,"instruction_word":word,"mnemonic":"bl" if word>>24==0xEB else "b","displacement":displacement<<2,"target_address":target,"thumb":False}

def encode_branch(target_address:int,base_address:int=0x08000000,link:bool=False)->int:
 displacement=target_address-(base_address+8)
 if displacement%4:raise ValueError("ARM branch target must be word-aligned")
 immediate=displacement//4
 if not -(1<<23)<=immediate<(1<<23):raise ValueError("ARM branch target is out of range")
 return (0xEB000000 if link else 0xEA000000)|(immediate&0x00ffffff)

def analyze_rom(path:Path,expected_sha256:str|None=None)->dict:
 import hashlib
 data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
 if expected_sha256 and digest.lower()!=expected_sha256.lower():raise ValueError("SHA-256 mismatch")
 if len(data)<4:raise ValueError("ROM is shorter than the entry word")
 result=decode_entry_word(struct.unpack_from("<I",data)[0]);result.update({"source_size":len(data),"source_sha256":digest});return result

def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("rom",type=Path);p.add_argument("--expected-sha256");p.add_argument("--output",type=Path);a=p.parse_args()
 try:r=analyze_rom(a.rom,a.expected_sha256)
 except (OSError,ValueError) as e:p.error(str(e))
 text=json.dumps(r,indent=2)+"\n"
 if a.output:a.output.write_text(text,encoding="utf-8",newline="\n")
 else:print(text,end="")
 return 0
if __name__=="__main__":raise SystemExit(main())
