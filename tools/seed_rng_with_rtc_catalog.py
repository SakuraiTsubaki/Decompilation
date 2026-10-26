#!/usr/bin/env python3
"""Reconstruct SeedRngWithRtc across Ruby and Sapphire release catalogs."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thumb_cfg


FUNCTION_LENGTH = 24
LITERAL_OFFSET = 24
MASK_LITERAL = 0x0000FFFF
PREFIX = bytes.fromhex("00b5")
MIDDLE = (0x1C02, 0x0C10, 0x4903, 0x4011, 0x4048)
EPILOGUE = (0xBC01, 0x4700)


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


def matching_offsets(data: bytes) -> list[int]:
    matches = []
    start = 0
    while True:
        offset = data.find(PREFIX, start)
        if offset < 0:
            break
        if offset % 2 == 0 and offset + LITERAL_OFFSET + 4 <= len(data):
            words = struct.unpack_from("<12H", data, offset)
            if (
                is_bl(words[1], words[2])
                and words[3:8] == MIDDLE
                and is_bl(words[8], words[9])
                and words[10:12] == EPILOGUE
                and struct.unpack_from("<I", data, offset + LITERAL_OFFSET)[0] == MASK_LITERAL
            ):
                matches.append(offset)
        start = offset + 2
    return matches


def unique_function_offset(data: bytes) -> int:
    matches = matching_offsets(data)
    if len(matches) != 1:
        raise ValueError(f"expected one SeedRngWithRtc candidate, found {len(matches)}")
    return matches[0]


def reconstructed_source() -> str:
    return """#include <stdint.h>

extern uint32_t RtcGetMinuteCount(void);
extern void SeedRng(uint16_t seed);

void SeedRngWithRtc(void)
{
    uint32_t seed = RtcGetMinuteCount();
    seed = (seed >> 16) ^ (seed & 0xFFFF);
    SeedRng((uint16_t)seed);
}
"""


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str, reference_commit: str) -> dict[str, object]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    source_path = Path("src/seed_rng_with_rtc.c")
    (root / source_path).write_text(reconstructed_source(), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    outputs: list[Path] = [source_path, catalog_path]
    records = []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        offset = unique_function_offset(data)
        cfg = thumb_cfg.omit_raw_halfwords(thumb_cfg.trace_thumb_function(data, offset, max_span=FUNCTION_LENGTH))
        cfg.update({"source_size": len(data), "source_sha256": sha256})
        expected_end = 0x08000000 + offset + FUNCTION_LENGTH
        if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or len(cfg["calls"]) != 2:
            raise ValueError(f"CFG boundary mismatch: {release_id}")
        cfg_path = Path(f"analysis/{release_id}-seed-rng-with-rtc-cfg.json")
        write_json(root / cfg_path, cfg)
        calls = [
            {"name": name, "source": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"}
            for name, call in zip(("RtcGetMinuteCount", "SeedRng"), cfg["calls"])
        ]
        code = data[offset:offset + FUNCTION_LENGTH]
        mapping = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "source": source_path.as_posix(),
            "source_sha256": source_sha256,
            "function": {"name": "SeedRngWithRtc", "address": f"0x{0x08000000 + offset:08X}", "range_end_exclusive": f"0x{expected_end:08X}", "rom_code_range": {"start_offset": offset, "end_offset_exclusive": offset + FUNCTION_LENGTH, "length": FUNCTION_LENGTH, "sha256": digest(code), "raw_bytes_published": False}, "cfg": cfg_path.as_posix()},
            "calls": calls,
            "behavior": {"input": "RtcGetMinuteCount 32-bit result", "fold": "upper 16 bits XOR lower 16 bits", "mask_literal": "0x0000FFFF", "seed_width_bits": 16},
            "origin_reference": index == 0,
            "naming_basis": {"repository": "pret/pokeruby", "commit": reference_commit, "path": "src/main.c", "match_kind": "Thumb control flow, 0xFFFF literal, call order, and XOR fold", "raw_rom_bytes_published": False},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-seed-rng-with-rtc-map.json")
        write_json(root / map_path, mapping)
        outputs.extend((cfg_path, map_path))
        records.append({"id": release_id, "language": release["language"], "revision": release["revision"], "build_kind": release["build_kind"], "sha256": sha256, "origin_reference": index == 0, "address": mapping["function"]["address"], "code_sha256": mapping["function"]["rom_code_range"]["sha256"], "calls": calls, "evidence": {"map": map_path.as_posix(), "cfg": cfg_path.as_posix()}})

    summary = {"schema_version": 1, "game": game, "function": "SeedRngWithRtc", "origin_reference": releases[0]["id"], "release_count": len(records), "source": source_path.as_posix(), "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/seed-rng-with-rtc-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/seed-rng-with-rtc-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} SeedRngWithRtc reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. All {len(records)} cataloged releases ({languages}) contain exactly one matching 24-byte Thumb function followed by the required 0x0000FFFF mask literal. The function obtains an RTC minute count, XOR-folds its upper and lower 16-bit halves, and passes the result to `SeedRng`.\n\n"
        "The reconstructed C source contains no ROM instructions. Per-release CFGs omit raw halfwords, while maps preserve ranges, hashes and the release-specific `RtcGetMinuteCount` and `SeedRng` targets. "
        f"Naming and semantics are corroborated by `pret/pokeruby` at `{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8", newline="\n")
    outputs.append(research_path)
    test_path = Path("tests/test_seed_rng_with_rtc_reconstruction.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {"schema_version": 1, "game": game, "function": "SeedRngWithRtc", "origin_reference": releases[0]["id"], "release_count": len(records), "generator": {"repository": "SakuraiTsubaki/Decompilation", "tool": "tools/seed_rng_with_rtc_catalog.py", "tool_sha256": file_hash(Path(__file__))}, "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs], "raw_rom_bytes_included": False}
    write_json(root / "manifests/seed-rng-with-rtc-reconstruction.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("analysis/global-release-catalog.json"))
    parser.add_argument("--game", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
