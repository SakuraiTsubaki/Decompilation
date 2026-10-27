#!/usr/bin/env python3
"""Verify the Gen III background-reset cluster across release catalogs."""
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
FUNCTIONS = ["ResetBgs", "ResetBgControlStructs", "SetTextModeAndHideBgs"]
SHAPES = {
    "ResetBgs": (20, 10, 2, 1, 0),
    "ResetBgControlStructs": (24, 12, 0, 1, 2),
    "SetTextModeAndHideBgs": (22, 11, 2, 1, 0),
}
PROFILES = {
    "emerald": {
        "repository": "pret/pokeemerald",
        "commit": "fe1d8e51b265851676b65885818b1f5f62586135",
        "path": "src/bg.c",
        "bitfield_base": "uint8_t",
    },
    "frlg": {
        "repository": "pret/pokefirered",
        "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14",
        "path": "src/bg.c",
        "bitfield_base": "uint16_t",
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


def validate(name: str, cfg: dict, release_id: str) -> None:
    shape = (
        cfg["range_end"] - cfg["start_address"], cfg["instruction_halfwords"],
        len(cfg["calls"]), len(cfg["returns"]), len(cfg["edges"]),
    )
    if shape != SHAPES[name]:
        raise ValueError(f"{name} structural signature differs: {release_id}")
    if name == "ResetBgControlStructs":
        kinds = sorted(edge["kind"] for edge in cfg["edges"])
        if kinds != ["conditional-fallthrough", "conditional-taken"]:
            raise ValueError(f"background-array loop differs: {release_id}")


def function_record(data: bytes, name: str, cfg: dict, names: list[str],
                    source: Path, root: Path) -> dict:
    calls = sorted(cfg["calls"], key=lambda item: item["source"])
    if len(calls) != len(names):
        raise ValueError(f"{name} named call count differs")
    start = cfg["start_address"] - ROM_BASE
    end = cfg["range_end"] - ROM_BASE
    edge_kinds = dict(sorted({
        kind: sum(edge["kind"] == kind for edge in cfg["edges"])
        for kind in {edge["kind"] for edge in cfg["edges"]}
    }.items()))
    return {
        "name": name,
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
            {"name": call_name, "source": f"0x{call['source']:08X}",
             "target": f"0x{call['target']:08X}"}
            for call_name, call in zip(names, calls)
        ],
        "control_flow": {
            "instruction_halfwords": cfg["instruction_halfwords"],
            "edge_count": len(cfg["edges"]),
            "edge_kinds": edge_kinds,
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
    source_path = Path("src/bg_reset.c")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in (*FUNCTIONS, "GetGpuReg", "SetGpuReg",
                  "bgVisibilityAndMode = 0", profile["bitfield_base"]):
        if token not in source:
            raise ValueError(f"background source is missing token: {token}")
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        agb_path = Path(f"analysis/{release_id}-agb-main-map.json")
        agb = json.loads((root / agb_path).read_text(encoding="utf-8"))
        reset_address = unique_named_target(agb, "ResetBgs")
        data = roms[sha256].read_bytes()
        reset_cfg = thumb_cfg.trace_thumb_function(
            data, reset_address - ROM_BASE, max_span=0x800
        )
        validate("ResetBgs", reset_cfg, release_id)
        reset_calls = sorted(reset_cfg["calls"], key=lambda item: item["source"])
        control_cfg = thumb_cfg.trace_thumb_function(
            data, reset_calls[0]["target"] - ROM_BASE, max_span=0x400
        )
        text_cfg = thumb_cfg.trace_thumb_function(
            data, reset_calls[1]["target"] - ROM_BASE, max_span=0x400
        )
        validate("ResetBgControlStructs", control_cfg, release_id)
        validate("SetTextModeAndHideBgs", text_cfg, release_id)
        functions = [
            function_record(data, "ResetBgs", reset_cfg,
                            ["ResetBgControlStructs", "SetTextModeAndHideBgs"],
                            source_path, root),
            function_record(data, "ResetBgControlStructs", control_cfg, [],
                            source_path, root),
            function_record(data, "SetTextModeAndHideBgs", text_cfg,
                            ["GetGpuReg", "SetGpuReg"], source_path, root),
        ]
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "functions": functions,
            "verified_behavior": {
                "background_count": 4,
                "clears_control_configs": True,
                "clears_visibility_and_mode_cache": True,
                "display_control_clear_mask": "0x0F07",
            },
            "cross_reference": {
                "agb_main_map": agb_path.as_posix(),
                "agb_main_map_sha256": file_hash(root / agb_path),
            },
            "naming_basis": {
                "repository": profile["repository"],
                "commit": profile["commit"],
                "path": profile["path"],
                "match_kind": "caller identity, call chain, loop and state stores",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-bg-reset-map.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "functions": {
                item["name"]: {"address": item["address"],
                               "code_sha256": item["rom_code_range"]["sha256"]}
                for item in functions
            },
            "evidence": map_path.as_posix(),
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "cluster": FUNCTIONS,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/bg-reset-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/bg-reset-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} background reset reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) preserve the same "
        "three-function reset cluster. Four cached background configurations are "
        "zeroed, the cached mode/visibility field is cleared, and display-control "
        "mode plus BG0-BG3 enable bits are removed through `GetGpuReg`/`SetGpuReg`. "
        "Per-release maps retain addresses, calls and code hashes without ROM bytes "
        f"or instruction halfwords. `{profile['repository']}` commit "
        f"`{profile['commit']}`, `{profile['path']}`, is the naming basis.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_bg_reset_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/bg-reset-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "cluster": FUNCTIONS,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/reset_bgs_catalog.py",
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
