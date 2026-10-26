#!/usr/bin/env python3
"""Verify DoSoftReset across a Generation III release catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thumb_cfg


REG_IME = 0x04000208
DMA1_BASE = 0x040000BC
DMA3_BASE = 0x040000D4
DMA_CLEAR_ENABLE = 0x0000C5FF
DMA_CLEAR_ALL = 0x00007FFF
THUMB_PUSH_R4_LR = 0xB510
THUMB_POP_R4 = 0xBC10
THUMB_POP_R0 = 0xBC01
THUMB_BX_R0 = 0x4700


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


def literal_offset(instruction_offset: int, halfword: int) -> int:
    return ((instruction_offset + 4) & ~3) + (halfword & 0xFF) * 4


def literal_value(data: bytes, function_offset: int, word_index: int, halfword: int) -> int | None:
    offset = literal_offset(function_offset + word_index * 2, halfword)
    if offset < 0 or offset + 4 > len(data):
        return None
    return struct.unpack_from("<I", data, offset)[0]


def is_ldr_literal(value: int, register: int) -> bool:
    return value & 0xF800 == 0x4800 and (value >> 8) & 7 == register


def is_mov_immediate(value: int, register: int, immediate: int) -> bool:
    return value & 0xF800 == 0x2000 and (value >> 8) & 7 == register and value & 0xFF == immediate


def is_halfword_access(value: int, load: bool, register: int, base: int, byte_offset: int) -> bool:
    opcode = 0x8800 if load else 0x8000
    return (
        value & 0xF800 == opcode
        and value & 7 == register
        and (value >> 3) & 7 == base
        and ((value >> 6) & 0x1F) * 2 == byte_offset
    )


def is_add_immediate3(value: int, destination: int, source: int, immediate: int) -> bool:
    return (
        value & 0xFE00 == 0x1C00
        and value & 7 == destination
        and (value >> 3) & 7 == source
        and (value >> 6) & 7 == immediate
    )


def is_add_immediate8(value: int, register: int, immediate: int) -> bool:
    return value & 0xF800 == 0x3000 and (value >> 8) & 7 == register and value & 0xFF == immediate


def is_and(value: int, destination: int, source: int) -> bool:
    return value & 0xFFC0 == 0x4000 and value & 7 == destination and (value >> 3) & 7 == source


def is_bl_pair(first: int, second: int) -> bool:
    return first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def dma_sequence(words: tuple[int, ...]) -> bool:
    return all(
        (
            is_ldr_literal(words[8], 1),
            is_halfword_access(words[9], True, 2, 1, 10),
            is_ldr_literal(words[10], 3),
            is_add_immediate3(words[11], 0, 3, 0),
            is_and(words[12], 0, 2),
            is_halfword_access(words[13], False, 0, 1, 10),
            is_halfword_access(words[14], True, 4, 1, 10),
            is_ldr_literal(words[15], 2),
            is_add_immediate3(words[16], 0, 2, 0),
            is_and(words[17], 0, 4),
            is_halfword_access(words[18], False, 0, 1, 10),
            is_halfword_access(words[19], True, 0, 1, 10),
            is_add_immediate8(words[20], 1, 12),
            is_halfword_access(words[21], True, 4, 1, 10),
            is_add_immediate3(words[22], 0, 3, 0),
            is_and(words[23], 0, 4),
            is_halfword_access(words[24], False, 0, 1, 10),
            is_halfword_access(words[25], True, 4, 1, 10),
            is_add_immediate3(words[26], 0, 2, 0),
            is_and(words[27], 0, 4),
            is_halfword_access(words[28], False, 0, 1, 10),
            is_halfword_access(words[29], True, 0, 1, 10),
            is_ldr_literal(words[30], 0),
            is_halfword_access(words[31], True, 1, 0, 10),
            is_and(words[32], 3, 1),
            is_halfword_access(words[33], False, 3, 0, 10),
            is_halfword_access(words[34], True, 1, 0, 10),
            is_and(words[35], 2, 1),
            is_halfword_access(words[36], False, 2, 0, 10),
            is_halfword_access(words[37], True, 0, 0, 10),
        )
    )


def semantic_variant(data: bytes, offset: int, variant: str) -> bool:
    count = 46 if variant == "rtc-full-reset" else 44
    if offset < 0 or offset % 2 or offset + count * 2 > len(data):
        return False
    words = struct.unpack_from(f"<{count}H", data, offset)
    if not all(
        (
            words[0] == THUMB_PUSH_R4_LR,
            is_ldr_literal(words[1], 1),
            is_mov_immediate(words[2], 0, 0),
            is_halfword_access(words[3], False, 0, 1, 0),
            is_bl_pair(words[4], words[5]),
            is_bl_pair(words[6], words[7]),
            dma_sequence(words),
        )
    ):
        return False
    expected_literals = ((1, REG_IME), (8, DMA1_BASE), (10, DMA_CLEAR_ENABLE), (15, DMA_CLEAR_ALL), (30, DMA3_BASE))
    if any(literal_value(data, offset, index, words[index]) != value for index, value in expected_literals):
        return False
    if variant == "rtc-full-reset":
        return all(
            (
                is_bl_pair(words[38], words[39]),
                is_mov_immediate(words[40], 0, 0xFF),
                is_bl_pair(words[41], words[42]),
                words[43:] == (THUMB_POP_R4, THUMB_POP_R0, THUMB_BX_R0),
            )
        )
    return all(
        (
            is_mov_immediate(words[38], 0, 0xDF),
            is_bl_pair(words[39], words[40]),
            words[41:] == (THUMB_POP_R4, THUMB_POP_R0, THUMB_BX_R0),
        )
    )


def unique_candidate(data: bytes) -> dict[str, int | str | bool]:
    candidates: list[dict[str, int | str | bool]] = []
    marker = struct.pack("<H", THUMB_PUSH_R4_LR)
    offset = 0
    while True:
        offset = data.find(marker, offset)
        if offset < 0:
            break
        if offset % 2:
            offset += 1
            continue
        for variant, length, reset_mask, rtc in (
            ("rtc-full-reset", 92, 0xFF, True),
            ("no-rtc-preserve-sio", 88, 0xDF, False),
        ):
            if semantic_variant(data, offset, variant):
                candidates.append(
                    {"offset": offset, "length": length, "variant": variant, "reset_mask": reset_mask, "rtc_protected": rtc}
                )
        offset += 2
    if len(candidates) != 1:
        raise ValueError(f"expected one DoSoftReset candidate, found {len(candidates)}")
    return candidates[0]


def refresh_legacy_reference(root: Path, map_path: Path, manifest_path: Path, reference_commit: str) -> None:
    mapping = json.loads((root / map_path).read_text(encoding="utf-8"))
    mapping["naming_basis"]["commit"] = reference_commit
    write_json(root / map_path, mapping)
    manifest = json.loads((root / manifest_path).read_text(encoding="utf-8"))
    for output in manifest["outputs"]:
        if output["path"] == map_path.as_posix():
            output["sha256"] = file_hash(root / map_path)
            write_json(root / manifest_path, manifest)
            return
    raise ValueError("legacy manifest does not own the origin map")


def build(
    root: Path,
    rom_dir: Path,
    catalog_path: Path,
    legacy_origin_map: Path,
    legacy_manifest: Path,
    game: str,
    reference_repository: str,
    reference_commit: str,
) -> dict[str, object]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/do_soft_reset.c")
    source = (root / source_path).read_text(encoding="utf-8")
    if "DoSoftReset" not in source or "DmaStop" not in source:
        raise ValueError("existing DoSoftReset reconstruction is missing")
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
        cfg = thumb_cfg.omit_raw_halfwords(thumb_cfg.trace_thumb_function(data, offset, max_span=length))
        cfg.update({"source_size": len(data), "source_sha256": sha256})
        expected_end = 0x08000000 + offset + length
        expected_calls = 4 if candidate["rtc_protected"] else 3
        if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or len(cfg["calls"]) != expected_calls:
            raise ValueError(f"CFG boundary mismatch: {release_id}")
        cfg_path = Path(f"analysis/{release_id}-do-soft-reset-cfg.json")
        write_json(root / cfg_path, cfg)
        call_names = ["m4aSoundVSyncOff", "ScanlineEffect_Stop"]
        if candidate["rtc_protected"]:
            call_names.append("SiiRtcProtect")
        call_names.append("SoftReset")
        calls = [
            {"name": name, "source": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"}
            for name, call in zip(call_names, cfg["calls"])
        ]
        code = data[offset:offset + length]
        mapping = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "source": source_path.as_posix(),
            "source_sha256": source_sha256,
            "function": {
                "name": "DoSoftReset",
                "address": f"0x{0x08000000 + offset:08X}",
                "range_end_exclusive": f"0x{expected_end:08X}",
                "variant": candidate["variant"],
                "rom_code_range": {
                    "start_offset": offset,
                    "end_offset_exclusive": offset + length,
                    "length": length,
                    "sha256": digest(code),
                    "raw_bytes_published": False,
                },
                "cfg": cfg_path.as_posix(),
            },
            "calls": calls,
            "hardware_writes": {
                "REG_IME": f"0x{REG_IME:08X}",
                "dma_control_high": ["0x040000C6", "0x040000D2", "0x040000DE"],
            },
            "behavior": {
                "interrupt_master_enable": 0,
                "dma_channels_stopped": [1, 2, 3],
                "rtc_protected": candidate["rtc_protected"],
                "soft_reset_mask": f"0x{int(candidate['reset_mask']):02X}",
            },
            "origin_reference": index == 0,
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "src/main.c",
                "match_kind": "Thumb call order, hardware addresses, DMA masks, and reset constant",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-do-soft-reset-map.json")
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
                "variant": candidate["variant"],
                "soft_reset_mask": mapping["behavior"]["soft_reset_mask"],
                "call_targets": {call["name"]: call["target"] for call in calls},
                "evidence": {"map": map_path.as_posix(), "cfg": cfg_path.as_posix()},
            }
        )

    refresh_legacy_reference(root, legacy_origin_map, legacy_manifest, reference_commit)
    outputs.extend((legacy_origin_map, legacy_manifest))
    summary = {
        "schema_version": 1,
        "game": game,
        "function": "DoSoftReset",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/do-soft-reset-catalog-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)

    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    variants = ", ".join(sorted({str(item["variant"]) for item in records}))
    research_path = Path("research/do-soft-reset-global-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} DoSoftReset global reconstruction\n\n"
        f"The existing Japanese reconstruction remains the origin reference. All {len(records)} "
        f"cataloged releases ({languages}) disable IME, stop sound VSync and the scanline "
        "effect, disable DMA channels 1 through 3, and invoke SoftReset. Observed variants: "
        f"{variants}.\n\n"
        "RTC-family builds call `SiiRtcProtect` and reset with mask `0xFF`; FireRed/LeafGreen "
        "builds omit RTC protection and preserve SIO registers with mask `0xDF`. Per-release "
        "maps retain ranges, hashes, ordered call targets, hardware writes, and raw-free CFGs. "
        "No ROM instructions or binaries are published.\n\n"
        f"Naming and behavior are corroborated by `{reference_repository}` at "
        f"`{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8",
        newline="\n",
    )
    outputs.append(research_path)
    test_path = Path("tests/test_do_soft_reset_catalog.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "game": game,
        "function": "DoSoftReset",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/do_soft_reset_catalog.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/do-soft-reset-catalog-reconstruction.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("analysis/global-release-catalog.json"))
    parser.add_argument("--legacy-origin-map", type=Path, required=True)
    parser.add_argument("--legacy-manifest", type=Path, default=Path("manifests/do-soft-reset-reconstruction.json"))
    parser.add_argument("--game", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(
            args.root,
            args.rom_dir,
            args.catalog,
            args.legacy_origin_map,
            args.legacy_manifest,
            args.game,
            args.reference_repository,
            args.reference_commit,
        )
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
