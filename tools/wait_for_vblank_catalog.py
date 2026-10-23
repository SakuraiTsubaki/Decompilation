#!/usr/bin/env python3
"""Verify WaitForVBlank across a Generation III release catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thumb_cfg


INTR_CHECK_OFFSET = 0x1C
VBLANK_CLEAR_MASK = 0xFFFE
THUMB_PUSH_LR = 0xB500
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


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def literal_offset(instruction_offset: int, halfword: int) -> int:
    return ((instruction_offset + 4) & ~3) + (halfword & 0xFF) * 4


def is_ldr_literal(value: int, register: int) -> bool:
    return value & 0xF800 == 0x4800 and (value >> 8) & 7 == register


def is_halfword_access(value: int, load: bool, register: int, base: int, byte_offset: int) -> bool:
    opcode = 0x8800 if load else 0x8000
    return (
        value & 0xF800 == opcode
        and value & 7 == register
        and (value >> 3) & 7 == base
        and ((value >> 6) & 0x1F) * 2 == byte_offset
    )


def is_and(value: int, destination: int, source: int) -> bool:
    return value & 0xFFC0 == 0x4000 and value & 7 == destination and (value >> 3) & 7 == source


def is_mov_immediate(value: int, register: int, immediate: int) -> bool:
    return value & 0xF800 == 0x2000 and (value >> 8) & 7 == register and value & 0xFF == immediate


def is_cmp_immediate(value: int, register: int, immediate: int) -> bool:
    return value & 0xF800 == 0x2800 and (value >> 8) & 7 == register and value & 0xFF == immediate


def is_add_immediate3(value: int, destination: int, source: int, immediate: int) -> bool:
    return (
        value & 0xFE00 == 0x1C00
        and value & 7 == destination
        and (value >> 3) & 7 == source
        and (value >> 6) & 7 == immediate
    )


def branch_target(offset: int, value: int) -> int | None:
    if value & 0xF000 != 0xD000 or value & 0x0F00 == 0x0F00:
        return None
    return offset + 4 + (sign_extend(value & 0xFF, 8) << 1)


def is_bl_pair(first: int, second: int) -> bool:
    return first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def semantic_variant(data: bytes, offset: int, variant: str) -> bool:
    count = 11 if variant == "bios-call" else 20
    if offset < 0 or offset % 2 or offset + count * 2 > len(data):
        return False
    words = struct.unpack_from(f"<{count}H", data, offset)
    common = all(
        (
            words[0] == THUMB_PUSH_LR,
            is_ldr_literal(words[1], 1 if variant == "bios-call" else 2),
            is_halfword_access(words[2], True, 2 if variant == "bios-call" else 1, 1 if variant == "bios-call" else 2, INTR_CHECK_OFFSET),
            is_ldr_literal(words[3], 0),
            is_and(words[4], 0, 2 if variant == "bios-call" else 1),
            is_halfword_access(words[5], True, 2 if variant == "bios-call" else 1, 1 if variant == "bios-call" else 2, INTR_CHECK_OFFSET),
            is_halfword_access(words[6], False, 0, 1 if variant == "bios-call" else 2, INTR_CHECK_OFFSET),
        )
    )
    if variant == "bios-call":
        return common and is_bl_pair(words[7], words[8]) and words[9:] == (THUMB_POP_R0, THUMB_BX_R0)
    return common and all(
        (
            is_halfword_access(words[7], True, 1, 2, INTR_CHECK_OFFSET),
            is_mov_immediate(words[8], 0, 1),
            is_and(words[9], 0, 1),
            is_cmp_immediate(words[10], 0, 0),
            branch_target(offset + 22, words[11]) == offset + 36,
            is_mov_immediate(words[12], 3, 1),
            is_halfword_access(words[13], True, 1, 2, INTR_CHECK_OFFSET),
            is_add_immediate3(words[14], 0, 3, 0),
            is_and(words[15], 0, 1),
            is_cmp_immediate(words[16], 0, 0),
            branch_target(offset + 34, words[17]) == offset + 26,
            words[18:] == (THUMB_POP_R0, THUMB_BX_R0),
        )
    )


def unique_candidate(data: bytes) -> dict[str, int | str]:
    candidates: list[dict[str, int | str]] = []
    marker = struct.pack("<H", THUMB_PUSH_LR)
    offset = 0
    while True:
        offset = data.find(marker, offset)
        if offset < 0:
            break
        if offset % 2:
            offset += 1
            continue
        for variant, length in (("bios-call", 22), ("volatile-poll", 40)):
            if not semantic_variant(data, offset, variant):
                continue
            words = struct.unpack_from(f"<{length // 2}H", data, offset)
            g_main_literal = literal_offset(offset + 2, words[1])
            mask_literal = literal_offset(offset + 6, words[3])
            if max(g_main_literal, mask_literal) + 4 > len(data):
                continue
            g_main = struct.unpack_from("<I", data, g_main_literal)[0]
            mask = struct.unpack_from("<I", data, mask_literal)[0]
            if not 0x03000000 <= g_main < 0x03008000 or mask != VBLANK_CLEAR_MASK:
                continue
            candidates.append(
                {
                    "offset": offset,
                    "length": length,
                    "variant": variant,
                    "g_main_address": g_main,
                    "g_main_literal_offset": g_main_literal,
                    "mask_literal_offset": mask_literal,
                }
            )
        offset += 2
    if len(candidates) != 1:
        raise ValueError(f"expected one WaitForVBlank candidate, found {len(candidates)}")
    return candidates[0]


def refresh_legacy_evidence(
    root: Path,
    map_path: Path,
    manifest_path: Path,
    origin: dict[str, object],
    reference_commit: str,
) -> None:
    mapping = json.loads((root / map_path).read_text(encoding="utf-8"))
    function = origin["function"]
    literals = origin["literal_addresses"]
    mapping["function"]["address"] = function["address"]
    mapping["function"]["range_end_exclusive"] = function["range_end_exclusive"]
    mapping["literal_addresses"]["gMain"] = literals["gMain"]
    mapping["literal_addresses"]["clear_mask"] = literals["clear_mask"]
    mapping["naming_basis"]["commit"] = reference_commit
    write_json(root / map_path, mapping)
    manifest = json.loads((root / manifest_path).read_text(encoding="utf-8"))
    found = False
    for output in manifest["outputs"]:
        if output["path"] == map_path.as_posix():
            output["sha256"] = file_hash(root / map_path)
            found = True
    if not found:
        raise ValueError("legacy manifest does not own the origin map")
    write_json(root / manifest_path, manifest)


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
    source_path = Path("src/wait_for_vblank.c")
    source = (root / source_path).read_text(encoding="utf-8")
    if "WaitForVBlank" not in source or "intrCheck" not in source:
        raise ValueError("existing WaitForVBlank reconstruction is missing")
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
        call_count = 1 if candidate["variant"] == "bios-call" else 0
        if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or len(cfg["calls"]) != call_count:
            raise ValueError(f"CFG boundary mismatch: {release_id}")
        cfg_path = Path(f"analysis/{release_id}-wait-for-vblank-cfg.json")
        write_json(root / cfg_path, cfg)
        call = None
        if cfg["calls"]:
            call = {"name": "VBlankIntrWait", "target": f"0x{cfg['calls'][0]['target']:08X}"}
        code = data[offset:offset + length]
        mapping = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "source": source_path.as_posix(),
            "source_sha256": source_sha256,
            "function": {
                "name": "WaitForVBlank",
                "address": f"0x{0x08000000 + offset:08X}",
                "range_end_exclusive": f"0x{expected_end:08X}",
                "rom_code_range": {
                    "start_offset": offset,
                    "end_offset_exclusive": offset + length,
                    "length": length,
                    "sha256": digest(code),
                    "raw_bytes_published": False,
                },
                "cfg": cfg_path.as_posix(),
            },
            "literal_addresses": {
                "gMain": f"0x{int(candidate['g_main_address']):08X}",
                "gMain_pointer": f"0x{0x08000000 + int(candidate['g_main_literal_offset']):08X}",
                "clear_mask": f"0x{0x08000000 + int(candidate['mask_literal_offset']):08X}",
            },
            "state": {"intrCheck_offset": INTR_CHECK_OFFSET, "cleared_mask": 1},
            "wait": {"mode": candidate["variant"], "call": call},
            "origin_reference": index == 0,
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "src/main.c",
                "match_kind": "Thumb data access, control flow, literals, and wait behavior",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-wait-for-vblank-map.json")
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
                "wait_mode": candidate["variant"],
                "g_main_address": mapping["literal_addresses"]["gMain"],
                "call_target": call["target"] if call else None,
                "evidence": {"map": map_path.as_posix(), "cfg": cfg_path.as_posix()},
            }
        )

    origin_map = json.loads((root / records[0]["evidence"]["map"]).read_text(encoding="utf-8"))
    refresh_legacy_evidence(root, legacy_origin_map, legacy_manifest, origin_map, reference_commit)
    outputs.extend((legacy_origin_map, legacy_manifest))

    summary = {
        "schema_version": 1,
        "game": game,
        "function": "WaitForVBlank",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "intr_check_offset": INTR_CHECK_OFFSET,
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/wait-for-vblank-catalog-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)

    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    modes = ", ".join(sorted({str(item["wait_mode"]) for item in records}))
    research_path = Path("research/wait-for-vblank-global-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} WaitForVBlank global reconstruction\n\n"
        f"The existing Japanese reconstruction remains the origin reference. All {len(records)} "
        f"cataloged releases ({languages}) clear bit zero of `gMain.intrCheck` at offset "
        f"`0x{INTR_CHECK_OFFSET:X}` before waiting for VBlank. Observed wait modes: {modes}.\n\n"
        "Per-release evidence records the function range and hash, RAM base, literal locations, "
        "call target where present, and a raw-free CFG. The catalog also recalculates the "
        "legacy origin map's PC-relative literal locations instead of carrying forward a "
        "hand-entered address. No ROM instructions or binaries are published.\n\n"
        f"Naming and behavior are corroborated by `{reference_repository}` at "
        f"`{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8",
        newline="\n",
    )
    outputs.append(research_path)

    test_path = Path("tests/test_wait_for_vblank_catalog.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "game": game,
        "function": "WaitForVBlank",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/wait_for_vblank_catalog.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/wait-for-vblank-catalog-reconstruction.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("analysis/global-release-catalog.json"))
    parser.add_argument("--legacy-origin-map", type=Path, required=True)
    parser.add_argument("--legacy-manifest", type=Path, default=Path("manifests/wait-for-vblank-reconstruction.json"))
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
