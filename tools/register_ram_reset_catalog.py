#!/usr/bin/env python3
"""Verify the RegisterRamReset BIOS wrapper across Gen III release catalogs."""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path

ROM_BASE = 0x08000000
ROUTINE_LENGTH = 4
PROFILES = {
    "rs": {"repository": "pret/pokeruby", "commit": "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f", "path": "src/main.c"},
    "emerald": {"repository": "pret/pokeemerald", "commit": "fe1d8e51b265851676b65885818b1f5f62586135", "path": "src/main.c"},
    "frlg": {"repository": "pret/pokefirered", "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14", "path": "src/main.c"},
}

def digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def file_hash(path: Path) -> str: return digest(path.read_bytes())
def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
def rom_index(directory: Path) -> dict[str, Path]:
    result = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() == ".gba": result.setdefault(file_hash(path), path)
    return result

def named_target(agb_main: dict) -> int:
    targets = {int(call["target"], 16) for call in agb_main["direct_calls"] if call["name"] == "RegisterRamReset"}
    if len(targets) != 1: raise ValueError(f"expected one RegisterRamReset target, found {len(targets)}")
    return targets.pop()

def decode_wrapper(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + ROUTINE_LENGTH]
    if len(code) != ROUTINE_LENGTH: return None
    first, second = int.from_bytes(code[:2], "little"), int.from_bytes(code[2:], "little")
    if first != 0xDF01 or second != 0x4770: return None
    return {"length": 4, "instruction_halfwords": 2, "software_interrupt": 1,
            "return_instruction": "bx lr", "argument_register": "r0"}

def source_text() -> str:
    return '''.syntax unified
.thumb

.global RegisterRamReset
.type RegisterRamReset, %function
RegisterRamReset:
    swi 1
    bx lr
.size RegisterRamReset, . - RegisterRamReset
'''

def build(root: Path, rom_dir: Path, catalog_path: Path, game: str, family: str) -> dict:
    profile = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8")); releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese": raise ValueError("catalog must begin with Japanese origin")
    source_path = Path("src/register_ram_reset.s")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    roms = rom_index(rom_dir); maps=[]; records=[]
    for index, release in enumerate(releases):
        rid, sha256 = release["id"], release["sha256"]
        if sha256 not in roms: raise ValueError(f"missing catalog ROM: {rid}")
        caller_path = Path(release["evidence"].replace("-agb-main-map.json", "-agb-main-map.json")) if "evidence" in release else Path(f"analysis/{rid}-agb-main-map.json")
        if not (root / caller_path).is_file(): caller_path = Path(f"analysis/{rid}-agb-main-map.json")
        caller = json.loads((root / caller_path).read_text(encoding="utf-8")); address = named_target(caller)
        data = roms[sha256].read_bytes(); offset = address - ROM_BASE
        decoded = decode_wrapper(data, offset)
        if decoded is None: raise ValueError(f"RegisterRamReset wrapper differs: {rid}")
        code = data[offset:offset + ROUTINE_LENGTH]
        evidence = {
            "schema_version": 1, "axis": "Decompilation",
            "target": {"release": rid, "sha256": sha256,
                       "build_kind": release["build_kind"]}, "origin_reference": index == 0,
            "function": {"name": "RegisterRamReset", "address": f"0x{address:08X}",
                         "range_end_exclusive": f"0x{address + ROUTINE_LENGTH:08X}",
                         "source": source_path.as_posix(), "source_sha256": file_hash(root / source_path),
                         "rom_code_range": {"start_offset": offset,
                                            "end_offset_exclusive": offset + ROUTINE_LENGTH,
                                            "length": ROUTINE_LENGTH, "sha256": digest(code),
                                            "raw_bytes_published": False}},
            "verified_behavior": decoded,
            "cross_reference": {"agb_main_map": caller_path.as_posix(),
                                "agb_main_map_sha256": file_hash(root / caller_path)},
            "naming_basis": profile, "raw_rom_bytes_included": False}
        map_path = Path(f"analysis/{rid}-register-ram-reset-map.json"); write_json(root / map_path, evidence); maps.append(map_path)
        records.append({"id":rid,"language":release["language"],"revision":release["revision"],
                        "build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,
                        "address":evidence["function"]["address"],"code_sha256":digest(code),
                        "evidence":map_path.as_posix()})
    summary={"schema_version":1,"axis":"Decompilation","game":game,"function":"RegisterRamReset",
             "family_profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),
             "source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False}
    summary_path=Path("analysis/register-ram-reset-summary.json");write_json(root/summary_path,summary)
    languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/register-ram-reset-reconstruction.md")
    (root/research_path).write_text(f"# {game} RegisterRamReset reconstruction\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) resolve the AgbMain call to a two-instruction Thumb wrapper: BIOS software interrupt 1 followed by return through LR. The wrapper consumes reset flags in r0. Per-release maps preserve addresses and hashes without ROM bytes or instruction dumps.\n",encoding="utf-8",newline="\n")
    test_path=Path("tests/test_register_ram_reset_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path]
    missing=[p.as_posix() for p in outputs if not (root/p).is_file()]
    if missing: raise ValueError("missing output(s): "+", ".join(missing))
    write_json(root/"manifests/register-ram-reset-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"function":"RegisterRamReset","origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/register_ram_reset_catalog.py","tool_sha256":file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False})
    return summary

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(PROFILES),required=True);a=p.parse_args()
    try: build(a.root,a.rom_dir,a.catalog,a.game,a.family)
    except (OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
    return 0
if __name__=="__main__":raise SystemExit(main())

