#!/usr/bin/env python3
"""Reconstruct the libgcc Thumb _call_via_rX suite across Gen III catalogs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import register_ram_reset_catalog as common

FUNCTIONS=[*((f"_call_via_r{i}",f"r{i}",i)for i in range(10)),("_call_via_sl","sl",10),("_call_via_fp","fp",11),("_call_via_ip","ip",12),("_call_via_sp","sp",13),("_call_via_lr","lr",14)]
FUNCTION_LENGTH=4
RESET_TO_SUITE_DELTA=40
SQRT_SIGNATURE=bytes.fromhex("08df7047")
VBLANK_SIGNATURE=bytes.fromhex("002205df7047")
ALIGNMENT_PADDING=bytes.fromhex("0000")
NOP=bytes.fromhex("c046")
LINKER_PATHS={"rs":"ld_script.txt","emerald":"ld_script.ld","frlg":"ld_script.ld"}
def encoding(register:int)->bytes:return(0x4700+(register<<3)).to_bytes(2,"little")+NOP
SUITE_SIGNATURE=b"".join(encoding(number)for _,_,number in FUNCTIONS)
SUITE_LENGTH=len(SUITE_SIGNATURE)
def locate(data:bytes)->list[int]:
 out=[];start=0
 while True:
  start=data.find(SUITE_SIGNATURE,start)
  if start<0:return out
  out.append(start);start+=1
def source_text()->str:
 lines=[".syntax unified",".thumb","",".balign 4, 0"]
 for name,register,_ in FUNCTIONS:lines += [f".global {name}",f".type {name}, %function",f"{name}:",f"    bx {register}","    nop",f".size {name}, . - {name}",""]
 return "\n".join(lines)
def build(root:Path,rom_dir:Path,catalog_path:Path,game:str,family:str)->dict:
 profile=common.PROFILES[family];catalog=json.loads((root/catalog_path).read_text(encoding="utf-8"));releases=catalog["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with Japanese origin")
 source_path=Path("src/call_via_stubs.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");roms=common.rom_index(rom_dir);maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  reset_path=Path(f"analysis/{rid}-register-ram-reset-map.json");reset=json.loads((root/reset_path).read_text(encoding="utf-8"));reset_start=int(reset["function"]["rom_code_range"]["start_offset"])
  soft_path=Path(f"analysis/{rid}-soft-reset-map.json");soft=json.loads((root/soft_path).read_text(encoding="utf-8"));soft_start=int(soft["function"]["rom_code_range"]["start_offset"])
  data=roms[sha256].read_bytes();start=reset_start+RESET_TO_SUITE_DELTA;matches=locate(data)
  if soft_start!=reset_start+4 or start not in matches:raise ValueError(f"SDK runtime layout differs: {rid}")
  if data[reset_start+28:reset_start+32]!=SQRT_SIGNATURE or data[reset_start+32:reset_start+38]!=VBLANK_SIGNATURE or data[reset_start+38:start]!=ALIGNMENT_PADDING:raise ValueError(f"intervening SDK stubs differ: {rid}")
  functions={}
  for ordinal,(name,register,number) in enumerate(FUNCTIONS):
   offset=start+ordinal*FUNCTION_LENGTH;chunk=data[offset:offset+FUNCTION_LENGTH]
   if chunk!=encoding(number):raise ValueError(f"call-via encoding differs: {rid} {name}")
   functions[name]={"address":f"0x{common.ROM_BASE+offset:08X}","rom_offset":offset,"range_end_exclusive":f"0x{common.ROM_BASE+offset+FUNCTION_LENGTH:08X}","length":FUNCTION_LENGTH,"code_sha256":common.digest(chunk),"branch_exchange_register":register,"register_number":number,"trailing_instruction":"nop"}
  evidence={"schema_version":1,"axis":"Decompilation","target":{"release":rid,"sha256":sha256,"build_kind":release["build_kind"]},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"functions":functions,"verified_layout":{"function_count":len(FUNCTIONS),"suite_length":SUITE_LENGTH,"word_aligned":start%4==0,"register_ram_reset_to_suite_delta":RESET_TO_SUITE_DELTA,"suite_signature_match_count":len(matches),"selected_by_verified_sdk_layout":True,"intervening_functions":["SoftReset","Sqrt","VBlankIntrWait"]},"cross_reference":{"register_ram_reset_map":reset_path.as_posix(),"register_ram_reset_map_sha256":common.file_hash(root/reset_path),"soft_reset_map":soft_path.as_posix(),"soft_reset_map_sha256":common.file_hash(root/soft_path)},"naming_basis":{**profile,"path":LINKER_PATHS[family],"section_pattern":"libgcc.a:_call_via_rX.o(.text)"},"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-call-via-map.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,"suite_address":f"0x{common.ROM_BASE+start:08X}","suite_sha256":common.digest(data[start:start+SUITE_LENGTH]),"signature_match_count":len(matches),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Decompilation","game":game,"library":"libgcc","object":"_call_via_rX.o","family_profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"function_count":len(FUNCTIONS),"functions":[x[0]for x in FUNCTIONS],"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/call-via-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"]for x in records));duplicates=sum(x["signature_match_count"]>1 for x in records);research_path=Path("research/call-via-reconstruction.md");(root/research_path).write_text(f"# {game} libgcc call-via reconstruction\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged builds ({languages}) independently verify the word-aligned `_call_via_rX` suite at +40 bytes from RegisterRamReset, after SoftReset, Sqrt, VBlankIntrWait, and alignment padding. Its 15 four-byte Thumb trampolines branch through r0-r9, sl, fp, ip, sp, and lr, with a trailing `nop`. The pinned upstream linker script places `libgcc.a:_call_via_rX.o(.text)` here. {duplicates} build(s) contain a second byte-identical suite, so selection uses the verified SDK layout. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_call_via_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/call-via-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"library":"libgcc","object":"_call_via_rX.o","origin_reference":releases[0]["id"],"release_count":len(records),"function_count":len(FUNCTIONS),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/call_via_catalog.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)}for p in outputs],"raw_rom_bytes_included":False})
 return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(common.PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
