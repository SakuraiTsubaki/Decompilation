#!/usr/bin/env python3
"""Read-only Nintendo DS ROM structure inventory and comparison tool."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

for candidate in Path(__file__).resolve().parents:
    if (candidate / "tools").is_dir():
        sys.path.insert(0, str(candidate))
        break

try:
    from tools.rom_inventory import crc16_nintendo
except ImportError:  # Installed shared-repository layout.
    from tools.nds_rom_inventory.rom_inventory import crc16_nintendo


TOOL_VERSION = "1.0.0"
HEADER_MIN_SIZE = 0x200
LANGUAGES = ("japanese", "english", "french", "german", "italian", "spanish", "chinese", "korean")
BANNER_SIZES = {1: 0x840, 2: 0x940, 3: 0xA40, 0x103: 0x23C0}
MAGICS = {
    b"NARC": "NARC archive",
    b"BMG\0": "BMG message",
    b"RGCN": "NCGR graphics",
    b"RLCN": "NCLR palette",
    b"RECN": "NCER cell",
    b"RNAN": "NANR animation",
    b"RTFN": "NFTR font",
    b"BTX0": "NSBTX texture",
    b"BMD0": "NSBMD model",
    b"BCA0": "NSBCA animation",
    b"BTA0": "NSBTA texture animation",
    b"BTP0": "NSBTP texture-pattern animation",
    b"BMA0": "NSBMA material animation",
    b"BVA0": "NSBVA visibility animation",
    b"SDAT": "SDAT sound archive",
    b"SSEQ": "SSEQ sequence",
    b"SSAR": "SSAR sequence archive",
    b"SBNK": "SBNK sound bank",
    b"SWAR": "SWAR wave archive",
    b"SWAV": "SWAV wave",
    b"STRM": "STRM stream",
}
LONG_MAGICS = {b"MESGbmg1": "BMG message"}
CONTAINER_FORMATS = {"NARC archive", "SDAT sound archive", "NSBTX texture", "NSBMD model"}


class AnalysisError(ValueError):
    pass


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def ascii_text(raw: bytes) -> str:
    return raw.rstrip(b"\0 ").decode("ascii", errors="replace")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise AnalysisError(f"{label} outside ROM: offset=0x{offset:x}, size=0x{size:x}, ROM=0x{len(data):x}")
    return data[offset:offset + size]


def region(offset: int, size: int) -> dict[str, int]:
    return {"offset": offset, "end": offset + size, "size": size}


def parse_header(data: bytes) -> dict[str, Any]:
    if len(data) < HEADER_MIN_SIZE:
        raise AnalysisError("ROM is too small for the 512-byte Nintendo DS header")
    h = data[:HEADER_MIN_SIZE]
    fields: dict[str, Any] = {
        "game_title": ascii_text(h[0x00:0x0C]),
        "game_code": ascii_text(h[0x0C:0x10]),
        "maker_code": ascii_text(h[0x10:0x12]),
        "unit_code": h[0x12],
        "encryption_seed_select": h[0x13],
        "device_capacity_exponent": h[0x14],
        "nominal_capacity_bytes": 128 * 1024 << h[0x14],
        "reserved_015_01b_hex": h[0x15:0x1C].hex(),
        "reserved_01c": h[0x1C],
        "reserved_01d": h[0x1D],
        "rom_version": h[0x1E],
        "autostart": h[0x1F],
        "arm9": {"rom_offset": u32(h, 0x20), "entry_address": u32(h, 0x24), "ram_address": u32(h, 0x28), "size": u32(h, 0x2C)},
        "arm7": {"rom_offset": u32(h, 0x30), "entry_address": u32(h, 0x34), "ram_address": u32(h, 0x38), "size": u32(h, 0x3C)},
        "fnt": region(u32(h, 0x40), u32(h, 0x44)),
        "fat": region(u32(h, 0x48), u32(h, 0x4C)),
        "arm9_overlay_table": region(u32(h, 0x50), u32(h, 0x54)),
        "arm7_overlay_table": region(u32(h, 0x58), u32(h, 0x5C)),
        "normal_card_control_register": f"0x{u32(h, 0x60):08x}",
        "secure_card_control_register": f"0x{u32(h, 0x64):08x}",
        "banner_offset": u32(h, 0x68),
        "secure_area_crc16_stored": f"{u16(h, 0x6C):04x}",
        "secure_transfer_timeout": u16(h, 0x6E),
        "arm9_autoload": u32(h, 0x70),
        "arm7_autoload": u32(h, 0x74),
        "secure_disable_hex": h[0x78:0x80].hex(),
        "used_rom_size": u32(h, 0x80),
        "header_size": u32(h, 0x84),
        "reserved_088_0bf_sha256": sha256(h[0x88:0xC0]),
        "nintendo_logo_sha256": sha256(h[0xC0:0x15C]),
        "nintendo_logo_crc16_stored": f"{u16(h, 0x15C):04x}",
        "nintendo_logo_crc16_calculated": f"{crc16_nintendo(h[0xC0:0x15C]):04x}",
        "header_crc16_stored": f"{u16(h, 0x15E):04x}",
        "header_crc16_calculated": f"{crc16_nintendo(h[:0x15E]):04x}",
        "debug_rom_offset": u32(h, 0x160),
        "debug_size": u32(h, 0x164),
        "debug_ram_address": u32(h, 0x168),
        "reserved_16c_1ff_sha256": sha256(h[0x16C:0x200]),
    }
    fields["nintendo_logo_crc16_valid"] = fields["nintendo_logo_crc16_stored"] == fields["nintendo_logo_crc16_calculated"]
    fields["header_crc16_valid"] = fields["header_crc16_stored"] == fields["header_crc16_calculated"]
    for key in ("arm9", "arm7"):
        item = fields[key]
        item["rom_end"] = item["rom_offset"] + item["size"]
        item["ram_end"] = item["ram_address"] + item["size"]
        checked_slice(data, item["rom_offset"], item["size"], key)
        item["sha256"] = sha256(data[item["rom_offset"]:item["rom_end"]])
    for key in ("fnt", "fat", "arm9_overlay_table", "arm7_overlay_table"):
        item = fields[key]
        checked_slice(data, item["offset"], item["size"], key)
        item["sha256"] = sha256(data[item["offset"]:item["end"]])
    return fields


def parse_fat(data: bytes, header: dict[str, Any]) -> list[dict[str, Any]]:
    info = header["fat"]
    if info["size"] % 8:
        raise AnalysisError("FAT size is not divisible by 8")
    raw = checked_slice(data, info["offset"], info["size"], "FAT")
    entries = []
    for file_id in range(len(raw) // 8):
        start, end = struct.unpack_from("<II", raw, file_id * 8)
        if end < start or end > len(data):
            raise AnalysisError(f"invalid FAT entry {file_id}: 0x{start:x}..0x{end:x}")
        entries.append({"file_id": file_id, "offset": start, "end": end, "size": end - start})
    return entries


def parse_fnt(data: bytes, header: dict[str, Any], file_count: int) -> tuple[list[dict[str, Any]], dict[int, str]]:
    info = header["fnt"]
    raw = checked_slice(data, info["offset"], info["size"], "FNT")
    if len(raw) < 8:
        raise AnalysisError("FNT lacks a root directory record")
    root_subtable, root_first_file, directory_count = struct.unpack_from("<IHH", raw, 0)
    if directory_count == 0 or directory_count * 8 > len(raw):
        raise AnalysisError(f"invalid FNT directory count: {directory_count}")
    records = {}
    for index in range(directory_count):
        subtable, first_file, parent = struct.unpack_from("<IHH", raw, index * 8)
        if subtable >= len(raw):
            raise AnalysisError(f"FNT directory {index:#x} subtable outside FNT")
        records[0xF000 + index] = {"directory_id": 0xF000 + index, "subtable_offset": subtable, "first_file_id": first_file, "parent_id_raw": parent}
    if records[0xF000]["subtable_offset"] != root_subtable or records[0xF000]["first_file_id"] != root_first_file:
        raise AnalysisError("inconsistent FNT root record")
    paths: dict[int, str] = {}
    directories: list[dict[str, Any]] = []
    visiting: set[int] = set()

    def walk(directory_id: int, current: PurePosixPath) -> None:
        if directory_id in visiting:
            raise AnalysisError(f"FNT directory cycle at {directory_id:#x}")
        if directory_id not in records:
            raise AnalysisError(f"FNT references missing directory {directory_id:#x}")
        visiting.add(directory_id)
        rec = records[directory_id]
        directories.append({**rec, "path": "/" if directory_id == 0xF000 else current.as_posix()})
        pos = rec["subtable_offset"]
        next_file_id = rec["first_file_id"]
        while True:
            if pos >= len(raw):
                raise AnalysisError(f"unterminated FNT subtable for {directory_id:#x}")
            control = raw[pos]
            pos += 1
            if control == 0:
                break
            name_len = control & 0x7F
            is_directory = bool(control & 0x80)
            if name_len == 0 or pos + name_len > len(raw):
                raise AnalysisError(f"invalid FNT name in {directory_id:#x}")
            name_raw = raw[pos:pos + name_len]
            pos += name_len
            name = name_raw.decode("ascii", errors="replace")
            child_path = current / name
            if is_directory:
                if pos + 2 > len(raw):
                    raise AnalysisError("truncated FNT child directory ID")
                child_id = u16(raw, pos)
                pos += 2
                walk(child_id, child_path)
            else:
                if next_file_id >= file_count:
                    raise AnalysisError(f"FNT file ID {next_file_id} exceeds FAT")
                if next_file_id in paths:
                    raise AnalysisError(f"duplicate FNT file ID {next_file_id}")
                paths[next_file_id] = child_path.as_posix()
                next_file_id += 1
        visiting.remove(directory_id)

    walk(0xF000, PurePosixPath("/"))
    directories.sort(key=lambda item: item["directory_id"])
    return directories, paths


def identify_format(raw: bytes, path: str) -> dict[str, Any]:
    result: dict[str, Any] = {"extension": PurePosixPath(path).suffix.lower() or None, "format": None, "signature_hex": raw[:16].hex()}
    if len(raw) >= 8 and raw[:8] in LONG_MAGICS:
        result["format"] = LONG_MAGICS[raw[:8]]
    elif len(raw) >= 4 and raw[:4] in MAGICS:
        result["format"] = MAGICS[raw[:4]]
        if raw[:4] == b"NARC" and len(raw) >= 0x10:
            result["container"] = {"declared_size": u32(raw, 8), "header_size": u16(raw, 12), "chunk_count": u16(raw, 14)}
    elif raw:
        compression = {0x10: "Nintendo LZ10", 0x11: "Nintendo LZ11", 0x20: "Nintendo Huffman", 0x30: "Nintendo RLE"}.get(raw[0])
        if compression:
            result["format"] = compression
            if len(raw) >= 4:
                result["decompressed_size_field"] = int.from_bytes(raw[1:4], "little")
    return result


def enrich_files(data: bytes, fat: list[dict[str, Any]], paths: dict[int, str]) -> list[dict[str, Any]]:
    files = []
    for item in fat:
        path = paths.get(item["file_id"], f"__unmapped__/file_{item['file_id']:05d}")
        raw = data[item["offset"]:item["end"]]
        files.append({**item, "path": path, "sha256": sha256(raw), **identify_format(raw, path)})
    return files


def parse_overlays(data: bytes, table: dict[str, Any], files: list[dict[str, Any]], cpu: str) -> list[dict[str, Any]]:
    if table["size"] % 32:
        raise AnalysisError(f"{cpu} overlay table size is not divisible by 32")
    raw = checked_slice(data, table["offset"], table["size"], f"{cpu} overlay table")
    by_id = {item["file_id"]: item for item in files}
    overlays = []
    for index in range(len(raw) // 32):
        values = struct.unpack_from("<8I", raw, index * 32)
        overlay_id, ram_address, ram_size, bss_size, init_start, init_end, file_id, packed = values
        file_info = by_id.get(file_id)
        overlays.append({
            "table_index": index,
            "overlay_id": overlay_id,
            "ram_address": ram_address,
            "ram_end": ram_address + ram_size + bss_size,
            "ram_size": ram_size,
            "bss_size": bss_size,
            "static_init_start": init_start,
            "static_init_end": init_end,
            "file_id": file_id,
            "compressed_size_field": packed & 0x00FFFFFF,
            "flags": packed >> 24,
            "compression_flag": bool((packed >> 24) & 1),
            "file": file_info,
        })
    return overlays


def parse_banner(data: bytes, offset: int) -> dict[str, Any] | None:
    if offset == 0:
        return None
    base = checked_slice(data, offset, 0x20, "banner header")
    version = u16(base, 0)
    size = BANNER_SIZES.get(version)
    if size is None:
        raise AnalysisError(f"unsupported banner version 0x{version:04x}")
    raw = checked_slice(data, offset, size, "banner")
    title_count = 6 if version == 1 else 7 if version == 2 else 8
    titles = {}
    for index in range(title_count):
        value = raw[0x240 + index * 0x100:0x340 + index * 0x100].decode("utf-16le", errors="replace").rstrip("\0")
        titles[LANGUAGES[index]] = value
    checks = []
    coverage = ((0x02, 0x840),)
    if version >= 2:
        coverage += ((0x04, 0x940),)
    if version >= 3:
        coverage += ((0x06, 0xA40),)
    for crc_offset, end in coverage:
        stored = u16(raw, crc_offset)
        calculated = crc16_nintendo(raw[0x20:end])
        checks.append({"crc_offset": crc_offset, "covered_start": 0x20, "covered_end": end, "stored": f"{stored:04x}", "calculated": f"{calculated:04x}", "valid": stored == calculated})
    return {
        "offset": offset,
        "end": offset + size,
        "size": size,
        "version": version,
        "sha256": sha256(raw),
        "icon_bitmap_sha256": sha256(raw[0x20:0x220]),
        "icon_palette_sha256": sha256(raw[0x220:0x240]),
        "titles": titles,
        "crc_checks": checks,
    }


def summarize_range(data: bytes, start: int, end: int, kind: str) -> dict[str, Any]:
    raw = data[start:end]
    counts = Counter(raw)
    common = [{"byte": f"{value:02x}", "count": count} for value, count in counts.most_common(4)]
    return {"kind": kind, "offset": start, "end": end, "size": end - start, "sha256": sha256(raw), "uniform_byte": f"{raw[0]:02x}" if raw and len(counts) == 1 else None, "most_common_bytes": common}


def merge_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted((max(0, s), max(0, e)) for s, e in intervals if e > s):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def analyze_ranges(data: bytes, header: dict[str, Any], files: list[dict[str, Any]], banner: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    named = []
    def add(name: str, start: int, size: int) -> None:
        if size:
            named.append({"name": name, "offset": start, "end": start + size, "size": size, "alignment_4": start % 4 == 0, "alignment_0x200": start % 0x200 == 0})
    add("header_region", 0, min(header["header_size"] or HEADER_MIN_SIZE, len(data)))
    add("arm9", header["arm9"]["rom_offset"], header["arm9"]["size"])
    add("arm7", header["arm7"]["rom_offset"], header["arm7"]["size"])
    for key in ("fnt", "fat", "arm9_overlay_table", "arm7_overlay_table"):
        add(key, header[key]["offset"], header[key]["size"])
    if banner:
        add("banner", banner["offset"], banner["size"])
    for item in files:
        add(f"nitrofs:{item['file_id']}:{item['path']}", item["offset"], item["size"])
    limit = min(header["used_rom_size"] or len(data), len(data))
    merged = merge_intervals((max(0, x["offset"]), min(limit, x["end"])) for x in named)
    gaps = []
    cursor = 0
    for start, end in merged:
        if cursor < start:
            gaps.append(summarize_range(data, cursor, start, "unreferenced_within_used_rom"))
        cursor = max(cursor, end)
    if cursor < limit:
        gaps.append(summarize_range(data, cursor, limit, "unreferenced_within_used_rom"))
    if limit < len(data):
        gaps.append(summarize_range(data, limit, len(data), "trailing_after_used_rom"))
    return named, gaps


def analyze_rom(path: Path, label: str | None = None) -> dict[str, Any]:
    data = path.read_bytes()
    header = parse_header(data)
    fat = parse_fat(data, header)
    directories, paths = parse_fnt(data, header, len(fat))
    files = enrich_files(data, fat, paths)
    overlays = {
        "arm9": parse_overlays(data, header["arm9_overlay_table"], files, "ARM9"),
        "arm7": parse_overlays(data, header["arm7_overlay_table"], files, "ARM7"),
    }
    banner = parse_banner(data, header["banner_offset"])
    named_ranges, gaps = analyze_ranges(data, header, files, banner)
    secure = None
    if len(data) >= 0x8000:
        secure_raw = data[0x4000:0x8000]
        calculated = crc16_nintendo(secure_raw)
        secure = {
            "offset": 0x4000,
            "end": 0x8000,
            "size": 0x4000,
            "raw_encrypted_sha256": sha256(secure_raw),
            "header_crc16_stored": header["secure_area_crc16_stored"],
            "raw_encrypted_crc16_calculated": f"{calculated:04x}",
            "raw_encrypted_crc16_matches_header": header["secure_area_crc16_stored"] == f"{calculated:04x}",
            "decrypted_crc_validation": "not_performed",
            "overlaps_arm9": header["arm9"]["rom_offset"] < 0x8000 and header["arm9"]["rom_end"] > 0x4000,
        }
    containers = [{"file_id": f["file_id"], "path": f["path"], "format": f["format"], "size": f["size"]} for f in files if f["format"] in CONTAINER_FORMATS]
    mapped_ids = set(paths)
    all_ids = {item["file_id"] for item in files}
    overlay_ids = {item["file_id"] for group in overlays.values() for item in group}
    ordered_nonempty = sorted((item["offset"], item["end"], item["file_id"]) for item in files if item["size"])
    fat_overlaps = [
        {"left_file_id": left[2], "right_file_id": right[2], "left_end": left[1], "right_start": right[0]}
        for left, right in zip(ordered_nonempty, ordered_nonempty[1:]) if right[0] < left[1]
    ]
    checks = {
        "actual_size_equals_nominal_capacity": len(data) == header["nominal_capacity_bytes"],
        "used_rom_size_within_actual_file": 0 < header["used_rom_size"] <= len(data),
        "header_crc16_valid": header["header_crc16_valid"],
        "nintendo_logo_crc16_valid": header["nintendo_logo_crc16_valid"],
        "all_banner_crc_checks_valid": bool(banner) and all(item["valid"] for item in banner["crc_checks"]),
        "all_fat_entries_have_fnt_or_overlay_reference": (all_ids - mapped_ids) <= overlay_ids,
        "all_overlay_file_ids_exist_in_fat": overlay_ids <= all_ids,
        "fat_file_ranges_non_overlapping": not fat_overlaps,
    }
    return {
        "schema_version": 1,
        "tool": {"name": "nds_rom_analyzer", "version": TOOL_VERSION},
        "provenance": {"input_label": label or path.name, "input_basename": path.name, "input_size": len(data), "input_sha256": sha256(data), "rom_bytes_committed": False},
        "header": header,
        "secure_area": secure,
        "banner": banner,
        "directories": directories,
        "files": files,
        "overlays": overlays,
        "referenced_ranges": named_ranges,
        "unreferenced_ranges": gaps,
        "containers": containers,
        "validation": {"checks": checks, "unmapped_fat_file_ids": sorted(all_ids - mapped_ids), "overlay_file_ids": sorted(overlay_ids), "fat_range_overlaps": fat_overlaps, "all_checks_passed": all(checks.values())},
        "summary": {"directory_count": len(directories), "file_count": len(files), "mapped_file_count": len(paths), "arm9_overlay_count": len(overlays["arm9"]), "arm7_overlay_count": len(overlays["arm7"]), "recognized_format_count": sum(1 for f in files if f["format"]), "extensionless_file_count": sum(1 for f in files if not f["extension"]), "extensionless_recognized_count": sum(1 for f in files if not f["extension"] and f["format"]), "narc_count": sum(1 for f in files if f["format"] == "NARC archive"), "unreferenced_range_count": len(gaps)},
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "structure.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(output / "nitrofs-files.csv", result["files"], ["file_id", "path", "offset", "end", "size", "sha256", "extension", "format", "signature_hex"])
    write_csv(output / "directories.csv", result["directories"], ["directory_id", "path", "parent_id_raw", "subtable_offset", "first_file_id"])
    for cpu in ("arm9", "arm7"):
        rows = []
        for item in result["overlays"][cpu]:
            row = {k: v for k, v in item.items() if k != "file"}
            if item["file"]:
                row.update({"file_path": item["file"]["path"], "file_offset": item["file"]["offset"], "file_size": item["file"]["size"], "file_sha256": item["file"]["sha256"]})
            rows.append(row)
        write_csv(output / f"overlays-{cpu}.csv", rows, ["table_index", "overlay_id", "ram_address", "ram_end", "ram_size", "bss_size", "static_init_start", "static_init_end", "file_id", "file_path", "file_offset", "file_size", "file_sha256", "compressed_size_field", "flags", "compression_flag"])
    write_csv(output / "unreferenced-ranges.csv", result["unreferenced_ranges"], ["kind", "offset", "end", "size", "sha256", "uniform_byte"])
    h, s = result["header"], result["summary"]
    md = [
        f"# ROM structure inventory: {result['provenance']['input_label']}", "",
        "## Provenance", "",
        f"- Tool: `nds_rom_analyzer {result['tool']['version']}`",
        f"- Input basename: `{result['provenance']['input_basename']}`",
        f"- Input SHA-256: `{result['provenance']['input_sha256']}`",
        "- ROM bytes committed: no", "- Confidence: **Confirmed** for directly parsed offsets, fields, hashes, and CRC results.", "",
        "## Core structure", "",
        "| Field | Value |", "| --- | --- |",
        f"| Game code | `{h['game_code']}` |", f"| ROM/header size | `{result['provenance']['input_size']}` / `{h['header_size']}` bytes |",
        f"| ARM9 ROM / RAM / entry / size | `0x{h['arm9']['rom_offset']:x}` / `0x{h['arm9']['ram_address']:08x}` / `0x{h['arm9']['entry_address']:08x}` / `{h['arm9']['size']}` |",
        f"| ARM7 ROM / RAM / entry / size | `0x{h['arm7']['rom_offset']:x}` / `0x{h['arm7']['ram_address']:08x}` / `0x{h['arm7']['entry_address']:08x}` / `{h['arm7']['size']}` |",
        f"| FNT / FAT files / directories | `0x{h['fnt']['offset']:x}` / `{s['file_count']}` / `{s['directory_count']}` |",
        f"| ARM9 / ARM7 overlays | `{s['arm9_overlay_count']}` / `{s['arm7_overlay_count']}` |",
        f"| NARC archives | `{s['narc_count']}` |", f"| Recognized signatures | `{s['recognized_format_count']}` |",
        f"| Header/logo CRC valid | `{h['header_crc16_valid']}` / `{h['nintendo_logo_crc16_valid']}` |",
        f"| Structural validation checks | `{result['validation']['all_checks_passed']}` |",
        f"| Secure-area raw encrypted bytes / decrypted CRC validation | `{result['secure_area']['raw_encrypted_sha256'] if result['secure_area'] else None}` / `not performed` |", "",
        "## Outputs", "",
        "- `structure.json`: complete machine-readable inventory.", "- `nitrofs-files.csv`: every FAT file with path, offsets, size, SHA-256, extension, and detected signature.", "- `directories.csv`: complete FNT directory table.", "- `overlays-arm9.csv` and `overlays-arm7.csv`: complete overlay tables and RAM placement.", "- `unreferenced-ranges.csv`: physical gaps and trailing padding. `unreferenced` does not prove unused.", "",
        "## Reproduction", "", "```console", f"python tools/nds_rom_analyzer/analyzer.py /path/to/input.nds --output analysis/generated/rom-structure --label \"{result['provenance']['input_label']}\"", "```", "",
        "## Unknowns", "", "The secure-area bytes and header checksum field are recorded, but decrypted secure-area CRC validation is not performed; a mismatch against CRC of encrypted raw bytes is not corruption evidence. Magic detection identifies only known leading signatures and compression markers. Unknown or extensionless files remain unclassified rather than receiving inferred names. Semantic analysis of NARC members, text, maps, scripts, Pokémon, moves, and items is deferred.", "",
    ]
    (output / "README.md").write_text("\n".join(md), encoding="utf-8")


def compare_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [r["provenance"]["input_label"] for r in results]
    by_label = {label: {f["path"]: f for f in result["files"]} for label, result in zip(labels, results)}
    all_paths = sorted(set().union(*(files.keys() for files in by_label.values())))
    rows = []
    counts = {"all_present_identical": 0, "all_present_changed": 0, "subset_present": 0}
    for path in all_paths:
        present = {label: by_label[label][path] for label in labels if path in by_label[label]}
        hashes = {item["sha256"] for item in present.values()}
        if len(present) == len(labels):
            status = "all_present_identical" if len(hashes) == 1 else "all_present_changed"
        else:
            status = "subset_present"
        counts[status] += 1
        rows.append({"path": path, "status": status, "present_in": sorted(present), "missing_from": [label for label in labels if label not in present], "sha256_by_rom": {label: item["sha256"] for label, item in present.items()}, "size_by_rom": {label: item["size"] for label, item in present.items()}})
    pairwise = []
    for left_index, left in enumerate(labels):
        for right in labels[left_index + 1:]:
            left_files, right_files = by_label[left], by_label[right]
            shared_paths = set(left_files) & set(right_files)
            left_hashes = {item["sha256"] for item in left_files.values()}
            right_hashes = {item["sha256"] for item in right_files.values()}
            identical = sum(left_files[path]["sha256"] == right_files[path]["sha256"] for path in shared_paths)
            pairwise.append({
                "left": left,
                "right": right,
                "shared_paths": len(shared_paths),
                "identical_at_same_path": identical,
                "changed_at_same_path": len(shared_paths) - identical,
                "left_unique_paths": len(set(left_files) - set(right_files)),
                "right_unique_paths": len(set(right_files) - set(left_files)),
                "shared_content_hashes_any_path": len(left_hashes & right_hashes),
            })
    return {"schema_version": 1, "tool": {"name": "nds_rom_analyzer", "version": TOOL_VERSION}, "labels": labels, "summary": counts, "structures": {label: result["summary"] | {"rom_size": result["provenance"]["input_size"], "used_rom_size": result["header"]["used_rom_size"], "game_code": result["header"]["game_code"], "arm9_size": result["header"]["arm9"]["size"], "arm7_size": result["header"]["arm7"]["size"], "fnt_size": result["header"]["fnt"]["size"], "fat_size": result["header"]["fat"]["size"], "banner_version": result["banner"]["version"] if result["banner"] else None} for label, result in zip(labels, results)}, "pairwise": pairwise, "files": rows}


def write_comparison_outputs(comparison: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "structure-comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    file_rows = []
    for item in comparison["files"]:
        file_rows.append({
            "path": item["path"],
            "status": item["status"],
            "present_in": json.dumps(item["present_in"], ensure_ascii=False),
            "missing_from": json.dumps(item["missing_from"], ensure_ascii=False),
            "sha256_by_rom": json.dumps(item["sha256_by_rom"], ensure_ascii=False, sort_keys=True),
            "size_by_rom": json.dumps(item["size_by_rom"], ensure_ascii=False, sort_keys=True),
        })
    write_csv(output / "file-comparison.csv", file_rows, ["path", "status", "present_in", "missing_from", "sha256_by_rom", "size_by_rom"])
    write_csv(output / "pairwise-comparison.csv", comparison["pairwise"], ["left", "right", "shared_paths", "identical_at_same_path", "changed_at_same_path", "left_unique_paths", "right_unique_paths", "shared_content_hashes_any_path"])
    lines = [
        "# Generation IV ROM structure comparison", "",
        "## Scope", "", "Path-based and content-hash comparisons of the five selected ROM inventories. ROM bytes are not included. Counts are **Confirmed** outputs of the same analyzer version and input hashes recorded in each inventory.", "",
        "## Structure summary", "", "| ROM | Code | ROM / used bytes | Files | Directories | ARM9 / ARM7 overlays | NARC | Banner |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in comparison["labels"]:
        item = comparison["structures"][label]
        lines.append(f"| {label} | `{item['game_code']}` | `{item['rom_size']}` / `{item['used_rom_size']}` | `{item['file_count']}` | `{item['directory_count']}` | `{item['arm9_overlay_count']}` / `{item['arm7_overlay_count']}` | `{item['narc_count']}` | `{item['banner_version']}` |")
    lines += ["", "## Pairwise file comparison", "", "| Left | Right | Shared paths | Identical | Changed | Left-only | Right-only | Shared hashes at any path |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for item in comparison["pairwise"]:
        lines.append(f"| {item['left']} | {item['right']} | {item['shared_paths']} | {item['identical_at_same_path']} | {item['changed_at_same_path']} | {item['left_unique_paths']} | {item['right_unique_paths']} | {item['shared_content_hashes_any_path']} |")
    lines += ["", "## Interpretation limits", "", "An identical SHA-256 proves byte identity for the compared file payloads. A changed hash proves a byte difference but not its semantic cause. A path missing from one FNT can still have related data elsewhere or in an overlay. `file-comparison.csv` and `structure-comparison.json` retain the complete path-level evidence.", ""]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments and arguments[0] == "compare":
            parser = argparse.ArgumentParser(description="Compare structure inventories")
            parser.add_argument("inventories", nargs="+", type=Path)
            parser.add_argument("--output", required=True, type=Path)
            args = parser.parse_args(arguments[1:])
            results = [json.loads(path.read_text(encoding="utf-8")) for path in args.inventories]
            comparison = compare_results(results)
            write_comparison_outputs(comparison, args.output)
            return 0
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("rom", type=Path)
        parser.add_argument("--output", required=True, type=Path)
        parser.add_argument("--label")
        args = parser.parse_args(arguments)
        write_outputs(analyze_rom(args.rom, args.label), args.output)
        return 0
    except (OSError, AnalysisError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
