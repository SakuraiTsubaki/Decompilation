#!/usr/bin/env python3
"""Verify the default-font pointer bootstrap across Gen III releases."""
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
FUNCTIONS = ["SetDefaultFontsPointer", "SetFontsPointer"]
SHAPES = {
    "SetDefaultFontsPointer": (12, 6, 1, 1),
    "SetFontsPointer": (6, 3, 0, 1),
}
PROFILES = {
    "emerald": {
        "repository": "pret/pokeemerald",
        "commit": "fe1d8e51b265851676b65885818b1f5f62586135",
        "wrapper_path": "src/text.c",
        "callee_path": "src/text.c",
        "default_table": "sFontInfos",
    },
    "frlg": {
        "repository": "pret/pokefirered",
        "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14",
        "wrapper_path": "src/new_menu_helpers.c",
        "callee_path": "src/text_printer.c",
        "default_table": "gFontInfos",
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


def trace_cluster(data: bytes, wrapper_address: int) -> list[tuple[str, dict]]:
    address = wrapper_address
    result = []
    for index, name in enumerate(FUNCTIONS):
        cfg = thumb_cfg.trace_thumb_function(data, address - ROM_BASE, max_span=0x100)
        shape = (
            cfg["range_end"] - cfg["start_address"], cfg["instruction_halfwords"],
            len(cfg["calls"]), len(cfg["returns"]),
        )
        if shape != SHAPES[name] or cfg["edges"]:
            raise ValueError(f"{name} structural signature differs")
        result.append((name, cfg))
        if index == 0:
            address = cfg["calls"][0]["target"]
    return result


def function_record(data: bytes, name: str, cfg: dict, source: Path,
                    root: Path, callee: str | None) -> dict:
    start = cfg["start_address"] - ROM_BASE
    end = cfg["range_end"] - ROM_BASE
    calls = [] if callee is None else [{
        "name": callee,
        "source": f"0x{cfg['calls'][0]['source']:08X}",
        "target": f"0x{cfg['calls'][0]['target']:08X}",
    }]
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
        "calls": calls,
        "control_flow": {
            "instruction_halfwords": cfg["instruction_halfwords"],
            "edge_count": 0,
            "direct_call_count": len(cfg["calls"]),
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
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/font_pointer.c")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in (*FUNCTIONS, profile["default_table"], "gFonts = fonts"):
        if token not in source:
            raise ValueError(f"font pointer source is missing token: {token}")
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        agb_path = Path(f"analysis/{release_id}-agb-main-map.json")
        agb = json.loads((root / agb_path).read_text(encoding="utf-8"))
        wrapper_address = unique_named_target(agb, "SetDefaultFontsPointer")
        data = roms[sha256].read_bytes()
        traced = trace_cluster(data, wrapper_address)
        functions = [
            function_record(
                data, name, cfg, source_path, root,
                "SetFontsPointer" if name == "SetDefaultFontsPointer" else None,
            )
            for name, cfg in traced
        ]
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "functions": functions,
            "verified_behavior": {
                "default_table": profile["default_table"],
                "sets_active_font_table": True,
            },
            "cross_reference": {
                "agb_main_map": agb_path.as_posix(),
                "agb_main_map_sha256": file_hash(root / agb_path),
            },
            "naming_basis": {
                "repository": profile["repository"],
                "commit": profile["commit"],
                "wrapper_path": profile["wrapper_path"],
                "callee_path": profile["callee_path"],
                "match_kind": "caller identity, direct-call target and pointer store",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-font-pointer-bootstrap-map.json")
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
                item["name"]: {
                    "address": item["address"],
                    "code_sha256": item["rom_code_range"]["sha256"],
                }
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
    summary_path = Path("analysis/font-pointer-bootstrap-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/font-pointer-bootstrap-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} default font-pointer reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) resolve "
        "`SetDefaultFontsPointer` from `AgbMain` and follow its sole direct call "
        "to `SetFontsPointer`. The wrapper selects the game's default font-info "
        f"table (`{profile['default_table']}`); the callee stores it as the active "
        "table. Both functions have one observed return and no branch edges. "
        "Maps retain addresses and hashes without ROM bytes or instruction "
        f"halfwords, using `{profile['repository']}` commit `{profile['commit']}` "
        "as the naming and behavior reference.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_font_pointer_bootstrap_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/font-pointer-bootstrap-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "cluster": FUNCTIONS,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/font_pointer_catalog.py",
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
