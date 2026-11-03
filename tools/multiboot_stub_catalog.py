#!/usr/bin/env python3
"""Reconstruct the MultiBoot BIOS wrapper across Emerald and FRLG catalogs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import register_ram_reset_catalog as common

SIGNATURE=bytes.fromhex("012125df7047")
FUNCTION_LENGTH=6
LZ_RELATIVE={"emerald":8,"frlg":8}
PATHS={"emerald":"libagbsyscall/libagbsyscall.s","frlg":"src/libagbsyscall.s"}
def locate(data:bytes)->list[int]:
 out=[];start=0
 while True:
  start=data.find(SIGNATURE,start)
  if start<0:return out
  out.append(start);start+=1
def source_text()->str:
 return """.syntax unified
.thumb

.global MultiBoot
.type MultiBoot, %function
MultiBoot:
    movs r1, 1
    swi 0x25
    bx lr
.size MultiBoot, . - MultiBoot
"""
def build(root:Path,rom_dir:Path,catalog_path:Path,game:str,family:str)->dict:
 profile={**common.PROFILES[family],"path":PATHS[family]};catalog=json.loads((root/catalog_path).read_text(encoding="utf-8"));releases=catalog["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with Japanese origin")
 roms=common.rom_index(rom_dir);source_path=Path("src/multiboot_bios_stub.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  lz_path=Path(f"analysis/{rid}-lz77-bios-stub-map.json");lz=json.loads((root/lz_path).read_text(encoding="utf-8"));anchor=int(lz["functions"]["LZ77UnCompVram"]["rom_offset"]);data=roms[sha256].read_bytes();matches=locate(data);offset=anchor+LZ_RELATIVE[family]
  if offset not in matches:raise ValueError(f"MultiBoot SDK selection differs in {rid}: {matches}")
  function={"name":"MultiBoot","rom_offset":offset,"address":f"0x{common.ROM_BASE+offset:08X}","range_end_exclusive":f"0x{common.ROM_BASE+offset+FUNCTION_LENGTH:08X}","length":FUNCTION_LENGTH,"code_sha256":common.digest(data[offset:offset+FUNCTION_LENGTH]),"mode_register":"r1","mode_value":1,"parameter_register":"r0","result_register":"r0","software_interrupt":0x25,"return":"bx lr","signature_match_count":len(matches),"lz77_vram_relative_offset":offset-anchor,"selected_by_verified_sdk_layout":True}
  evidence={"schema_version":1,"axis":"Decompilation","target":{"release":rid,"sha256":sha256,"build_kind":release["build_kind"]},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"function":function,"verified_layout":{"lz77_vram_anchor":lz["functions"]["LZ77UnCompVram"]["address"],"family_relative_offset":LZ_RELATIVE[family]},"cross_reference":{"lz77_bios_stub_map":lz_path.as_posix(),"sha256":common.file_hash(root/lz_path)},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-multiboot-stub-map.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,"address":function["address"],"signature_match_count":len(matches),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Decompilation","game":game,"library":"libagbsyscall","function":"MultiBoot","family_profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/multiboot-stub-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/multiboot-stub-reconstruction.md");(root/research_path).write_text(f"# {game} MultiBoot BIOS stub reconstruction\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} cataloged builds ({languages}) independently verify the six-byte MultiBoot wrapper at +8 from LZ77UnCompVram. It fixes r1 to mode 1, invokes BIOS SWI 0x25, and returns the result in r0. Pinned libagbsyscall sources corroborate the symbol and calling convention. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_multiboot_stub_catalog.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix() for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/multiboot-stub-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"library":"libagbsyscall","function":"MultiBoot","family_profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/multiboot_stub_catalog.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(LZ_RELATIVE),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
