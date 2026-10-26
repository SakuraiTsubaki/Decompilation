#!/usr/bin/env python3
"""Reconstruct InitMapMusic and MapMusicMain across Gen III release catalogs."""
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
INIT_LENGTH = 16
MAIN_RELATIVE = 20
MAIN_LENGTH = 232
INIT_PREFIX = (0xB500, 0x4903, 0x2000, 0x7008)
INIT_EPILOGUE = (0xBC01, 0x4700)
CALL_NAMES = (
    "PlayBGM", "IsBGMStopped", "IsBGMStopped", "IsFanfareTaskInactive",
    "PlayBGM", "IsBGMStopped", "IsFanfareTaskInactive", "FadeInNewBGM",
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


def is_bl(first: int, second: int) -> bool:
    return first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def bl_target(offset: int, first: int, second: int) -> int:
    delta = sign_extend(((first & 0x7FF) << 12) | ((second & 0x7FF) << 1), 23)
    return ROM_BASE + offset + 12 + delta


def matching_init_offsets(data: bytes) -> list[int]:
    needle = struct.pack("<4H", *INIT_PREFIX)
    result = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            break
        if offset % 2 == 0 and offset + INIT_LENGTH + 4 <= len(data):
            words = struct.unpack_from("<8H", data, offset)
            expected_reset = ROM_BASE + offset + 0x10C
            if (is_bl(words[4], words[5]) and words[6:8] == INIT_EPILOGUE
                    and bl_target(offset, words[4], words[5]) == expected_reset):
                disable_music = struct.unpack_from("<I", data, offset + INIT_LENGTH)[0]
                if 0x03000000 <= disable_music <= 0x03007FFF:
                    result.append(offset)
        start = offset + 2
    return result


def unique_init_offset(data: bytes) -> int:
    matches = matching_init_offsets(data)
    if len(matches) != 1:
        raise ValueError(f"expected one InitMapMusic candidate, found {len(matches)}")
    return matches[0]


def init_source() -> str:
    return """#include <stdint.h>

typedef uint8_t bool8;

enum
{
    FALSE = 0
};

extern bool8 gDisableMusic;
extern void ResetMapMusic(void);

void InitMapMusic(void)
{
    gDisableMusic = FALSE;
    ResetMapMusic();
}
"""


def main_source() -> str:
    return """#include <stdint.h>

typedef uint8_t bool8;
typedef uint8_t u8;
typedef uint16_t u16;

extern u16 sCurrentMapMusic;
extern u16 sNextMapMusic;
extern u8 sMapMusicState;
extern u8 sMapMusicFadeInSpeed;

extern void PlayBGM(u16 songNum);
extern bool8 IsBGMStopped(void);
extern bool8 IsFanfareTaskInactive(void);
extern void FadeInNewBGM(u16 songNum, u8 speed);

void MapMusicMain(void)
{
    switch (sMapMusicState)
    {
    case 0:
        break;
    case 1:
        sMapMusicState = 2;
        PlayBGM(sCurrentMapMusic);
        break;
    case 2:
    case 3:
    case 4:
        break;
    case 5:
        if (IsBGMStopped())
        {
            sNextMapMusic = 0;
            sMapMusicState = 0;
        }
        break;
    case 6:
        if (IsBGMStopped() && IsFanfareTaskInactive())
        {
            sCurrentMapMusic = sNextMapMusic;
            sNextMapMusic = 0;
            sMapMusicState = 2;
            PlayBGM(sCurrentMapMusic);
        }
        break;
    case 7:
        if (IsBGMStopped() && IsFanfareTaskInactive())
        {
            FadeInNewBGM(sNextMapMusic, sMapMusicFadeInSpeed);
            sCurrentMapMusic = sNextMapMusic;
            sNextMapMusic = 0;
            sMapMusicState = 2;
            sMapMusicFadeInSpeed = 0;
        }
        break;
    }
}
"""


def trace(data: bytes, offset: int, length: int, call_names: tuple[str, ...]) -> tuple[dict[str, object], list[dict[str, str]]]:
    cfg = thumb_cfg.omit_raw_halfwords(thumb_cfg.trace_thumb_function(data, offset, max_span=length))
    expected_end = ROM_BASE + offset + length
    calls = sorted(cfg["calls"], key=lambda item: item["source"])
    if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or len(calls) != len(call_names):
        raise ValueError("music CFG boundary mismatch")
    named_calls = [
        {"name": name, "source": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"}
        for name, call in zip(call_names, calls)
    ]
    compact = {
        "instruction_halfwords": cfg["instruction_halfwords"],
        "edge_count": len(cfg["edges"]), "return_count": len(cfg["returns"]),
        "call_count": len(calls), "raw_halfwords_omitted": True,
    }
    return compact, named_calls


def jump_table_record(data: bytes, main_offset: int, cfg: dict[str, object]) -> dict[str, object]:
    branches = [item for item in cfg["instructions"] if item["kind"] == "jump-table-branch"]
    if len(branches) != 1 or len(branches[0]["targets"]) != 8:
        raise ValueError("expected one eight-case MapMusicMain jump table")
    branch = branches[0]
    if branch["table_address"] != ROM_BASE + main_offset + 32:
        raise ValueError("unexpected MapMusicMain jump table position")
    targets = branch["targets"]
    if not (targets[0] == targets[2] == targets[3] == targets[4]):
        raise ValueError("idle MapMusicMain cases do not share one target")
    return {"address": f"0x{branch['table_address']:08X}", "cases": {str(index): f"0x{target:08X}" for index, target in enumerate(targets)}}


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          reference_repository: str, reference_commit: str) -> dict[str, object]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    init_source_path = Path("src/init_map_music.c")
    main_source_path = Path("src/map_music_main.c")
    (root / init_source_path).write_text(init_source(), encoding="utf-8", newline="\n")
    (root / main_source_path).write_text(main_source(), encoding="utf-8", newline="\n")
    init_source_sha = file_hash(root / init_source_path)
    main_source_sha = file_hash(root / main_source_path)
    init_maps = []
    main_maps = []
    records = []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        init_offset = unique_init_offset(data)
        main_offset = init_offset + MAIN_RELATIVE
        init_flow, init_calls = trace(data, init_offset, INIT_LENGTH, ("ResetMapMusic",))
        full_cfg = thumb_cfg.omit_raw_halfwords(thumb_cfg.trace_thumb_function(data, main_offset, max_span=MAIN_LENGTH))
        main_calls = sorted(full_cfg["calls"], key=lambda item: item["source"])
        if full_cfg["range_end"] != ROM_BASE + main_offset + MAIN_LENGTH or len(full_cfg["returns"]) != 1 or len(main_calls) != 8:
            raise ValueError(f"MapMusicMain CFG mismatch: {release_id}")
        named_calls = [
            {"name": name, "source": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"}
            for name, call in zip(CALL_NAMES, main_calls)
        ]
        if not (named_calls[0]["target"] == named_calls[4]["target"] and named_calls[1]["target"] == named_calls[2]["target"] == named_calls[5]["target"] and named_calls[3]["target"] == named_calls[6]["target"]):
            raise ValueError(f"MapMusicMain repeated call targets disagree: {release_id}")
        jump_table = jump_table_record(data, main_offset, full_cfg)
        disable_music = struct.unpack_from("<I", data, init_offset + INIT_LENGTH)[0]
        common = {
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "naming_basis": {"repository": reference_repository, "commit": reference_commit, "path": "src/sound.c", "raw_rom_bytes_published": False},
            "raw_rom_bytes_included": False,
        }
        init_map = {
            "schema_version": 1, **common,
            "source": init_source_path.as_posix(), "source_sha256": init_source_sha,
            "function": {"name": "InitMapMusic", "address": f"0x{ROM_BASE + init_offset:08X}", "range_end_exclusive": f"0x{ROM_BASE + init_offset + INIT_LENGTH:08X}", "rom_code_range": {"start_offset": init_offset, "end_offset_exclusive": init_offset + INIT_LENGTH, "length": INIT_LENGTH, "sha256": digest(data[init_offset:init_offset + INIT_LENGTH]), "raw_bytes_published": False}, "control_flow": init_flow},
            "calls": init_calls,
            "literal_addresses": {"gDisableMusic": f"0x{disable_music:08X}"},
            "behavior": {"disable_music_value": 0, "then_calls": "ResetMapMusic"},
        }
        main_map = {
            "schema_version": 1, **common,
            "source": main_source_path.as_posix(), "source_sha256": main_source_sha,
            "function": {"name": "MapMusicMain", "address": f"0x{ROM_BASE + main_offset:08X}", "range_end_exclusive": f"0x{ROM_BASE + main_offset + MAIN_LENGTH:08X}", "rom_code_range": {"start_offset": main_offset, "end_offset_exclusive": main_offset + MAIN_LENGTH, "length": MAIN_LENGTH, "sha256": digest(data[main_offset:main_offset + MAIN_LENGTH]), "raw_bytes_published": False}, "control_flow": {"instruction_halfwords": full_cfg["instruction_halfwords"], "edge_count": len(full_cfg["edges"]), "return_count": len(full_cfg["returns"]), "call_count": len(main_calls), "raw_halfwords_omitted": True}},
            "jump_table": jump_table,
            "calls": named_calls,
            "behavior": {"state_cases": list(range(8)), "shared_idle_target_cases": [0, 2, 3, 4]},
        }
        init_path = Path(f"analysis/{release_id}-init-map-music-map.json")
        main_path = Path(f"analysis/{release_id}-map-music-main-map.json")
        write_json(root / init_path, init_map)
        write_json(root / main_path, main_map)
        init_maps.append(init_path)
        main_maps.append(main_path)
        records.append({
            "id": release_id, "language": release["language"], "revision": release["revision"], "build_kind": release["build_kind"], "sha256": sha256,
            "origin_reference": index == 0,
            "init_address": init_map["function"]["address"], "main_address": main_map["function"]["address"],
            "init_code_sha256": init_map["function"]["rom_code_range"]["sha256"], "main_code_sha256": main_map["function"]["rom_code_range"]["sha256"],
            "evidence": {"init": init_path.as_posix(), "main": main_path.as_posix()},
        })

    summary = {"schema_version": 1, "game": game, "functions": ["InitMapMusic", "MapMusicMain"], "origin_reference": releases[0]["id"], "release_count": len(records), "sources": [init_source_path.as_posix(), main_source_path.as_posix()], "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/map-music-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(record["language"] for record in records))
    init_research = Path("research/init-map-music-reconstruction.md")
    main_research = Path("research/map-music-main-reconstruction.md")
    (root / init_research).write_text(f"# {game} InitMapMusic reconstruction\n\nThe Japanese release `{releases[0]['id']}` is the origin reference. All {len(releases)} cataloged releases ({languages}) contain exactly one verified InitMapMusic routine. It clears the release-specific IWRAM gDisableMusic byte and calls ResetMapMusic. Per-release maps preserve ranges, hashes, call targets and raw-free control flow. No ROM instruction bytes are published. Naming is corroborated by `{reference_repository}` at `{reference_commit}`, `src/sound.c`.\n", encoding="utf-8", newline="\n")
    (root / main_research).write_text(f"# {game} MapMusicMain reconstruction\n\nThe Japanese release `{releases[0]['id']}` is the origin reference. All {len(releases)} cataloged releases ({languages}) contain the adjacent 232-byte MapMusicMain state machine with eight jump-table cases. Cases 0, 2, 3 and 4 share the idle target; repeated PlayBGM, IsBGMStopped and IsFanfareTaskInactive targets agree inside every release. Per-release maps contain hashes, calls and raw-free control-flow summaries. No ROM instruction bytes are published. Naming is corroborated by `{reference_repository}` at `{reference_commit}`, `src/sound.c`.\n", encoding="utf-8", newline="\n")
    init_test = Path("tests/test_init_map_music_reconstruction.py")
    main_test = Path("tests/test_map_music_main_reconstruction.py")
    common_outputs = [catalog_path, summary_path]
    init_outputs = [init_source_path, *common_outputs, *init_maps, init_research, init_test]
    main_outputs = [main_source_path, *common_outputs, *main_maps, main_research, main_test]
    missing = [path.as_posix() for path in init_outputs + main_outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(dict.fromkeys(missing)))
    generator = {"repository": "SakuraiTsubaki/Decompilation", "tool": "tools/map_music_catalog.py", "tool_sha256": file_hash(Path(__file__))}
    write_json(root / "manifests/init-map-music-reconstruction.json", {"schema_version": 1, "game": game, "function": "InitMapMusic", "origin_reference": releases[0]["id"], "release_count": len(releases), "generator": generator, "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in init_outputs], "raw_rom_bytes_included": False})
    write_json(root / "manifests/map-music-main-reconstruction.json", {"schema_version": 1, "game": game, "function": "MapMusicMain", "origin_reference": releases[0]["id"], "release_count": len(releases), "generator": generator, "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in main_outputs], "raw_rom_bytes_included": False})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("analysis/global-release-catalog.json"))
    parser.add_argument("--game", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.reference_repository, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
