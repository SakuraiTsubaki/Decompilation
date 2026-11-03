#!/usr/bin/env python3
"""Reconstruct ArcTan2 and structurally selected CpuSet stubs across Gen III catalogs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import register_ram_reset_catalog as common

FUNCTIONS={"ArcTan2":{"signature":bytes.fromhex("0adf7047"),"swi":0x0A,"arguments":["r0:x","r1:y"],"result":"r0"},"CpuSet":{"signature":bytes.fromhex("0bdf7047"),"swi":0x0B,"arguments":["r0:source","r1:destination","r2:mode"],"result":None}}
LZ_RELATIVE={"rs":{"ArcTan2":[-16],"CpuSet":[-4]},"emerald":{"ArcTan2":[-20],"CpuSet":[-8]},"frlg":{"ArcTan2":[-20,-16],"CpuSet":[-8,-4]}}
PATHS={"rs":"src/libs/libagbsyscall.s","emerald":"libagbsyscall/libagbsyscall.s","frlg":"src/libagbsyscall.s"}
def locate(data:bytes,signature:bytes)->list[int]:
 out=[];start=0
 while True:
  start=data.find(signature,start)
  if start<0:return out
  out.append(start);start+=1
def source_text()->str:
 lines=[".syntax unified",".thumb",""]
 for name,cfg in FUNCTIONS.items():lines += [f".global {name}",f".type {name}, %function",f"{name}:",f"    swi 0x{cfg['swi']:02X}","    bx lr",f".size {name}, . - {name}",""]
 return "\n".join(lines)
def build(root:Path,rom_dir:Path,catalog_path:Path,game:str,family:str)->dict:
 profile={**common.PROFILES[family],"path":PATHS[family]};catalog=json.loads((root/catalog_path).read_text(encoding="utf-8"));releases=catalog["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with Japanese origin")
 roms=common.rom_index(rom_dir);source_path=Path("src/arctan2_cpuset_bios_stubs.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  lz_path=Path(f"analysis/{rid}-lz77-bios-stub-map.json");lz=json.loads((root/lz_path).read_text(encoding="utf-8"));anchor=int(lz["functions"]["LZ77UnCompVram"]["rom_offset"]);data=roms[sha256].read_bytes();decoded={}
  for name,cfg in FUNCTIONS.items():
   matches=locate(data,cfg["signature"]);selected=[x for x in matches if x-anchor in LZ_RELATIVE[family][name]]
   if len(selected)!=1:raise ValueError(f"{name} SDK selection differs in {rid}: {matches}")
   offset=selected[0];code=data[offset:offset+4];decoded[name]={"address":f"0x{common.ROM_BASE+offset:08X}","rom_offset":offset,"range_end_exclusive":f"0x{common.ROM_BASE+offset+4:08X}","length":4,"code_sha256":common.digest(code),"software_interrupt":cfg["swi"],"arguments":cfg["arguments"],"result_register":cfg["result"],"return":"bx lr","signature_match_count":len(matches),"lz77_vram_relative_offset":offset-anchor,"selected_by_verified_sdk_layout":True}
  evidence={"schema_version":1,"axis":"Decompilation","target":{"release":rid,"sha256":sha256,"build_kind":release["build_kind"]},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"functions":decoded,"verified_layout":{"lz77_vram_anchor":lz["functions"]["LZ77UnCompVram"]["address"],"allowed_family_relative_offsets":LZ_RELATIVE[family]},"cross_reference":{"lz77_bios_stub_map":lz_path.as_posix(),"sha256":common.file_hash(root/lz_path)},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-arctan2-cpuset-stub-map.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,"addresses":{n:v["address"]for n,v in decoded.items()},"cpuset_signature_match_count":decoded["CpuSet"]["signature_match_count"],"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Decompilation","game":game,"library":"libagbsyscall","functions":list(FUNCTIONS),"family_profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/arctan2-cpuset-stub-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"]for x in records));duplicates=sum(x["cpuset_signature_match_count"]>1 for x in records);research_path=Path("research/arctan2-cpuset-stub-reconstruction.md");(root/research_path).write_text(f"# {game} ArcTan2 and CpuSet BIOS stub reconstruction\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} builds ({languages}) verify ArcTan2 SWI 0x0A and CpuSet SWI 0x0B at SDK-layout offsets from the LZ77 VRAM wrapper, including Ruby debug. CpuSet has duplicate signatures in {duplicates} build(s), so only the candidate at the verified -4/-8 position is selected. Pinned libagbsyscall sources corroborate symbols and calling conventions. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_arctan2_cpuset_stub_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/arctan2-cpuset-stub-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"library":"libagbsyscall","functions":list(FUNCTIONS),"family_profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/arctan2_cpuset_stub_catalog.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)}for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(common.PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
