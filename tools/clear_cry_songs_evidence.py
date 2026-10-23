#!/usr/bin/env python3
"""Reconstruct ClearPokemonCrySongs across a Generation III release catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thumb_cfg


PREFIX = bytes.fromhex("00b581b06946002008800449044a6846")
EPILOGUE = bytes.fromhex("01b001bc0047")
FUNCTION_LENGTH = 26
DESTINATION_LITERAL_OFFSET = 28
MODE_LITERAL_OFFSET = 32
CPU_SET_MODE = 0x01000034
HALFWORD_COUNT = 0x34
BYTE_COUNT = HALFWORD_COUNT * 2


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def rom_index(directory: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() == ".gba":
            result.setdefault(file_hash(path), path)
    return result


def matching_offsets(data: bytes) -> list[int]:
    matches: list[int] = []
    start = 0
    while True:
        offset = data.find(PREFIX, start)
        if offset < 0:
            break
        if (
            offset % 2 == 0
            and data[offset + 20:offset + FUNCTION_LENGTH] == EPILOGUE
            and len(data) >= offset + MODE_LITERAL_OFFSET + 4
            and struct.unpack_from("<I", data, offset + MODE_LITERAL_OFFSET)[0] == CPU_SET_MODE
        ):
            matches.append(offset)
        start = offset + 2
    return matches


def unique_function_offset(data: bytes) -> int:
    matches = matching_offsets(data)
    if len(matches) != 1:
        raise ValueError(f"expected one ClearPokemonCrySongs candidate, found {len(matches)}")
    return matches[0]


def reconstructed_source() -> str:
    return """#include <stdint.h>

#define CPU_SET_SOURCE_FIXED (1u << 24)
#define POKEMON_CRY_SONG_BYTES 104u

extern uint8_t gPokemonCrySongs[POKEMON_CRY_SONG_BYTES];
extern void CpuSet(const void *source, void *destination, uint32_t mode);

void ClearPokemonCrySongs(void)
{
    const uint16_t zero = 0;
    CpuSet(&zero, gPokemonCrySongs,
           CPU_SET_SOURCE_FIXED | (POKEMON_CRY_SONG_BYTES / sizeof(uint16_t)));
}
"""


def build(
    root: Path,
    rom_dir: Path,
    catalog_path: Path,
    game: str,
    reference_repository: str,
    reference_commit: str,
) -> dict[str, object]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)

    source_path = Path("src/clear_pokemon_cry_songs.c")
    (root / source_path).parent.mkdir(parents=True, exist_ok=True)
    (root / source_path).write_text(reconstructed_source(), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    outputs: list[Path] = [source_path, catalog_path]
    records = []

    for index, release in enumerate(releases):
        release_id = release["id"]
        sha256 = release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        offset = unique_function_offset(data)
        destination = struct.unpack_from("<I", data, offset + DESTINATION_LITERAL_OFFSET)[0]
        if not 0x03000000 <= destination < 0x03008000:
            raise ValueError(f"unexpected destination address: {release_id}/0x{destination:08X}")
        cfg = thumb_cfg.omit_raw_halfwords(
            thumb_cfg.trace_thumb_function(data, offset, max_span=FUNCTION_LENGTH)
        )
        cfg.update({"source_size": len(data), "source_sha256": sha256})
        expected_end = 0x08000000 + offset + FUNCTION_LENGTH
        if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or len(cfg["calls"]) != 1:
            raise ValueError(f"CFG boundary mismatch: {release_id}")
        cfg_path = Path(f"analysis/{release_id}-clear-pokemon-cry-songs-cfg.json")
        write_json(root / cfg_path, cfg)
        code = data[offset:offset + FUNCTION_LENGTH]
        mapping = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "source": source_path.as_posix(),
            "source_sha256": source_sha256,
            "function": {
                "name": "ClearPokemonCrySongs",
                "address": f"0x{0x08000000 + offset:08X}",
                "range_end_exclusive": f"0x{expected_end:08X}",
                "rom_code_range": {
                    "start_offset": offset,
                    "end_offset_exclusive": offset + FUNCTION_LENGTH,
                    "length": FUNCTION_LENGTH,
                    "sha256": digest(code),
                    "raw_bytes_published": False,
                },
                "cfg": cfg_path.as_posix(),
            },
            "call": {"name": "CpuSet", "target": f"0x{cfg['calls'][0]['target']:08X}"},
            "state": {"gPokemonCrySongs": f"0x{destination:08X}", "byte_count": BYTE_COUNT},
            "behavior": {
                "fill_value": 0,
                "unit": "halfword",
                "halfword_count": HALFWORD_COUNT,
                "source_fixed": True,
                "cpu_set_mode": f"0x{CPU_SET_MODE:08X}",
            },
            "origin_reference": index == 0,
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "src/main.c",
                "match_kind": "Thumb control flow, CpuSet mode, destination class, and clear size",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-clear-pokemon-cry-songs-map.json")
        write_json(root / map_path, mapping)
        outputs.extend((cfg_path, map_path))
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "address": mapping["function"]["address"],
            "code_sha256": mapping["function"]["rom_code_range"]["sha256"],
            "destination": mapping["state"]["gPokemonCrySongs"],
            "cpu_set_target": mapping["call"]["target"],
            "evidence": {"map": map_path.as_posix(), "cfg": cfg_path.as_posix()},
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "function": "ClearPokemonCrySongs",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "cleared_byte_count": BYTE_COUNT,
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/clear-pokemon-cry-songs-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)

    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/clear-pokemon-cry-songs-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} ClearPokemonCrySongs reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. All "
        f"{len(records)} cataloged releases ({languages}) contain exactly one function "
        "with the same 26-byte Thumb structure: a zero halfword is placed on the stack, "
        "then `CpuSet` repeats it for 52 halfwords (104 bytes) into the release-specific "
        "`gPokemonCrySongs` address.\n\n"
        "The reconstructed C source expresses that behavior without embedding ROM "
        "instructions. Per-release maps retain function ranges, hashes, call targets, "
        "destination addresses, and raw-free control-flow evidence. Naming and semantics "
        f"are corroborated by `{reference_repository}` at `{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8",
        newline="\n",
    )
    outputs.append(research_path)

    test_path = Path("tests/test_clear_pokemon_cry_songs_reconstruction.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "game": game,
        "function": "ClearPokemonCrySongs",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/clear_cry_songs_evidence.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/clear-pokemon-cry-songs-reconstruction.json", manifest)
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
