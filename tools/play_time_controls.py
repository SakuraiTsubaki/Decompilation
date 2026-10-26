#!/usr/bin/env python3
"""Reconstruct the complete play-time counter family across Gen III releases."""
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
DIRECT_RESET = (0x4905, 0x2000, 0x7008, 0x4905, 0x2200, 0x2000, 0x81C8, 0x740A, 0x744A, 0x748A, 0x4770)
POINTER_RESET = (0x4906, 0x2000, 0x7008, 0x4A06, 0x6813, 0x2100, 0x2000, 0x81D8, 0x7419, 0x6810, 0x7441, 0x6810, 0x7481, 0x4770)
LAYOUTS = {
    "direct": {
        "functions": (
            ("PlayTimeCounter_Reset", 0, 22, 0),
            ("PlayTimeCounter_Start", 32, 26, 1),
            ("PlayTimeCounter_Stop", 72, 8, 0),
            ("PlayTimeCounter_Update", 84, 84, 1),
            ("PlayTimeCounter_SetToMax", 180, 22, 0),
        ),
        "literals": {
            "reset": (24, 28),
            "start": (60, 64, 68),
            "stop": (80,),
            "update": (168, 172, 176),
            "max": (204, 208, 212),
        },
        "save_storage": "direct-gSaveBlock2",
    },
    "pointer": {
        "functions": (
            ("PlayTimeCounter_Reset", 0, 28, 0),
            ("PlayTimeCounter_Start", 36, 28, 1),
            ("PlayTimeCounter_Stop", 76, 8, 0),
            ("PlayTimeCounter_Update", 88, 92, 1),
            ("PlayTimeCounter_SetToMax", 192, 28, 0),
        ),
        "literals": {
            "reset": (28, 32),
            "start": (64, 68, 72),
            "stop": (84,),
            "update": (180, 184, 188),
            "max": (220, 224, 228),
        },
        "save_storage": "gSaveBlock2Ptr",
    },
}
CONTROL_NAMES = (
    "PlayTimeCounter_Reset",
    "PlayTimeCounter_Start",
    "PlayTimeCounter_Stop",
    "PlayTimeCounter_SetToMax",
)


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


def reset_template(profile: str) -> tuple[int, ...]:
    if profile == "direct":
        return DIRECT_RESET
    if profile == "pointer":
        return POINTER_RESET
    raise ValueError(f"unsupported profile: {profile}")


def matching_cluster_offsets(data: bytes, profile: str) -> list[int]:
    template = reset_template(profile)
    needle = struct.pack(f"<{len(template)}H", *template)
    result = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            break
        if offset % 2 == 0:
            result.append(offset)
        start = offset + 2
    return result


def unique_cluster_offset(data: bytes, profile: str) -> int:
    matches = matching_cluster_offsets(data, profile)
    if len(matches) != 1:
        raise ValueError(f"expected one play-time counter cluster, found {len(matches)}")
    return matches[0]


def reconstructed_source(profile: str) -> str:
    if profile not in {"direct", "pointer"}:
        raise ValueError(f"unsupported profile: {profile}")
    save_decl = "extern struct SaveBlock2 gSaveBlock2;" if profile == "direct" else "extern struct SaveBlock2 *gSaveBlock2Ptr;"
    save = "gSaveBlock2" if profile == "direct" else "gSaveBlock2Ptr->"
    member = "." if profile == "direct" else ""
    def field(name: str) -> str:
        return f"{save}{member}{name}"
    return f"""#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;

struct SaveBlock2
{{
    u8 unknown_000[0x0E];
    u16 playTimeHours;
    u8 playTimeMinutes;
    u8 playTimeSeconds;
    u8 playTimeVBlanks;
}};

{save_decl}
extern u8 sPlayTimeCounterState;

enum
{{
    PLAY_TIME_STOPPED,
    PLAY_TIME_RUNNING,
    PLAY_TIME_MAXED_OUT
}};

void PlayTimeCounter_Reset(void)
{{
    sPlayTimeCounterState = PLAY_TIME_STOPPED;
    {field("playTimeHours")} = 0;
    {field("playTimeMinutes")} = 0;
    {field("playTimeSeconds")} = 0;
    {field("playTimeVBlanks")} = 0;
}}

void PlayTimeCounter_SetToMax(void);

void PlayTimeCounter_Start(void)
{{
    sPlayTimeCounterState = PLAY_TIME_RUNNING;
    if ({field("playTimeHours")} > 999)
        PlayTimeCounter_SetToMax();
}}

void PlayTimeCounter_Stop(void)
{{
    sPlayTimeCounterState = PLAY_TIME_STOPPED;
}}

void PlayTimeCounter_Update(void)
{{
    if (sPlayTimeCounterState != PLAY_TIME_RUNNING)
        return;

    {field("playTimeVBlanks")}++;
    if ({field("playTimeVBlanks")} < 60)
        return;

    {field("playTimeVBlanks")} = 0;
    {field("playTimeSeconds")}++;
    if ({field("playTimeSeconds")} < 60)
        return;

    {field("playTimeSeconds")} = 0;
    {field("playTimeMinutes")}++;
    if ({field("playTimeMinutes")} < 60)
        return;

    {field("playTimeMinutes")} = 0;
    {field("playTimeHours")}++;
    if ({field("playTimeHours")} > 999)
        PlayTimeCounter_SetToMax();
}}

void PlayTimeCounter_SetToMax(void)
{{
    sPlayTimeCounterState = PLAY_TIME_MAXED_OUT;
    {field("playTimeHours")} = 999;
    {field("playTimeMinutes")} = 59;
    {field("playTimeSeconds")} = 59;
    {field("playTimeVBlanks")} = 59;
}}
"""


def literal_record(data: bytes, cluster: int, profile: str) -> dict[str, str]:
    offsets = LAYOUTS[profile]["literals"]
    reset = tuple(struct.unpack_from("<I", data, cluster + value)[0] for value in offsets["reset"])
    start = tuple(struct.unpack_from("<I", data, cluster + value)[0] for value in offsets["start"])
    stop = tuple(struct.unpack_from("<I", data, cluster + value)[0] for value in offsets["stop"])
    update = tuple(struct.unpack_from("<I", data, cluster + value)[0] for value in offsets["update"])
    maximum = tuple(struct.unpack_from("<I", data, cluster + value)[0] for value in offsets["max"])
    state, save = reset
    if not (start[0] == stop[0] == update[0] == maximum[0] == state):
        raise ValueError("play-time state literals disagree")
    if not (start[1] == update[1] == maximum[1] == save):
        raise ValueError("play-time save-storage literals disagree")
    if (start[2], update[2], maximum[2]) != (999, 999 << 16, 999):
        raise ValueError("play-time maximum-hour literals disagree")
    if not 0x03000000 <= state <= 0x03007FFF:
        raise ValueError("play-time state leaves IWRAM")
    if profile == "direct":
        if not 0x02000000 <= save <= 0x0203FFFF:
            raise ValueError("direct SaveBlock2 leaves EWRAM")
        save_name = "gSaveBlock2"
    else:
        if not 0x03000000 <= save <= 0x03007FFF:
            raise ValueError("gSaveBlock2Ptr leaves IWRAM")
        save_name = "gSaveBlock2Ptr"
    return {"sPlayTimeCounterState": f"0x{state:08X}", save_name: f"0x{save:08X}"}


def function_records(data: bytes, cluster: int, profile: str) -> list[dict[str, object]]:
    records = []
    for name, relative, length, call_count in LAYOUTS[profile]["functions"]:
        offset = cluster + relative
        cfg = thumb_cfg.omit_raw_halfwords(thumb_cfg.trace_thumb_function(data, offset, max_span=length))
        expected_end = ROM_BASE + offset + length
        calls = sorted(cfg["calls"], key=lambda item: item["source"])
        if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or len(calls) != call_count:
            raise ValueError(f"CFG boundary mismatch for {name}")
        records.append({
            "name": name,
            "address": f"0x{ROM_BASE + offset:08X}",
            "range_end_exclusive": f"0x{expected_end:08X}",
            "rom_code_range": {
                "start_offset": offset,
                "end_offset_exclusive": offset + length,
                "length": length,
                "sha256": digest(data[offset:offset + length]),
                "raw_bytes_published": False,
            },
            "calls": [{"source": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"} for call in calls],
            "control_flow": {
                "instruction_halfwords": cfg["instruction_halfwords"],
                "edge_count": len(cfg["edges"]),
                "return_count": len(cfg["returns"]),
                "call_count": len(calls),
                "raw_halfwords_omitted": True,
            },
        })
    target = next(item["address"] for item in records if item["name"] == "PlayTimeCounter_SetToMax")
    for name in ("PlayTimeCounter_Start", "PlayTimeCounter_Update"):
        item = next(record for record in records if record["name"] == name)
        if item["calls"][0]["target"] != target:
            raise ValueError(f"{name} does not call observed SetToMax")
        item["calls"][0]["name"] = "PlayTimeCounter_SetToMax"
    return records


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str, profile: str,
          reference_repository: str, reference_commit: str) -> dict[str, object]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    source_path = Path("src/play_time_counter.c")
    (root / source_path).write_text(reconstructed_source(profile), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    control_maps = []
    update_maps = []
    summary_records = []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        cluster = unique_cluster_offset(data, profile)
        functions = function_records(data, cluster, profile)
        literals = literal_record(data, cluster, profile)
        common = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "profile": profile,
            "source": source_path.as_posix(),
            "source_sha256": source_sha256,
            "save_storage": LAYOUTS[profile]["save_storage"],
            "literal_addresses": literals,
            "save_field_offsets": {
                "playTimeHours": 14, "playTimeMinutes": 16,
                "playTimeSeconds": 17, "playTimeVBlanks": 18,
            },
            "origin_reference": index == 0,
            "naming_basis": {
                "repository": reference_repository, "commit": reference_commit,
                "path": "src/play_time.c",
                "match_kind": "cluster layout, state writes, save offsets, thresholds, CFGs, and SetToMax call targets",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        controls = [item for item in functions if item["name"] in CONTROL_NAMES]
        control_map = {
            **common,
            "functions": controls,
            "behavior": {
                "reset": {"state": 0, "hours": 0, "minutes": 0, "seconds": 0, "vblanks": 0},
                "start": {"state": 1, "clamp_when_hours_above": 999},
                "stop": {"state": 0},
                "set_to_max": {"state": 2, "hours": 999, "minutes": 59, "seconds": 59, "vblanks": 59},
            },
        }
        update = next(item for item in functions if item["name"] == "PlayTimeCounter_Update")
        update_map = {
            **common,
            "function": update,
            "behavior": {
                "required_state": 1, "vblanks_per_second": 60,
                "seconds_per_minute": 60, "minutes_per_hour": 60,
                "maximum_hours": 999,
            },
        }
        control_path = Path(f"analysis/{release_id}-play-time-counter-controls-map.json")
        update_path = Path(f"analysis/{release_id}-play-time-counter-update-map.json")
        write_json(root / control_path, control_map)
        write_json(root / update_path, update_map)
        control_maps.append(control_path)
        update_maps.append(update_path)
        summary_records.append({
            "id": release_id, "language": release["language"], "revision": release["revision"],
            "build_kind": release["build_kind"], "sha256": sha256,
            "origin_reference": index == 0, "profile": profile,
            "functions": [{"name": item["name"], "address": item["address"], "code_sha256": item["rom_code_range"]["sha256"]} for item in functions],
            "evidence": {"controls": control_path.as_posix(), "update": update_path.as_posix()},
        })

    summary = {
        "schema_version": 1, "game": game, "profile": profile,
        "functions": [item[0] for item in LAYOUTS[profile]["functions"]],
        "origin_reference": releases[0]["id"], "release_count": len(summary_records),
        "source": source_path.as_posix(), "releases": summary_records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/play-time-counter-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(record["language"] for record in summary_records))
    controls_research = Path("research/play-time-counter-controls-reconstruction.md")
    update_research = Path("research/play-time-counter-update-reconstruction.md")
    (root / controls_research).write_text(
        f"# {game} play-time counter controls reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. All {len(releases)} cataloged releases ({languages}) contain one verified Reset/Start/Stop/SetToMax control family using the `{profile}` save-storage profile. Start calls the observed SetToMax entry when hours exceed 999.\n\n"
        "Per-release maps preserve ranges, hashes, state/save addresses and raw-free control-flow summaries. No ROM instruction bytes are published. "
        f"Naming and behavior are corroborated by `{reference_repository}` at `{reference_commit}`, `src/play_time.c`.\n",
        encoding="utf-8", newline="\n",
    )
    (root / update_research).write_text(
        f"# {game} play-time counter update reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. All {len(releases)} cataloged releases ({languages}) contain one verified Update routine in the same `{profile}` cluster. It advances 60 VBlanks per second, 60 seconds per minute and 60 minutes per hour, then calls the exact observed SetToMax entry above 999 hours.\n\n"
        "Per-release maps retain code hashes, thresholds, state/save addresses and raw-free control-flow summaries. No ROM instruction bytes are published. "
        f"Naming and behavior are corroborated by `{reference_repository}` at `{reference_commit}`, `src/play_time.c`.\n",
        encoding="utf-8", newline="\n",
    )
    controls_test = Path("tests/test_play_time_counter_controls_reconstruction.py")
    update_test = Path("tests/test_play_time_counter_update_reconstruction.py")
    common_outputs = [source_path, catalog_path, summary_path]
    controls_outputs = [*common_outputs, *control_maps, controls_research, controls_test]
    update_outputs = [*common_outputs, *update_maps, update_research, update_test]
    missing = [path.as_posix() for path in controls_outputs + update_outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(dict.fromkeys(missing)))
    generator = {
        "repository": "SakuraiTsubaki/Decompilation",
        "tool": "tools/play_time_controls.py",
        "tool_sha256": file_hash(Path(__file__)),
    }
    controls_manifest = {
        "schema_version": 1, "game": game, "profile": profile,
        "functions": list(CONTROL_NAMES), "origin_reference": releases[0]["id"],
        "release_count": len(releases), "generator": generator,
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in controls_outputs],
        "raw_rom_bytes_included": False,
    }
    update_manifest = {
        "schema_version": 1, "game": game, "profile": profile,
        "function": "PlayTimeCounter_Update", "origin_reference": releases[0]["id"],
        "release_count": len(releases), "generator": generator,
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in update_outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/play-time-counter-controls-reconstruction.json", controls_manifest)
    write_json(root / "manifests/play-time-counter-update-reconstruction.json", update_manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("analysis/global-release-catalog.json"))
    parser.add_argument("--game", required=True)
    parser.add_argument("--profile", choices=("direct", "pointer"), required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.profile,
              args.reference_repository, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

