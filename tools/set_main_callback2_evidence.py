#!/usr/bin/env python3
"""Verify the SetMainCallback2 reconstruction across a GBA release catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thumb_cfg


ORIGIN_STATE_OFFSET = 0x438
VALID_STATE_OFFSETS = {0x438, 0x43C}
CALLBACK2_OFFSET = 4
THUMB_BX_LR = 0x4770


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


def literal_offset(instruction_offset: int, immediate_words: int) -> int:
    return ((instruction_offset + 4) & ~3) + immediate_words * 4


def halfwords(data: bytes, offset: int, count: int) -> tuple[int, ...] | None:
    if offset < 0 or offset + count * 2 > len(data) or offset % 2:
        return None
    return struct.unpack_from(f"<{count}H", data, offset)


def is_ldr_literal(value: int, register: int, words: int) -> bool:
    return value & 0xF800 == 0x4800 and (value >> 8) & 7 == register and value & 0xFF == words


def is_str_word(value: int, source: int, base: int, byte_offset: int) -> bool:
    return (
        value & 0xF800 == 0x6000
        and value & 7 == source
        and (value >> 3) & 7 == base
        and ((value >> 6) & 0x1F) * 4 == byte_offset
    )


def is_mov_immediate(value: int, register: int, immediate: int) -> bool:
    return value & 0xF800 == 0x2000 and (value >> 8) & 7 == register and value & 0xFF == immediate


def is_lsl_immediate(value: int, destination: int, source: int, amount: int) -> bool:
    return (
        value & 0xF800 == 0
        and value & 7 == destination
        and (value >> 3) & 7 == source
        and (value >> 6) & 0x1F == amount
    )


def is_add_register(value: int, destination: int, left: int, right: int) -> bool:
    return (
        value & 0xFE00 == 0x1800
        and value & 7 == destination
        and (value >> 3) & 7 == left
        and (value >> 6) & 7 == right
    )


def is_str_byte(value: int, source: int, base: int, byte_offset: int) -> bool:
    return (
        value & 0xF800 == 0x7000
        and value & 7 == source
        and (value >> 3) & 7 == base
        and (value >> 6) & 0x1F == byte_offset
    )


def semantic_variant(data: bytes, offset: int, variant: str) -> bool:
    count = 8 if variant == "inline-state-offset" else 7
    words = halfwords(data, offset, count)
    if words is None:
        return False
    common_start = is_ldr_literal(words[0], 1, 3) and is_str_word(words[1], 0, 1, CALLBACK2_OFFSET)
    if variant == "inline-state-offset":
        return common_start and all(
            (
                is_mov_immediate(words[2], 0, 0x87),
                is_lsl_immediate(words[3], 0, 0, 3),
                is_add_register(words[4], 1, 1, 0),
                is_mov_immediate(words[5], 0, 0),
                is_str_byte(words[6], 0, 1, 0),
                words[7] == THUMB_BX_LR,
            )
        )
    return common_start and all(
        (
            is_ldr_literal(words[2], 0, 3),
            is_add_register(words[3], 1, 1, 0),
            is_mov_immediate(words[4], 0, 0),
            is_str_byte(words[5], 0, 1, 0),
            words[6] == THUMB_BX_LR,
        )
    )


def unique_candidate(data: bytes) -> dict[str, int | str]:
    candidates: list[dict[str, int | str]] = []
    return_encoding = struct.pack("<H", THUMB_BX_LR)
    return_offset = 0
    while True:
        return_offset = data.find(return_encoding, return_offset)
        if return_offset < 0:
            break
        if return_offset % 2:
            return_offset += 1
            continue
        for variant, length in (("inline-state-offset", 16), ("literal-state-offset", 14)):
            offset = return_offset - length + 2
            if not semantic_variant(data, offset, variant):
                continue
            main_literal = literal_offset(offset, 3)
            if main_literal + 4 > len(data):
                continue
            main_address = struct.unpack_from("<I", data, main_literal)[0]
            if not 0x03000000 <= main_address < 0x03008000:
                continue
            state_offset = ORIGIN_STATE_OFFSET
            if variant == "literal-state-offset":
                state_literal = literal_offset(offset + 4, 3)
                if state_literal + 4 > len(data):
                    continue
                state_offset = struct.unpack_from("<I", data, state_literal)[0]
                if state_offset not in VALID_STATE_OFFSETS:
                    continue
            candidates.append(
                {
                    "offset": offset,
                    "length": length,
                    "variant": variant,
                    "g_main_address": main_address,
                    "state_offset": state_offset,
                }
            )
        return_offset += 2
    if len(candidates) != 1:
        raise ValueError(f"expected one SetMainCallback2 candidate, found {len(candidates)}")
    return candidates[0]


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
    source_path = Path("src/main_callbacks.c")
    source = (root / source_path).read_text(encoding="utf-8")
    if "SetMainCallback2" not in source or "callback2" not in source:
        raise ValueError("existing main callback reconstruction is missing SetMainCallback2")
    source_sha256 = file_hash(root / source_path)
    roms = rom_index(rom_dir)
    outputs: list[Path] = [source_path, catalog_path]
    records = []

    for index, release in enumerate(releases):
        release_id = release["id"]
        sha256 = release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        candidate = unique_candidate(data)
        offset = int(candidate["offset"])
        length = int(candidate["length"])
        cfg = thumb_cfg.omit_raw_halfwords(
            thumb_cfg.trace_thumb_function(data, offset, max_span=length)
        )
        cfg.update({"source_size": len(data), "source_sha256": sha256})
        expected_end = 0x08000000 + offset + length
        if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or cfg["calls"]:
            raise ValueError(f"CFG boundary mismatch: {release_id}")
        cfg_path = Path(f"analysis/{release_id}-set-main-callback2-cfg.json")
        write_json(root / cfg_path, cfg)

        code = data[offset:offset + length]
        mapping = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "source": source_path.as_posix(),
            "source_sha256": source_sha256,
            "function": {
                "name": "SetMainCallback2",
                "address": f"0x{0x08000000 + offset:08X}",
                "range_end_exclusive": f"0x{expected_end:08X}",
                "compiler_variant": candidate["variant"],
                "rom_code_range": {
                    "start_offset": offset,
                    "end_offset_exclusive": offset + length,
                    "length": length,
                    "sha256": digest(code),
                    "raw_bytes_published": False,
                },
                "cfg": cfg_path.as_posix(),
            },
            "state": {
                "gMain": f"0x{int(candidate['g_main_address']):08X}",
                "callback2_offset": CALLBACK2_OFFSET,
                "state_offset": int(candidate["state_offset"]),
                "state_value": 0,
            },
            "behavior": [
                "store callback argument in gMain.callback2",
                "clear gMain.state",
                "return without calls",
            ],
            "origin_reference": index == 0,
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "src/main.c",
                "match_kind": "Thumb data-access and leaf-control-flow equivalence",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-set-main-callback2-map.json")
        write_json(root / map_path, mapping)
        outputs.extend((cfg_path, map_path))
        records.append(
            {
                "id": release_id,
                "language": release["language"],
                "revision": release["revision"],
                "build_kind": release["build_kind"],
                "sha256": sha256,
                "origin_reference": index == 0,
                "address": mapping["function"]["address"],
                "code_sha256": mapping["function"]["rom_code_range"]["sha256"],
                "compiler_variant": candidate["variant"],
                "g_main_address": mapping["state"]["gMain"],
                "state_offset": mapping["state"]["state_offset"],
                "evidence": {"map": map_path.as_posix(), "cfg": cfg_path.as_posix()},
            }
        )

    summary = {
        "schema_version": 1,
        "game": game,
        "function": "SetMainCallback2",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "proven_callback2_offset": CALLBACK2_OFFSET,
        "observed_state_offsets": sorted({int(item["state_offset"]) for item in records}),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/set-main-callback2-catalog-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)

    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    variants = ", ".join(sorted({str(item["compiler_variant"]) for item in records}))
    research_path = Path("research/set-main-callback2-global-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} SetMainCallback2 global reconstruction\n\n"
        f"The existing Japanese reconstruction remains the origin reference. All {len(records)} "
        f"cataloged releases ({languages}) independently prove the same leaf behavior: the "
        "argument is stored at `gMain + 0x4`, a release-specific state byte at "
        f"`gMain + {', '.join(f'0x{x:X}' for x in sorted({int(item['state_offset']) for item in records}))}` is cleared, "
        f"and the function returns without a call. Observed compiler forms: {variants}.\n\n"
        "Per-release maps retain addresses, code-range hashes, RAM addresses, and raw-free "
        "control-flow evidence. No ROM instruction bytes are published. Names and behavior "
        f"are corroborated by `{reference_repository}` at `{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8",
        newline="\n",
    )
    outputs.append(research_path)

    test_path = Path("tests/test_set_main_callback2_catalog.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "game": game,
        "function": "SetMainCallback2",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/set_main_callback2_evidence.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/set-main-callback2-catalog-reconstruction.json", manifest)
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
