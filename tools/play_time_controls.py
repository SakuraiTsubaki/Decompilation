#!/usr/bin/env python3
"""Publish ROM-backed evidence for the four play-time counter control routines."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FUNCTIONS = (
    ("reset", "PlayTimeCounter_Reset"),
    ("start", "PlayTimeCounter_Start"),
    ("stop", "PlayTimeCounter_Stop"),
    ("set-to-max", "PlayTimeCounter_SetToMax"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def build_evidence(
    root: Path,
    rom: Path,
    expected_sha256: str,
    release: str,
    prefix: str,
    save_storage: str,
    reference_repository: str,
    reference_commit: str,
    reference_path: str,
) -> list[Path]:
    data = rom.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")

    source_path = root / "src/play_time_counter.c"
    source_digest = sha256(source_path)
    records = []
    cfg_paths = []
    cfg_by_slug = {}
    for slug, name in FUNCTIONS:
        relative = Path(f"analysis/{prefix}-jp-play-time-counter-{slug}-cfg.json")
        path = root / relative
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if cfg["source_sha256"] != digest or not cfg.get("raw_halfwords_omitted"):
            raise ValueError(f"{slug} CFG is not publication-safe or targets another ROM")
        if len(cfg["returns"]) != 1:
            raise ValueError(f"{slug} must have exactly one observed return")
        start = cfg["range_start"]
        end = cfg["range_end"]
        offset_start = start - cfg["rom_base"]
        offset_end = end - cfg["rom_base"]
        calls = cfg["calls"]
        records.append(
            {
                "name": name,
                "address": f"0x{start:08X}",
                "range_end_exclusive": f"0x{end:08X}",
                "rom_code_range": {
                    "start_offset": offset_start,
                    "end_offset_exclusive": offset_end,
                    "length": offset_end - offset_start,
                    "sha256": hashlib.sha256(data[offset_start:offset_end]).hexdigest(),
                    "raw_bytes_published": False,
                },
                "cfg": relative.as_posix(),
                "edge_count": len(cfg["edges"]),
                "return_count": len(cfg["returns"]),
                "calls": [
                    {"address": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"}
                    for call in calls
                ],
            }
        )
        cfg_paths.append(path)
        cfg_by_slug[slug] = cfg

    if cfg_by_slug["reset"]["calls"] or cfg_by_slug["stop"]["calls"] or cfg_by_slug["set-to-max"]["calls"]:
        raise ValueError("only Start may call another routine")
    start_calls = cfg_by_slug["start"]["calls"]
    if len(start_calls) != 1 or start_calls[0]["target"] != cfg_by_slug["set-to-max"]["range_start"]:
        raise ValueError("Start must call the observed SetToMax entry")

    map_path = root / f"analysis/{prefix}-jp-play-time-counter-controls-map.json"
    report_path = root / "research/play-time-counter-controls-reconstruction.md"
    manifest_path = root / "manifests/play-time-counter-controls-reconstruction.json"
    evidence = {
        "schema_version": 1,
        "target": {"release": release, "sha256": digest},
        "source": "src/play_time_counter.c",
        "source_sha256": source_digest,
        "save_storage": save_storage,
        "save_field_offsets": {
            "playTimeHours": 14,
            "playTimeMinutes": 16,
            "playTimeSeconds": 17,
            "playTimeVBlanks": 18,
        },
        "functions": records,
        "behavior": {
            "reset": {"state": 0, "hours": 0, "minutes": 0, "seconds": 0, "vblanks": 0},
            "start": {"state": 1, "clamp_when_hours_above": 999},
            "stop": {"state": 0},
            "set_to_max": {"state": 2, "hours": 999, "minutes": 59, "seconds": 59, "vblanks": 59},
        },
        "naming_basis": {
            "repository": reference_repository,
            "commit": reference_commit,
            "path": reference_path,
            "match_kind": "state writes, save-field offsets, clamp threshold and direct call target",
            "raw_rom_bytes_published": False,
        },
    }
    write_json(map_path, evidence)

    function_lines = "\n".join(
        f"- `{item['name']}`: `{item['address']}..{item['range_end_exclusive']}`, "
        f"{item['rom_code_range']['length']} bytes, SHA-256 `{item['rom_code_range']['sha256']}`."
        for item in records
    )
    report = f"""# {release} play-time counter control reconstruction

The verified Japanese ROM contains four control routines surrounding the previously reconstructed update routine:

{function_lines}

The publication-safe CFGs prove one return for every routine. Only `PlayTimeCounter_Start` has a call: when the saved hour count exceeds 999, it calls the observed `PlayTimeCounter_SetToMax` entry. Reset clears the state and all four saved counters, Stop clears only the state, and SetToMax stores state 2 with 999:59:59 plus 59 VBlanks.

Save access is recorded as `{save_storage}`. Names and behavior are corroborated by `{reference_repository}` commit `{reference_commit}`, `{reference_path}`.

No ROM instruction bytes are published.
"""
    report_path.write_text(report, encoding="utf-8", newline="\n")

    outputs = [source_path, *cfg_paths, map_path, report_path]
    manifest = {
        "schema_version": 1,
        "target": {"release": release, "sha256": digest},
        "functions": [name for _, name in FUNCTIONS],
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/play_time_controls.py",
            "tool_sha256": sha256(Path(__file__)),
        },
        "outputs": [
            {"path": path.relative_to(root).as_posix(), "sha256": sha256(path)}
            for path in outputs
        ],
        "raw_rom_bytes_included": False,
    }
    write_json(manifest_path, manifest)

    # The older Update evidence also hashes the shared source file.
    update_map_path = root / f"analysis/{prefix}-jp-play-time-counter-update-map.json"
    update_map = json.loads(update_map_path.read_text(encoding="utf-8"))
    update_map["source_sha256"] = source_digest
    write_json(update_map_path, update_map)
    update_manifest_path = root / "manifests/play-time-counter-update-reconstruction.json"
    update_manifest = json.loads(update_manifest_path.read_text(encoding="utf-8"))
    for output in update_manifest["outputs"]:
        output["sha256"] = sha256(root / output["path"])
    write_json(update_manifest_path, update_manifest)
    return [*outputs, manifest_path, update_map_path, update_manifest_path]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--save-storage", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    parser.add_argument("--reference-path", default="src/play_time.c")
    args = parser.parse_args()
    try:
        build_evidence(
            args.root,
            args.rom,
            args.expected_sha256,
            args.release,
            args.prefix,
            args.save_storage,
            args.reference_repository,
            args.reference_commit,
            args.reference_path,
        )
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
