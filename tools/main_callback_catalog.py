#!/usr/bin/env python3
"""Verify the Gen III main callback cluster across release catalogs."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thumb_cfg


ROM_BASE = 0x08000000
PROFILES = {
    "rs": {
        "update_calls": [
            "LinkMain1", "LinkMain2", "LinkReceivedNothingOverride", "CallCallbacks"
        ],
        "callback_calls": ["Callback1Dispatch", "Callback2Dispatch"],
    },
    "emerald": {
        "update_calls": ["HandleLinkConnection", "CallCallbacks"],
        "callback_calls": ["Callback1Dispatch", "Callback2Dispatch"],
    },
    "frlg": {
        "update_calls": ["HandleLinkConnection", "CallCallbacks"],
        "callback_calls": [
            "RunSaveFailedScreen", "RunHelpSystemCallback",
            "Callback1Dispatch", "Callback2Dispatch",
        ],
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


def compact_cfg(cfg: dict) -> dict:
    kinds = dict(sorted({
        kind: sum(1 for edge in cfg["edges"] if edge["kind"] == kind)
        for kind in {edge["kind"] for edge in cfg["edges"]}
    }.items()))
    return {
        "instruction_halfwords": cfg["instruction_halfwords"],
        "edge_count": len(cfg["edges"]),
        "edge_kinds": kinds,
        "direct_call_count": len(cfg["calls"]),
        "return_count": len(cfg["returns"]),
        "raw_halfwords_omitted": True,
    }


def trace_function(data: bytes, address: int) -> dict:
    offset = address - ROM_BASE
    if offset < 0 or offset % 2:
        raise ValueError(f"invalid Thumb function address: 0x{address:08X}")
    cfg = thumb_cfg.trace_thumb_function(data, offset, max_span=0x400)
    if len(cfg["returns"]) != 1:
        raise ValueError(f"expected one return at 0x{address:08X}")
    return cfg


def named_calls(cfg: dict, names: list[str]) -> list[dict]:
    calls = sorted(cfg["calls"], key=lambda item: item["source"])
    if len(calls) != len(names):
        raise ValueError(
            f"call count differs: expected {len(names)}, got {len(calls)}"
        )
    return [
        {
            "name": name,
            "source": f"0x{call['source']:08X}",
            "target": f"0x{call['target']:08X}",
        }
        for name, call in zip(names, calls)
    ]


def function_record(data: bytes, name: str, cfg: dict, calls: list[dict],
                    source: Path, root: Path) -> dict:
    start = cfg["start_address"] - ROM_BASE
    end = cfg["range_end"] - ROM_BASE
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
        "control_flow": compact_cfg(cfg),
    }


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    profile = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    source = Path("src/main_callbacks.c")
    init_source = (
        Path("src/init_main_callbacks.c")
        if (root / "src/init_main_callbacks.c").is_file() else source
    )
    for path in {source, init_source}:
        if not (root / path).is_file():
            raise ValueError(f"missing callback source: {path}")
    maps, records = [], []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        agb_path = Path(f"analysis/{release_id}-agb-main-map.json")
        agb = json.loads((root / agb_path).read_text(encoding="utf-8"))
        update_address = unique_named_target(agb, "UpdateLinkAndCallCallbacks")
        init_address = unique_named_target(agb, "InitMainCallbacks")
        update_cfg = trace_function(data, update_address)
        init_cfg = trace_function(data, init_address)
        update_calls = named_calls(update_cfg, profile["update_calls"])
        init_calls_raw = sorted(init_cfg["calls"], key=lambda item: item["source"])
        if len(init_calls_raw) != 1:
            raise ValueError(
                f"{release_id}: InitMainCallbacks expected one direct call, "
                f"got {len(init_calls_raw)}"
            )
        init_calls = named_calls(init_cfg, ["SetMainCallback2"])
        callback_address = int(update_calls[-1]["target"], 16)
        set_address = int(init_calls[-1]["target"], 16)
        callback_cfg = trace_function(data, callback_address)
        set_cfg = trace_function(data, set_address)
        callback_calls = named_calls(callback_cfg, profile["callback_calls"])
        set_calls = named_calls(set_cfg, [])

        set_path = Path(f"analysis/{release_id}-set-main-callback2-map.json")
        set_map = json.loads((root / set_path).read_text(encoding="utf-8"))
        if int(set_map["function"]["address"], 16) != set_address:
            raise ValueError(f"{release_id}: SetMainCallback2 cross-reference differs")
        if int(set_map["function"]["range_end_exclusive"], 16) != set_cfg["range_end"]:
            raise ValueError(f"{release_id}: SetMainCallback2 range differs")

        functions = [
            function_record(data, "UpdateLinkAndCallCallbacks", update_cfg,
                            update_calls, source, root),
            function_record(data, "InitMainCallbacks", init_cfg,
                            init_calls, init_source, root),
            function_record(data, "CallCallbacks", callback_cfg,
                            callback_calls, source, root),
            function_record(data, "SetMainCallback2", set_cfg,
                            set_calls, source, root),
        ]
        address_map = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "family_profile": family,
            "functions": functions,
            "cross_references": {
                "agb_main_map": agb_path.as_posix(),
                "agb_main_map_sha256": file_hash(root / agb_path),
                "set_main_callback2_map": set_path.as_posix(),
                "set_main_callback2_map_sha256": file_hash(root / set_path),
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-main-callbacks-map.json")
        write_json(root / map_path, address_map)
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

    sources = list(dict.fromkeys([source.as_posix(), init_source.as_posix()]))
    summary = {
        "schema_version": 1,
        "game": game,
        "cluster": [
            "UpdateLinkAndCallCallbacks", "InitMainCallbacks",
            "CallCallbacks", "SetMainCallback2",
        ],
        "family_profile": family,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "sources": sources,
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/main-callbacks-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/main-callbacks-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} main callback cluster reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) were verified from "
        "`AgbMain` call targets. `CallCallbacks` is reached as the terminal "
        "direct callee of `UpdateLinkAndCallCallbacks`; `SetMainCallback2` is "
        "reached from `InitMainCallbacks` and cross-checked against the existing "
        "global SetMainCallback2 catalog. Per-release maps retain function ranges, "
        "hashes, named direct calls and raw-free CFG summaries. No ROM instruction "
        "bytes are published.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_main_callbacks_reconstruction.py")
    outputs = [
        catalog_path, *[Path(value) for value in sources],
        summary_path, *maps, research_path, test_path,
    ]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/main-callbacks-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "cluster": summary["cluster"],
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/main_callback_catalog.py",
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
