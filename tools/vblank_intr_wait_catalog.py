#!/usr/bin/env python3
"""Verify the VBlankIntrWait SDK wrapper used by Ruby and Sapphire."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import register_ram_reset_catalog as common

ROUTINE_LENGTH=6
PROFILE=common.PROFILES["rs"]
def named_target(mapping:dict)->int:
 call=mapping["wait"]["call"]
 if mapping["wait"]["mode"]!="bios-call" or not call or call["name"]!="VBlankIntrWait":raise ValueError("WaitForVBlank is not the BIOS-call variant")
 return int(call["target"],16)
def decode_wrapper(data:bytes,offset:int)->dict|None:
 code=data[offset:offset+ROUTINE_LENGTH]
 if code!=bytes.fromhex("002205df7047"):return None
 return {"length":6,"instruction_halfwords":3,"temporary_register":"r2","temporary_value":0,"software_interrupt":5,"return_instruction":"bx lr"}
def source_text()->str:
 return '''.syntax unified
.thumb

.global VBlankIntrWait
.type VBlankIntrWait, %function
VBlankIntrWait:
    movs r2, #0
    swi 5
    bx lr
.size VBlankIntrWait, . - VBlankIntrWait
'''
def build(root:Path,rom_dir:Path,catalog_path:Path,game:str)->dict:
 catalog=json.loads((root/catalog_path).read_text(encoding="utf-8"));releases=catalog["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with Japanese origin")
 source_path=Path("src/vblank_intr_wait.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");roms=common.rom_index(rom_dir);maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  caller_path=Path(f"analysis/{rid}-wait-for-vblank-map.json");caller=json.loads((root/caller_path).read_text(encoding="utf-8"));address=named_target(caller)
  data=roms[sha256].read_bytes();offset=address-common.ROM_BASE;decoded=decode_wrapper(data,offset)
  if decoded is None:raise ValueError(f"VBlankIntrWait wrapper differs: {rid}")
  code=data[offset:offset+ROUTINE_LENGTH]
  evidence={"schema_version":1,"axis":"Decompilation","target":{"release":rid,"sha256":sha256,"build_kind":release["build_kind"]},"origin_reference":index==0,
   "function":{"name":"VBlankIntrWait","address":f"0x{address:08X}","range_end_exclusive":f"0x{address+ROUTINE_LENGTH:08X}","source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"rom_code_range":{"start_offset":offset,"end_offset_exclusive":offset+ROUTINE_LENGTH,"length":ROUTINE_LENGTH,"sha256":common.digest(code),"raw_bytes_published":False}},
   "verified_behavior":decoded,"cross_reference":{"wait_for_vblank_map":caller_path.as_posix(),"wait_for_vblank_map_sha256":common.file_hash(root/caller_path)},"naming_basis":PROFILE,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-vblank-intr-wait-map.json");common.write_json(root/map_path,evidence);maps.append(map_path)
  records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,"address":evidence["function"]["address"],"code_sha256":common.digest(code),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Decompilation","game":game,"function":"VBlankIntrWait","family_profile":"rs","origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False}
 summary_path=Path("analysis/vblank-intr-wait-summary.json");common.write_json(root/summary_path,summary);languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/vblank-intr-wait-reconstruction.md")
 (root/research_path).write_text(f"# {game} VBlankIntrWait reconstruction\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) use the BIOS-call WaitForVBlank variant and resolve it to the same three-instruction SDK wrapper: clear r2, invoke SWI 5, then return through LR. Emerald and FireRed/LeafGreen use their verified volatile-poll implementation instead and are intentionally outside this wrapper catalog. No ROM bytes or instruction dumps are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_vblank_intr_wait_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix() for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/vblank-intr-wait-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"function":"VBlankIntrWait","origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/vblank_intr_wait_catalog.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False})
 return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())

