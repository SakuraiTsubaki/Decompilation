#!/usr/bin/env python3
"""Verify the SoftReset SDK wrapper across Gen III release catalogs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import register_ram_reset_catalog as common

ROUTINE_LENGTH=24
HALFWORDS=[0x4B03,0x2200,0x701A,0x4903,0x468D,0xDF01,0xDF00,0x0000]
REG_IME=0x04000208
RESET_STACK=0x03007F00

def named_target(evidence:dict)->int:
 targets={int(c["target"],16) for c in evidence["calls"] if c["name"]=="SoftReset"}
 if len(targets)!=1:raise ValueError(f"expected one SoftReset target, found {len(targets)}")
 return targets.pop()
def decode_wrapper(data:bytes,offset:int)->dict|None:
 code=data[offset:offset+ROUTINE_LENGTH]
 if len(code)!=ROUTINE_LENGTH:return None
 values=[int.from_bytes(code[i:i+2],"little") for i in range(0,16,2)]
 if values!=HALFWORDS:return None
 if int.from_bytes(code[16:20],"little")!=REG_IME or int.from_bytes(code[20:24],"little")!=RESET_STACK:return None
 return {"length":24,"instruction_halfwords":7,"literal_pool_bytes":8,
         "interrupt_master_enable_address":f"0x{REG_IME:08X}","interrupt_master_enable_value":0,
         "reset_stack_pointer":f"0x{RESET_STACK:08X}","register_ram_reset_swi":1,
         "soft_reset_swi":0,"reset_flags_register":"r0","nonreturning":True}
def source_text()->str:
 return '''.syntax unified
.thumb

.global SoftReset
.type SoftReset, %function
SoftReset:
    ldr r3, .LRegIme
    movs r2, #0
    strb r2, [r3]
    ldr r1, .LResetStack
    mov sp, r1
    swi 1
    swi 0
    .align 2
.LRegIme:
    .word 0x04000208
.LResetStack:
    .word 0x03007F00
.size SoftReset, . - SoftReset
'''
def build(root:Path,rom_dir:Path,catalog_path:Path,game:str,family:str)->dict:
 profile=common.PROFILES[family];catalog=json.loads((root/catalog_path).read_text(encoding="utf-8"));releases=catalog["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with Japanese origin")
 source_path=Path("src/soft_reset.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n")
 roms=common.rom_index(rom_dir);maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  caller_path=Path(f"analysis/{rid}-do-soft-reset-map.json");caller=json.loads((root/caller_path).read_text(encoding="utf-8"));address=named_target(caller)
  data=roms[sha256].read_bytes();offset=address-common.ROM_BASE;decoded=decode_wrapper(data,offset)
  if decoded is None:raise ValueError(f"SoftReset wrapper differs: {rid}")
  code=data[offset:offset+ROUTINE_LENGTH]
  evidence={"schema_version":1,"axis":"Decompilation","target":{"release":rid,"sha256":sha256,"build_kind":release["build_kind"]},"origin_reference":index==0,
   "function":{"name":"SoftReset","address":f"0x{address:08X}","range_end_exclusive":f"0x{address+ROUTINE_LENGTH:08X}","source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"rom_code_range":{"start_offset":offset,"end_offset_exclusive":offset+ROUTINE_LENGTH,"length":ROUTINE_LENGTH,"sha256":common.digest(code),"raw_bytes_published":False}},
   "verified_behavior":decoded,"cross_reference":{"do_soft_reset_map":caller_path.as_posix(),"do_soft_reset_map_sha256":common.file_hash(root/caller_path)},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-soft-reset-map.json");common.write_json(root/map_path,evidence);maps.append(map_path)
  records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,"address":evidence["function"]["address"],"code_sha256":common.digest(code),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Decompilation","game":game,"function":"SoftReset","family_profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False}
 summary_path=Path("analysis/soft-reset-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/soft-reset-reconstruction.md")
 (root/research_path).write_text(f"# {game} SoftReset reconstruction\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) resolve DoSoftReset to the same SDK wrapper. It disables REG_IME, moves SP to 0x03007F00, invokes BIOS RegisterRamReset through SWI 1 with flags in r0, then performs the non-returning SWI 0 soft reset. Maps preserve addresses, decoded behavior and hashes without ROM bytes or instruction dumps.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_soft_reset_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix() for p in outputs if not (root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/soft-reset-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"function":"SoftReset","origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/soft_reset_catalog.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False})
 return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(common.PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())

