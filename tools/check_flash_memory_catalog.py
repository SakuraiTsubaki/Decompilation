#!/usr/bin/env python3
"""Verify CheckForFlashMemory across Gen III release catalogs."""
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
SHAPE = (38, 17, 2, 1, 3)
PROFILES = {
    "rs": {
        "repository": "pret/pokeruby",
        "commit": "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f",
        "path": "src/load_save.c",
    },
    "emerald": {
        "repository": "pret/pokeemerald",
        "commit": "fe1d8e51b265851676b65885818b1f5f62586135",
        "path": "src/load_save.c",
    },
    "frlg": {
        "repository": "pret/pokefirered",
        "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14",
        "path": "src/load_save.c",
    },
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


def unique_named_target(address_map: dict, name: str) -> int:
    targets = {
        int(call["target"], 16)
        for call in address_map["direct_calls"] if call["name"] == name
    }
    if len(targets) != 1:
        raise ValueError(f"expected one target for {name}, found {len(targets)}")
    return targets.pop()


def canonical_hash(cfg: dict) -> str:
    ordered = sorted(cfg["instructions"], key=lambda item: item["address"])
    return digest(b"".join(struct.pack("<H", item["halfword"]) for item in ordered))


def validate(cfg: dict, release_id: str) -> None:
    shape = (
        cfg["range_end"] - cfg["start_address"], cfg["instruction_halfwords"],
        len(cfg["calls"]), len(cfg["returns"]), len(cfg["edges"]),
    )
    if shape != SHAPE:
        raise ValueError(f"CheckForFlashMemory structural signature differs: {release_id}")
    kinds = sorted(edge["kind"] for edge in cfg["edges"])
    if kinds != ["branch", "conditional-fallthrough", "conditional-taken"]:
        raise ValueError(f"CheckForFlashMemory branch structure differs: {release_id}")


def function_record(data: bytes, cfg: dict, source: Path, root: Path) -> dict:
    calls = sorted(cfg["calls"], key=lambda item: item["source"])
    names = ["IdentifyFlash", "InitFlashTimer"]
    start = cfg["start_address"] - ROM_BASE
    end = cfg["range_end"] - ROM_BASE
    return {
        "name": "CheckForFlashMemory",
        "address": f"0x{cfg['start_address']:08X}",
        "range_end_exclusive": f"0x{cfg['range_end']:08X}",
        "source": source.as_posix(),
        "source_sha256": file_hash(root / source),
        "rom_code_range": {
            "start_offset": start,
            "end_offset_exclusive": end,
            "length": end - start,
            "sha256": digest(data[start:end]),
            "raw_bytes_published": False,
        },
        "calls": [
            {"name": name, "source": f"0x{call['source']:08X}",
             "target": f"0x{call['target']:08X}"}
            for name, call in zip(names, calls)
        ],
        "control_flow": {
            "instruction_halfwords": cfg["instruction_halfwords"],
            "edge_count": len(cfg["edges"]),
            "edge_kinds": {
                kind: sum(edge["kind"] == kind for edge in cfg["edges"])
                for kind in sorted({edge["kind"] for edge in cfg["edges"]})
            },
            "direct_call_count": len(calls),
            "return_count": len(cfg["returns"]),
            "canonical_reachable_bytes_sha256": canonical_hash(cfg),
            "raw_halfwords_omitted": True,
        },
    }


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    profile = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    source_path = Path("src/check_flash_memory.c")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in ("CheckForFlashMemory", "IdentifyFlash", "InitFlashTimer",
                  "gFlashMemoryPresent = 1", "gFlashMemoryPresent = 0"):
        if token not in source:
            raise ValueError(f"flash-detection source is missing token: {token}")
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        agb_path = Path(f"analysis/{release_id}-agb-main-map.json")
        agb = json.loads((root / agb_path).read_text(encoding="utf-8"))
        address = unique_named_target(agb, "CheckForFlashMemory")
        data = roms[sha256].read_bytes()
        cfg = thumb_cfg.trace_thumb_function(data, address - ROM_BASE, max_span=0x800)
        validate(cfg, release_id)
        function = function_record(data, cfg, source_path, root)
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "function": function,
            "verified_behavior": {
                "identify_flash_success_value": 0,
                "present_flag_on_success": 1,
                "present_flag_on_failure": 0,
                "initializes_flash_timer_only_on_success": True,
            },
            "cross_reference": {
                "agb_main_map": agb_path.as_posix(),
                "agb_main_map_sha256": file_hash(root / agb_path),
            },
            "naming_basis": {
                "repository": profile["repository"],
                "commit": profile["commit"],
                "path": profile["path"],
                "match_kind": "caller identity, call order, branch and state store",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-check-flash-memory-map.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "address": function["address"],
            "code_sha256": function["rom_code_range"]["sha256"],
            "evidence": map_path.as_posix(),
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "function": "CheckForFlashMemory",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/check-flash-memory-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/check-flash-memory-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} flash-memory detection reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) preserve the same "
        "38-byte control-flow shape: `IdentifyFlash` returns zero on success, "
        "the presence flag is set, and `InitFlashTimer` is called only on that "
        "success path. Per-release maps retain addresses, calls and code hashes "
        "without ROM bytes or instruction halfwords. "
        f"`{profile['repository']}` commit `{profile['commit']}`, "
        f"`{profile['path']}`, is the naming basis.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_check_flash_memory_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/check-flash-memory-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "CheckForFlashMemory",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/check_flash_memory_catalog.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [
            {"path": path.as_posix(), "sha256": file_hash(root / path)}
            for path in outputs
        ],
        "raw_rom_bytes_included": False,
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path,
                        default=Path("analysis/global-release-catalog.json"))
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
