#!/usr/bin/env python3
"""Verify AgbMain across a Gen III release catalog without publishing ROM bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gba_bootstrap
import gba_entrypoint
import thumb_cfg


ROM_BASE = 0x08000000


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


def locate_agb_main(data: bytes) -> tuple[int, dict, dict]:
    if len(data) < 4:
        raise ValueError("ROM is shorter than its entry word")
    entry = gba_entrypoint.decode_entry_word(struct.unpack_from("<I", data)[0])
    bootstrap = gba_bootstrap.trace_bootstrap(
        data, entry["target_address"] - ROM_BASE
    )
    transition = bootstrap["transition"]
    if transition["target_state"] != "thumb":
        raise ValueError("bootstrap does not enter Thumb state")
    offset = transition["target_address"] - ROM_BASE
    if offset < 0 or offset % 2:
        raise ValueError("invalid AgbMain transition target")
    return offset, entry, bootstrap


def backward_loop_edges(cfg: dict) -> list[dict]:
    return [
        edge for edge in cfg["edges"]
        if edge["kind"] == "branch" and edge["target"] < edge["source"]
    ]


def target_equivalence(calls: list[dict]) -> list[int]:
    classes: dict[int, int] = {}
    result = []
    for call in calls:
        target = call["target"]
        if target not in classes:
            classes[target] = len(classes)
        result.append(classes[target])
    return result


def analyze_release(data: bytes, call_names: list[str] | None = None) -> dict:
    start, entry, bootstrap = locate_agb_main(data)
    cfg = thumb_cfg.trace_thumb_function(data, start, max_span=0x800)
    calls = sorted(cfg["calls"], key=lambda item: item["source"])
    loops = backward_loop_edges(cfg)
    if cfg["return_observed"]:
        raise ValueError("AgbMain unexpectedly returns")
    if call_names is not None and len(calls) != len(call_names):
        raise ValueError(
            f"AgbMain call count differs: expected {len(call_names)}, got {len(calls)}"
        )
    if len(loops) != 1:
        raise ValueError(f"expected one AgbMain loop back edge, found {len(loops)}")
    end = cfg["range_end"] - ROM_BASE
    if end <= start:
        raise ValueError("AgbMain range is empty")
    return {
        "start_offset": start,
        "end_offset": end,
        "entry_target": entry["target_address"],
        "bootstrap_target": bootstrap["transition"]["target_address"],
        "cfg": cfg,
        "calls": calls,
        "loop": loops[0],
        "target_equivalence": target_equivalence(calls),
    }


def inventory(root: Path, rom_dir: Path, catalog_path: Path) -> list[dict]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    roms = rom_index(rom_dir)
    result = []
    for release in catalog["releases"]:
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        analysis = analyze_release(roms[sha256].read_bytes())
        cfg = analysis["cfg"]
        result.append({
            "id": release_id,
            "call_count": len(analysis["calls"]),
            "range_length": analysis["end_offset"] - analysis["start_offset"],
            "call_source_offsets": [
                call["source"] - ROM_BASE - analysis["start_offset"]
                for call in analysis["calls"]
            ],
            "call_targets": [
                f"0x{call['target']:08X}" for call in analysis["calls"]
            ],
            "target_equivalence": analysis["target_equivalence"],
            "edge_kinds": dict(sorted({
                kind: sum(1 for edge in cfg["edges"] if edge["kind"] == kind)
                for kind in {edge["kind"] for edge in cfg["edges"]}
            }.items())),
        })
    return result


def build(root: Path, rom_dir: Path, catalog_path: Path, profile_path: Path,
          game: str) -> dict:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    profile = json.loads((root / profile_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    variants = profile["variants"]
    if not variants:
        raise ValueError("profile must provide at least one variant")
    release_variants = {}
    for variant in variants:
        names = variant["call_names"]
        if not names or any(not value for value in names):
            raise ValueError("every profile variant must provide non-empty call names")
        for release_id in variant["release_ids"]:
            if release_id in release_variants:
                raise ValueError(f"release appears in multiple variants: {release_id}")
            release_variants[release_id] = variant
    source_path = Path(profile["source"])
    source = (root / source_path).read_text(encoding="utf-8")
    all_call_names = {
        name for variant in variants for name in variant["call_names"]
    }
    for name in all_call_names:
        if name not in source:
            raise ValueError(f"source does not contain mapped call name: {name}")

    roms = rom_index(rom_dir)
    maps = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        if release_id not in release_variants:
            raise ValueError(f"release has no AgbMain profile variant: {release_id}")
        variant = release_variants[release_id]
        call_names = variant["call_names"]
        data = roms[sha256].read_bytes()
        try:
            analysis = analyze_release(data, call_names)
        except ValueError as error:
            raise ValueError(f"{release_id}: {error}") from error
        cfg, calls, loop = analysis["cfg"], analysis["calls"], analysis["loop"]
        shape = {
            "call_count": len(calls),
            "range_length": analysis["end_offset"] - analysis["start_offset"],
            "call_source_offsets": [
                call["source"] - ROM_BASE - analysis["start_offset"]
                for call in calls
            ],
            "target_equivalence": analysis["target_equivalence"],
            "edge_kinds": dict(sorted({
                kind: sum(1 for edge in cfg["edges"] if edge["kind"] == kind)
                for kind in {edge["kind"] for edge in cfg["edges"]}
            }.items())),
            "return_observed": cfg["return_observed"],
        }
        expected_shape = dict(variant["signature"])
        expected_shape.setdefault("return_observed", False)
        if shape != expected_shape:
            raise ValueError(
                f"AgbMain structural signature differs for {release_id} "
                f"({variant['id']})"
            )
        start, end = analysis["start_offset"], analysis["end_offset"]
        mapped_calls = [
            {
                "name": name,
                "source": f"0x{call['source']:08X}",
                "target": f"0x{call['target']:08X}",
            }
            for name, call in zip(call_names, calls)
        ]
        address_map = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "profile_variant": variant["id"],
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": {
                "name": "AgbMain",
                "address": f"0x{ROM_BASE + start:08X}",
                "range_end_exclusive": f"0x{ROM_BASE + end:08X}",
                "nonreturning": True,
                "rom_code_range": {
                    "start_offset": start,
                    "end_offset_exclusive": end,
                    "length": end - start,
                    "sha256": digest(data[start:end]),
                    "raw_bytes_published": False,
                },
                "loop_back_edge": {
                    "source": f"0x{loop['source']:08X}",
                    "target": f"0x{loop['target']:08X}",
                },
            },
            "entry_chain": {
                "arm_entry_target": f"0x{analysis['entry_target']:08X}",
                "thumb_transition_target": f"0x{analysis['bootstrap_target']:08X}",
            },
            "control_flow": {
                "instruction_halfwords": cfg["instruction_halfwords"],
                "edge_count": len(cfg["edges"]),
                "edge_kinds": shape["edge_kinds"],
                "direct_call_count": len(calls),
                "unique_call_target_count": len(set(call["target"] for call in calls)),
                "return_observed": False,
                "target_equivalence": shape["target_equivalence"],
                "raw_halfwords_omitted": True,
            },
            "direct_calls": mapped_calls,
            "naming_basis": profile["naming_basis"],
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-agb-main-map.json")
        write_json(root / map_path, address_map)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "profile_variant": variant["id"],
            "address": address_map["function"]["address"],
            "range_end_exclusive": address_map["function"]["range_end_exclusive"],
            "code_sha256": address_map["function"]["rom_code_range"]["sha256"],
            "evidence": map_path.as_posix(),
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "function": "AgbMain",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "profile": profile_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/agb-main-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/agb-main-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} `AgbMain` reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(releases)} cataloged releases ({languages}) were followed from "
        "the GBA ARM entry branch through the literal-backed ARM-to-Thumb bootstrap "
        "transition into `AgbMain`. The observed builds form "
        f"{len(variants)} explicit structural variant(s); each release is checked "
        "against its variant's direct-call name sequence, call offsets, target "
        "equivalence and edge-kind shape, plus one backward "
        "main-loop branch, and no return. Per-release maps preserve addresses, "
        "code hashes, calls, entry-chain evidence, and raw-free control-flow summaries. "
        "No ROM instruction bytes are published. Symbol names remain based on "
        f"`{profile['naming_basis']['repository']}` at "
        f"`{profile['naming_basis']['commit']}`, `{profile['naming_basis']['path']}`.\n",
        encoding="utf-8", newline="\n"
    )
    test_path = Path("tests/test_agb_main_reconstruction.py")
    outputs = [catalog_path, profile_path, source_path, summary_path, *maps,
               research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest_path = Path("manifests/agb-main-reconstruction.json")
    write_json(root / manifest_path, {
        "schema_version": 1,
        "game": game,
        "function": "AgbMain",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/agb_main_catalog.py",
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
    parser.add_argument("--profile", type=Path,
                        default=Path("analysis/agb-main-profile.json"))
    parser.add_argument("--game", required=True)
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    try:
        if args.inventory:
            print(json.dumps(inventory(args.root, args.rom_dir, args.catalog), indent=2))
        else:
            build(args.root, args.rom_dir, args.catalog, args.profile, args.game)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
