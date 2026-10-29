#!/usr/bin/env python3
"""Verify InitFlashTimer across Gen III release catalogs."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thumb_cfg


ROM_BASE = 0x08000000
PROFILES = {
    "rs": {"shape": (16, 8, 1, 1, 0), "repository": "pret/pokeruby",
           "commit": "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f", "path": "src/main.c",
           "operand_form": "loaded-handler", "handler_source": "gFlashTimerIntrFunc",
           "interrupt_table_slot": None},
    "emerald": {"shape": (14, 7, 1, 1, 0), "repository": "pret/pokeemerald",
                "commit": "fe1d8e51b265851676b65885818b1f5f62586135", "path": "src/main.c",
                "operand_form": "slot-address", "handler_source": "gIntrTable + 7",
                "interrupt_table_slot": 7},
    "frlg": {"shape": (16, 8, 1, 1, 0), "repository": "pret/pokefirered",
             "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14", "path": "src/main.c",
             "operand_form": "loaded-handler", "handler_source": "sTimerIntrFunc",
             "interrupt_table_slot": 7},
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def rom_index(directory: Path) -> dict[str, Path]:
    result = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() == ".gba":
            result.setdefault(file_hash(path), path)
    return result


def unique_named_target(evidence: dict, name: str) -> int:
    targets = {int(call["target"], 16) for call in evidence["function"]["calls"]
               if call["name"] == name}
    if len(targets) != 1:
        raise ValueError(f"expected one target for {name}, found {len(targets)}")
    return targets.pop()


def canonical_hash(cfg: dict) -> str:
    ordered = sorted(cfg["instructions"], key=lambda item: item["address"])
    return digest(b"".join(struct.pack("<H", item["halfword"]) for item in ordered))


def operand_form(cfg: dict) -> str:
    halfwords = [item["halfword"] for item in
                 sorted(cfg["instructions"], key=lambda item: item["address"])]
    if (len(halfwords) == 8 and halfwords[0] == 0xB500
            and halfwords[1] & 0xF800 == 0x4800 and halfwords[2] == 0x6801
            and halfwords[3] == 0x2002 and halfwords[-2:] == [0xBC01, 0x4700]):
        return "loaded-handler"
    if (len(halfwords) == 7 and halfwords[0] == 0xB500
            and halfwords[1] & 0xFF00 == 0x4900 and halfwords[2] == 0x2002
            and halfwords[-2:] == [0xBC01, 0x4700]):
        return "slot-address"
    return "unknown"


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    profile = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    source_path = Path("src/init_flash_timer.c")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in ("InitFlashTimer", "SetFlashTimerIntr", "2",
                  profile["handler_source"].split(" +")[0]):
        if token not in source:
            raise ValueError(f"timer source is missing token: {token}")
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        caller_path = Path(f"analysis/{release_id}-check-flash-memory-map.json")
        caller = json.loads((root / caller_path).read_text(encoding="utf-8"))
        address = unique_named_target(caller, "InitFlashTimer")
        data = roms[sha256].read_bytes()
        cfg = thumb_cfg.trace_thumb_function(data, address - ROM_BASE, max_span=0x400)
        shape = (cfg["range_end"] - cfg["start_address"], cfg["instruction_halfwords"],
                 len(cfg["calls"]), len(cfg["returns"]), len(cfg["edges"]))
        if shape != profile["shape"]:
            raise ValueError(f"InitFlashTimer structural signature differs: {release_id}")
        actual_form = operand_form(cfg)
        if actual_form != profile["operand_form"]:
            raise ValueError(f"InitFlashTimer operand form differs: {release_id}: {actual_form}")
        call = cfg["calls"][0]
        start, end = address - ROM_BASE, cfg["range_end"] - ROM_BASE
        evidence = {
            "schema_version": 1, "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "function": {"name": "InitFlashTimer", "address": f"0x{address:08X}",
                         "range_end_exclusive": f"0x{cfg['range_end']:08X}",
                         "source": source_path.as_posix(), "source_sha256": file_hash(root / source_path),
                         "rom_code_range": {"start_offset": start, "end_offset_exclusive": end,
                                            "length": end - start, "sha256": digest(data[start:end]),
                                            "raw_bytes_published": False},
                         "calls": [{"name": "SetFlashTimerIntr",
                                    "source": f"0x{call['source']:08X}",
                                    "target": f"0x{call['target']:08X}"}]},
            "control_flow": {"instruction_halfwords": cfg["instruction_halfwords"],
                             "edge_count": 0, "direct_call_count": 1, "return_count": 1,
                             "canonical_reachable_bytes_sha256": canonical_hash(cfg),
                             "raw_halfwords_omitted": True},
            "verified_behavior": {"timer_index": 2,
                                  "handler_operand_form": actual_form,
                                  "handler_source": profile["handler_source"],
                                  "interrupt_table_slot": profile["interrupt_table_slot"]},
            "cross_reference": {"check_flash_memory_map": caller_path.as_posix(),
                                "check_flash_memory_map_sha256": file_hash(root / caller_path)},
            "naming_basis": {"repository": profile["repository"], "commit": profile["commit"],
                             "path": profile["path"]},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-init-flash-timer-map.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": release_id, "language": release["language"],
                        "revision": release["revision"], "build_kind": release["build_kind"],
                        "sha256": sha256, "origin_reference": index == 0,
                        "address": evidence["function"]["address"],
                        "code_sha256": evidence["function"]["rom_code_range"]["sha256"],
                        "evidence": map_path.as_posix()})
    summary = {"schema_version": 1, "game": game, "function": "InitFlashTimer",
               "family_profile": family, "origin_reference": releases[0]["id"],
               "release_count": len(records), "source": source_path.as_posix(),
               "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/init-flash-timer-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/init-flash-timer-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} InitFlashTimer reconstruction\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) preserve the `{family}` profile: timer 2 uses "
        f"`{profile['handler_source']}` through `SetFlashTimerIntr`. Per-release maps "
        "retain calls and hashes without ROM bytes or instruction halfwords.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_init_flash_timer_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/init-flash-timer-reconstruction.json", {
        "schema_version": 1, "game": game, "function": "InitFlashTimer",
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Decompilation",
                      "tool": "tools/init_flash_timer_catalog.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("analysis/global-release-catalog.json"))
    parser.add_argument("--game", required=True)
    parser.add_argument("--family", choices=sorted(PROFILES), required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.family)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
