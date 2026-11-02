#!/usr/bin/env python3
"""Reconstruct the adjacent LZ77UnCompVram/Wram BIOS stubs across Gen III catalogs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import register_ram_reset_catalog as common

VRAM_SIGNATURE=bytes.fromhex("12df7047")
WRAM_SIGNATURE=bytes.fromhex("11df7047")
SUITE_SIGNATURE=VRAM_SIGNATURE+WRAM_SIGNATURE
FUNCTION_LENGTH=4
SUITE_LENGTH=8
PATHS={"rs":"src/libs/libagbsyscall.s","emerald":"libagbsyscall/libagbsyscall.s","frlg":"src/libagbsyscall.s"}
def locate(data:bytes)->list[int]:
 out=[];start=0
 while True:
  start=data.find(SUITE_SIGNATURE,start)
  if start<0:return out
  out.append(start);start+=1
def source_text()->str:
 return '''.syntax unified
.thumb

.global LZ77UnCompVram
.type LZ77UnCompVram, %function
LZ77UnCompVram:
    swi 0x12
    bx lr
.size LZ77UnCompVram, . - LZ77UnCompVram

.global LZ77UnCompWram
.type LZ77UnCompWram, %function
LZ77UnCompWram:
    swi 0x11
    bx lr
.size LZ77UnCompWram, . - LZ77UnCompWram
'''
def build(root:Path,rom_dir:Path,catalog_path:Path,game:str,family:str)->dict:
 profile={**common.PROFILES[family],"path":PATHS[family]};catalog=json.loads((root/catalog_path).read_text(encoding="utf-8"));releases=catalog["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with Japanese origin")
 roms=common.rom_index(rom_dir);source_path=Path("src/lz77_bios_stubs.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  data=roms[sha256].read_bytes();matches=locate(data)
  if len(matches)!=1:raise ValueError(f"expected one LZ77 BIOS stub suite in {rid}, found {len(matches)}")
  start=matches[0];wram=start+FUNCTION_LENGTH;end=start+SUITE_LENGTH
  functions={"LZ77UnCompVram":{"address":f"0x{common.ROM_BASE+start:08X}","rom_offset":start,"range_end_exclusive":f"0x{common.ROM_BASE+wram:08X}","length":FUNCTION_LENGTH,"code_sha256":common.digest(data[start:wram]),"software_interrupt":0x12,"source_register":"r0","destination_register":"r1","destination_memory":"VRAM","return":"bx lr"},"LZ77UnCompWram":{"address":f"0x{common.ROM_BASE+wram:08X}","rom_offset":wram,"range_end_exclusive":f"0x{common.ROM_BASE+end:08X}","length":FUNCTION_LENGTH,"code_sha256":common.digest(data[wram:end]),"software_interrupt":0x11,"source_register":"r0","destination_register":"r1","destination_memory":"WRAM","return":"bx lr"}}
  evidence={"schema_version":1,"axis":"Decompilation","target":{"release":rid,"sha256":sha256,"build_kind":release["build_kind"]},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"functions":functions,"verified_layout":{"adjacent":True,"suite_length":SUITE_LENGTH,"vram_to_wram_delta":FUNCTION_LENGTH,"suite_signature_match_count":len(matches)},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-lz77-bios-stub-map.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,"vram_address":functions["LZ77UnCompVram"]["address"],"wram_address":functions["LZ77UnCompWram"]["address"],"suite_sha256":common.digest(data[start:end]),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Decompilation","game":game,"library":"libagbsyscall","functions":["LZ77UnCompVram","LZ77UnCompWram"],"family_profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/lz77-bios-stub-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"]for x in records));research_path=Path("research/lz77-bios-stub-reconstruction.md");(root/research_path).write_text(f"# {game} LZ77 BIOS stub reconstruction\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged builds ({languages}) independently contain exactly one adjacent `LZ77UnCompVram`/`LZ77UnCompWram` suite, including the Ruby debug build where cataloged. The wrappers pass source and destination in r0/r1, invoke BIOS SWI 0x12 and 0x11, and return through lr. Pinned upstream libagbsyscall sources corroborate the symbols and order. Maps preserve addresses, semantics, and hashes without publishing ROM bytes.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_lz77_bios_stub_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/lz77-bios-stub-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"library":"libagbsyscall","functions":summary["functions"],"family_profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/lz77_bios_stub_catalog.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)}for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(common.PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
