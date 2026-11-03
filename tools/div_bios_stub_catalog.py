#!/usr/bin/env python3
"""Reconstruct the Div BIOS wrapper across Pokémon Emerald builds."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import register_ram_reset_catalog as common
SIGNATURE=bytes.fromhex("06df7047")
LZ_RELATIVE=-4
SOURCE_PATH="libagbsyscall/libagbsyscall.s"
def locate(data:bytes)->list[int]:
 out=[];start=0
 while True:
  start=data.find(SIGNATURE,start)
  if start<0:return out
  out.append(start);start+=1
def source_text()->str:
 return """.syntax unified
.thumb

.global Div
.type Div, %function
Div:
    swi 0x06
    bx lr
.size Div, . - Div
"""
def build(root:Path,rom_dir:Path,catalog_path:Path,game:str)->dict:
 profile={**common.PROFILES["emerald"],"path":SOURCE_PATH};catalog=json.loads((root/catalog_path).read_text(encoding="utf-8"));releases=catalog["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with Japanese origin")
 roms=common.rom_index(rom_dir);source_path=Path("src/div_bios_stub.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  lz_path=Path(f"analysis/{rid}-lz77-bios-stub-map.json");lz=json.loads((root/lz_path).read_text(encoding="utf-8"));anchor=int(lz["functions"]["LZ77UnCompVram"]["rom_offset"]);data=roms[sha256].read_bytes();matches=locate(data);offset=anchor+LZ_RELATIVE
  if offset not in matches:raise ValueError(f"Div SDK selection differs in {rid}: {matches}")
  function={"name":"Div","rom_offset":offset,"address":f"0x{common.ROM_BASE+offset:08X}","range_end_exclusive":f"0x{common.ROM_BASE+offset+4:08X}","length":4,"code_sha256":common.digest(data[offset:offset+4]),"numerator_register":"r0","denominator_register":"r1","quotient_register":"r0","remainder_register":"r1","absolute_quotient_register":"r3","software_interrupt":6,"return":"bx lr","signature_match_count":len(matches),"lz77_vram_relative_offset":LZ_RELATIVE,"selected_by_verified_sdk_layout":True}
  evidence={"schema_version":1,"axis":"Decompilation","target":{"release":rid,"sha256":sha256,"build_kind":release["build_kind"]},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"function":function,"verified_layout":{"lz77_vram_anchor":lz["functions"]["LZ77UnCompVram"]["address"],"relative_offset":LZ_RELATIVE},"cross_reference":{"lz77_bios_stub_map":lz_path.as_posix(),"sha256":common.file_hash(root/lz_path)},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-div-bios-stub-map.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,"address":function["address"],"signature_match_count":len(matches),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Decompilation","game":game,"library":"libagbsyscall","function":"Div","family_profile":"emerald","origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/div-bios-stub-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/div-bios-stub-reconstruction.md");(root/research_path).write_text(f"# {game} Div BIOS stub reconstruction\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} cataloged builds ({languages}) independently verify the Div wrapper at -4 from LZ77UnCompVram. It invokes BIOS SWI 0x06 and exposes quotient, remainder, and absolute quotient results in r0, r1, and r3. Pinned libagbsyscall source corroborates the symbol and calling convention. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_div_bios_stub_catalog.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path]
 if any(not(root/p).is_file() for p in outputs):raise ValueError("missing output")
 common.write_json(root/"manifests/div-bios-stub-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"library":"libagbsyscall","function":"Div","family_profile":"emerald","origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/div_bios_stub_catalog.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",default="Emerald");a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game)
 except(OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
