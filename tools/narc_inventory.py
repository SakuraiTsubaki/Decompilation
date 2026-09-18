#!/usr/bin/env python3
"""Exhaustive Nintendo DS NARC and member inventory tooling.

This module consumes a ROM plus the JSON emitted by ``nds_rom_analyzer``.  It
does not extract or retain member payloads: only reproducible structure,
validation, hashes, signatures, and comparison metadata are written.
"""

from __future__ import annotations

import argparse
import csv
import difflib
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

from tools.nds_rom_analyzer.analyzer import identify_format


TOOL_VERSION = "1.0.0"
MAX_RECURSION_DEPTH = 16
MAX_DECOMPRESSED_SIZE = 512 * 1024 * 1024
NITRO_MAGICS = {
    b"RGCN": "NCGR graphics",
    b"RLCN": "NCLR palette",
    b"RCSN": "NSCR screen map",
    b"RNAN": "NANR animation",
    b"RECN": "NCER cell",
    b"RTFN": "NFTR font",
    b"BMD0": "NSBMD model",
    b"BTX0": "NSBTX texture",
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
COMPRESSION_TYPES = {
    0x10: "Nintendo LZ10",
    0x11: "Nintendo LZ11",
    0x20: "Nintendo Huffman",
    0x24: "Nintendo Huffman 4-bit",
    0x28: "Nintendo Huffman 8-bit",
    0x30: "Nintendo RLE",
}


class NarcError(ValueError):
    """Raised when a NARC or a supported compressed stream is malformed."""


def u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise NarcError(f"u16 outside data at 0x{offset:x}")
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise NarcError(f"u32 outside data at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decompressed_size(data: bytes) -> tuple[int, int]:
    if len(data) < 4:
        raise NarcError("compressed stream is shorter than its four-byte header")
    size = int.from_bytes(data[1:4], "little")
    cursor = 4
    if size == 0:
        if len(data) < 8:
            raise NarcError("extended compressed-size header is truncated")
        size = u32(data, 4)
        cursor = 8
    if size > MAX_DECOMPRESSED_SIZE:
        raise NarcError(f"declared decompressed size {size} exceeds safety limit")
    return size, cursor


def decompress_lz(data: bytes) -> bytes:
    """Safely decode Nintendo LZ10/LZ11 streams with strict bounds checks."""
    if not data or data[0] not in (0x10, 0x11):
        raise NarcError("stream is not Nintendo LZ10/LZ11")
    kind = data[0]
    expected, cursor = _decompressed_size(data)
    output = bytearray()
    while len(output) < expected:
        if cursor >= len(data):
            raise NarcError("compressed stream ended before the declared output size")
        flags = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= expected:
                break
            if not (flags & (0x80 >> bit)):
                if cursor >= len(data):
                    raise NarcError("literal byte is out of range")
                output.append(data[cursor])
                cursor += 1
                continue
            if cursor + 2 > len(data):
                raise NarcError("back-reference header is truncated")
            first = data[cursor]
            second = data[cursor + 1]
            cursor += 2
            if kind == 0x10:
                length = (first >> 4) + 3
                displacement = ((first & 0x0F) << 8 | second) + 1
            else:
                high = first >> 4
                if high == 0:
                    if cursor >= len(data):
                        raise NarcError("long LZ11 reference is truncated")
                    third = data[cursor]
                    cursor += 1
                    length = ((first & 0x0F) << 4 | second >> 4) + 0x11
                    displacement = ((second & 0x0F) << 8 | third) + 1
                elif high == 1:
                    if cursor + 2 > len(data):
                        raise NarcError("very long LZ11 reference is truncated")
                    third, fourth = data[cursor], data[cursor + 1]
                    cursor += 2
                    length = ((first & 0x0F) << 12 | second << 4 | third >> 4) + 0x111
                    displacement = ((third & 0x0F) << 8 | fourth) + 1
                else:
                    length = high + 1
                    displacement = ((first & 0x0F) << 8 | second) + 1
            if displacement > len(output):
                raise NarcError("back-reference precedes decompressed output")
            for _ in range(length):
                if len(output) >= expected:
                    break
                output.append(output[-displacement])
    return bytes(output)


def compression_metadata(data: bytes) -> dict[str, Any]:
    if not data or data[0] not in COMPRESSION_TYPES:
        return {"compressed": False, "compression": None, "compression_evidence": None}
    result: dict[str, Any] = {
        "compressed": True,
        "compression": COMPRESSION_TYPES[data[0]],
        "compression_evidence": "Probable",
        "decompression_supported": data[0] in (0x10, 0x11),
    }
    try:
        size, _ = _decompressed_size(data)
        result["declared_decompressed_size"] = size
    except NarcError as error:
        result["compression_error"] = str(error)
        return result
    if data[0] in (0x10, 0x11):
        try:
            decoded = decompress_lz(data)
            result.update({
                "decompression_valid": True,
                "compression_evidence": "Confirmed",
                "decompressed_size": len(decoded),
                "decompressed_sha256": sha256(decoded),
            })
        except NarcError as error:
            result.update({"decompression_valid": False, "compression_error": str(error)})
    return result


def validate_nitro_format(data: bytes) -> dict[str, Any] | None:
    """Validate the common Nitro binary header for known leading magics."""
    if len(data) < 4 or data[:4] not in NITRO_MAGICS:
        return None
    result: dict[str, Any] = {
        "format": NITRO_MAGICS[data[:4]],
        "magic": data[:4].decode("ascii"),
        "evidence": "Probable",
        "structure_valid": False,
        "issues": [],
    }
    if len(data) < 16:
        result["issues"].append("common Nitro header is truncated")
        return result
    bom, version = u16(data, 4), u16(data, 6)
    declared_size, header_size, block_count = u32(data, 8), u16(data, 12), u16(data, 14)
    result.update({
        "bom": f"0x{bom:04x}", "version": f"0x{version:04x}",
        "declared_size": declared_size, "header_size": header_size,
        "block_count": block_count,
    })
    if bom not in (0xFEFF, 0xFFFE):
        result["issues"].append("unrecognized byte-order mark")
    if header_size < 16 or header_size > len(data):
        result["issues"].append("header size is out of bounds")
    if declared_size != len(data):
        result["issues"].append("declared size does not equal member size")
    if not result["issues"]:
        result.update({"evidence": "Confirmed", "structure_valid": True})
    return result


def _parse_btnf_names(payload: bytes, member_count: int) -> tuple[dict[int, str], list[str]]:
    """Parse a NARC BTNF using the Nitro FNT directory-table encoding."""
    if not payload or not any(payload):
        return {}, []
    # Canonical anonymous NARC name table: the root's subtable offset is four,
    # first file id is zero, and the final word contains the root directory
    # count.  There is intentionally no filename stream to traverse.
    if payload == b"\x04\x00\x00\x00\x00\x00\x01\x00":
        return {}, []
    issues: list[str] = []
    if len(payload) < 8:
        return {}, ["BTNF payload is too short for a root directory entry"]
    root_subtable = u32(payload, 0)
    directory_count = u16(payload, 6)
    if directory_count == 0:
        directory_count = 1
    if directory_count > 4096 or directory_count * 8 > len(payload):
        return {}, ["BTNF directory count/table is out of bounds"]
    entries = []
    for index in range(directory_count):
        offset = index * 8
        entries.append((u32(payload, offset), u16(payload, offset + 4), u16(payload, offset + 6)))
    if root_subtable < directory_count * 8 or root_subtable >= len(payload):
        return {}, ["BTNF root name subtable offset is out of bounds"]
    names: dict[int, str] = {}
    visiting: set[int] = set()

    def walk(directory_id: int, base: PurePosixPath) -> None:
        table_index = directory_id - 0xF000
        if table_index < 0 or table_index >= len(entries):
            issues.append(f"BTNF directory id 0x{directory_id:04x} is invalid")
            return
        if directory_id in visiting:
            issues.append(f"BTNF directory cycle at 0x{directory_id:04x}")
            return
        visiting.add(directory_id)
        cursor, file_id, _parent = entries[table_index]
        if cursor >= len(payload):
            issues.append(f"BTNF subtable for 0x{directory_id:04x} is out of bounds")
            visiting.remove(directory_id)
            return
        while cursor < len(payload):
            length = payload[cursor]
            cursor += 1
            if length == 0:
                break
            is_directory = bool(length & 0x80)
            name_length = length & 0x7F
            if name_length == 0 or cursor + name_length > len(payload):
                issues.append(f"BTNF name in directory 0x{directory_id:04x} is truncated")
                break
            raw_name = payload[cursor:cursor + name_length]
            cursor += name_length
            name = raw_name.decode("shift_jis", errors="replace")
            path = base / name
            if is_directory:
                if cursor + 2 > len(payload):
                    issues.append("BTNF child directory id is truncated")
                    break
                child_id = u16(payload, cursor)
                cursor += 2
                walk(child_id, path)
            else:
                if file_id >= member_count:
                    issues.append(f"BTNF file id {file_id} exceeds member count")
                elif file_id in names:
                    issues.append(f"BTNF duplicate file id {file_id}")
                else:
                    names[file_id] = path.as_posix()
                file_id += 1
        visiting.remove(directory_id)

    walk(0xF000, PurePosixPath("/"))
    return names, issues


def parse_narc(data: bytes) -> dict[str, Any]:
    """Parse and strictly validate one complete NARC payload."""
    if len(data) < 16 or data[:4] != b"NARC":
        raise NarcError("payload is not a complete NARC header")
    bom, version = u16(data, 4), u16(data, 6)
    declared_size, header_size, block_count = u32(data, 8), u16(data, 12), u16(data, 14)
    if bom not in (0xFEFF, 0xFFFE):
        raise NarcError(f"invalid NARC BOM 0x{bom:04x}")
    if declared_size != len(data):
        raise NarcError(f"declared NARC size {declared_size} does not equal payload size {len(data)}")
    if header_size < 16 or header_size > len(data):
        raise NarcError("NARC header size is out of bounds")
    blocks: list[dict[str, Any]] = []
    cursor = header_size
    for block_index in range(block_count):
        if cursor + 8 > len(data):
            raise NarcError(f"block {block_index} header is out of bounds")
        magic_bytes = data[cursor:cursor + 4]
        try:
            magic = magic_bytes.decode("ascii")
        except UnicodeDecodeError:
            magic = magic_bytes.hex()
        size = u32(data, cursor + 4)
        if size < 8:
            raise NarcError(f"block {block_index} has invalid size {size}")
        if cursor + size > len(data):
            raise NarcError(f"block {block_index} extends beyond NARC")
        blocks.append({"index": block_index, "magic": magic, "offset": cursor, "size": size, "end": cursor + size})
        cursor += size
    if cursor != len(data):
        raise NarcError(f"block sizes end at {cursor}, not declared size {len(data)}")
    if block_count != 3:
        raise NarcError(f"expected 3 NARC blocks, found {block_count}")
    if [item["magic"] for item in blocks] != ["BTAF", "BTNF", "GMIF"]:
        raise NarcError(f"nonstandard NARC block order/magic: {[item['magic'] for item in blocks]}")
    btaf, btnf, gmif = blocks
    if btaf["size"] < 12:
        raise NarcError("BTAF block is shorter than its header")
    member_count = u16(data, btaf["offset"] + 8)
    reserved = u16(data, btaf["offset"] + 10)
    expected_btaf_min = 12 + member_count * 8
    if expected_btaf_min > btaf["size"]:
        raise NarcError("BTAF member table exceeds block size")
    gmif_data_offset = gmif["offset"] + 8
    gmif_data_size = gmif["size"] - 8
    members = []
    last_start = -1
    for index in range(member_count):
        entry = btaf["offset"] + 12 + index * 8
        start, end = u32(data, entry), u32(data, entry + 4)
        if start > end:
            raise NarcError(f"member {index} start exceeds end")
        if end > gmif_data_size:
            raise NarcError(f"member {index} extends beyond GMIF data")
        if start < last_start:
            raise NarcError(f"member {index} offsets are not monotonic")
        last_start = start
        absolute = gmif_data_offset + start
        raw = data[absolute:gmif_data_offset + end]
        members.append({
            "member_index": index,
            "container_relative_offset": absolute,
            "container_relative_end": gmif_data_offset + end,
            "gmif_relative_offset": start,
            "gmif_relative_end": end,
            "size": end - start,
            "sha256": sha256(raw),
            "raw": raw,
        })
    btnf_payload = data[btnf["offset"] + 8:btnf["end"]]
    names, btnf_issues = _parse_btnf_names(btnf_payload, member_count)
    for member in members:
        member["name"] = names.get(member["member_index"])
    return {
        "magic": "NARC", "bom": f"0x{bom:04x}", "version": f"0x{version:04x}",
        "declared_file_size": declared_size, "actual_file_size": len(data),
        "header_size": header_size, "block_count": block_count,
        "blocks": blocks, "btaf_reserved": reserved,
        "member_count": member_count, "named_member_count": len(names),
        "btnf_issues": btnf_issues, "gmif_data_offset": gmif_data_offset,
        "gmif_data_size": gmif_data_size, "members": members,
    }


def _member_format(data: bytes, display_name: str) -> dict[str, Any]:
    basic = identify_format(data, display_name)
    nitro = validate_nitro_format(data)
    result = {
        "extension": basic.get("extension"),
        "probable_format": basic.get("format"),
        "signature_hex": basic.get("signature_hex"),
        "format_evidence": "Probable" if basic.get("format") else None,
        "structure_valid": None,
        "format_issues": [],
    }
    if nitro:
        result.update({
            "probable_format": nitro["format"], "format_evidence": nitro["evidence"],
            "structure_valid": nitro["structure_valid"], "format_issues": nitro["issues"],
            "nitro_header": {key: value for key, value in nitro.items() if key not in {"format", "evidence", "structure_valid", "issues"}},
        })
    result.update(compression_metadata(data))
    return result


def inventory_narc(
    data: bytes,
    *,
    parent_path: str,
    parent_file_id: int,
    parent_rom_offset: int,
    depth: int = 0,
    chain: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Inventory one NARC and recursively inspect nested or LZ-decoded NARCs."""
    if depth > MAX_RECURSION_DEPTH:
        raise NarcError("nested NARC recursion depth exceeds safety limit")
    parsed = parse_narc(data)
    chain = chain or parent_path
    container = {
        "container_chain": chain, "depth": depth, "parent_narc_path": parent_path,
        "parent_file_id": parent_file_id, "rom_offset": parent_rom_offset,
        "size": len(data), "sha256": sha256(data),
        "bom": parsed["bom"], "version": parsed["version"],
        "declared_file_size": parsed["declared_file_size"],
        "header_size": parsed["header_size"], "block_count": parsed["block_count"],
        "blocks": parsed["blocks"], "member_count": parsed["member_count"],
        "named_member_count": parsed["named_member_count"],
        "btnf_issues": parsed["btnf_issues"], "validation": "valid",
    }
    flat_members: list[dict[str, Any]] = []
    nested: list[dict[str, Any]] = []
    for item in parsed["members"]:
        raw = item.pop("raw")
        member_name = item["name"]
        logical_name = member_name or f"member_{item['member_index']:05d}"
        member_chain = f"{chain}!/{logical_name.lstrip('/')}"
        fmt = _member_format(raw, logical_name)
        record = {
            "container_chain": chain, "member_chain": member_chain, "depth": depth,
            "parent_narc_path": parent_path, "parent_file_id": parent_file_id,
            **item, **fmt,
            "nested_container": raw.startswith(b"NARC"),
            "nested_after_decompression": False,
            "decompressed_format": None,
            "decompressed_format_evidence": None,
        }
        decoded: bytes | None = None
        if record["compressed"] and record.get("decompression_valid"):
            decoded = decompress_lz(raw)
            decoded_fmt = _member_format(decoded, logical_name)
            record["decompressed_format"] = decoded_fmt.get("probable_format")
            record["decompressed_format_evidence"] = decoded_fmt.get("format_evidence")
            record["nested_after_decompression"] = decoded.startswith(b"NARC")
        flat_members.append(record)
        nested_payload = raw if raw.startswith(b"NARC") else decoded if decoded and decoded.startswith(b"NARC") else None
        if nested_payload is not None:
            child_container, child_members, child_nested = inventory_narc(
                nested_payload, parent_path=parent_path, parent_file_id=parent_file_id,
                parent_rom_offset=parent_rom_offset + item["container_relative_offset"],
                depth=depth + 1, chain=member_chain,
            )
            nested.append(child_container)
            nested.extend(child_nested)
            flat_members.extend(child_members)
    return container, flat_members, nested


def analyze_rom_narcs(rom_path: Path, structure_path: Path, label: str | None = None) -> dict[str, Any]:
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    rom = rom_path.read_bytes()
    expected_hash = structure["provenance"]["input_sha256"]
    actual_hash = sha256(rom)
    if actual_hash != expected_hash:
        raise NarcError(f"ROM SHA-256 mismatch: expected {expected_hash}, got {actual_hash}")
    candidates = [item for item in structure["files"] if item.get("format") == "NARC archive"]
    containers: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []
    nested: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    for file in candidates:
        raw = rom[file["offset"]:file["end"]]
        try:
            container, child_members, child_nested = inventory_narc(
                raw, parent_path=file["path"], parent_file_id=file["file_id"],
                parent_rom_offset=file["offset"],
            )
            containers.append(container)
            members.extend(child_members)
            nested.extend(child_nested)
        except NarcError as error:
            malformed.append({
                "parent_narc_path": file["path"], "parent_file_id": file["file_id"],
                "rom_offset": file["offset"], "size": file["size"],
                "sha256": file["sha256"], "error": str(error),
            })
    all_containers = containers + nested
    format_counts = Counter(item.get("probable_format") or "unknown" for item in members)
    confirmed_format_counts = Counter(
        item.get("probable_format") or "unknown" for item in members
        if item.get("format_evidence") == "Confirmed"
    )
    summary = {
        "top_level_narc_count": len(candidates),
        "valid_top_level_narc_count": len(containers),
        "malformed_top_level_narc_count": len(malformed),
        "nested_narc_count": len(nested),
        "total_container_count": len(all_containers),
        "total_member_count": len(members),
        "named_member_count": sum(item.get("name") is not None for item in members),
        "compression_marker_count": sum(bool(item.get("compressed")) for item in members),
        "confirmed_compressed_member_count": sum(item.get("compression_evidence") == "Confirmed" for item in members),
        "invalid_lz_marker_count": sum(bool(item.get("decompression_supported")) and item.get("decompression_valid") is not True for item in members),
        "unsupported_compression_marker_count": sum(bool(item.get("compressed")) and not bool(item.get("decompression_supported")) for item in members),
        "unknown_member_count": format_counts.get("unknown", 0),
        "format_counts": dict(sorted(format_counts.items())),
        "confirmed_format_counts": dict(sorted(confirmed_format_counts.items())),
    }
    return {
        "schema_version": 1,
        "tool": {"name": "narc_inventory", "version": TOOL_VERSION},
        "provenance": {
            "input_label": label or structure["provenance"]["input_label"],
            "input_rom_basename": rom_path.name,
            "input_rom_size": len(rom), "input_rom_sha256": actual_hash,
            "structure_inventory": str(structure_path),
            "structure_tool": structure["tool"], "rom_bytes_committed": False,
        },
        "summary": summary, "containers": all_containers,
        "members": members, "malformed": malformed,
    }


def _csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _csv_shards(
    directory: Path,
    prefix: str,
    rows: list[dict[str, Any]],
    fields: list[str],
    rows_per_shard: int = 2000,
) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob(f"{prefix}-*.csv"):
        stale.unlink()
    paths = []
    for start in range(0, len(rows), rows_per_shard):
        path = directory / f"{prefix}-{start // rows_per_shard:04d}.csv"
        _csv(path, rows[start:start + rows_per_shard], fields)
        paths.append(path.as_posix())
    if not paths:
        path = directory / f"{prefix}-0000.csv"
        _csv(path, [], fields)
        paths.append(path.as_posix())
    return paths


def write_inventory(result: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    member_fields = [
        "container_chain", "member_chain", "depth", "parent_narc_path", "parent_file_id",
        "member_index", "name", "container_relative_offset", "container_relative_end",
        "gmif_relative_offset", "gmif_relative_end", "size", "sha256", "signature_hex",
        "extension", "probable_format", "format_evidence", "structure_valid", "compressed",
        "compression", "compression_evidence", "decompression_supported", "declared_decompressed_size",
        "decompression_valid", "decompressed_size", "decompressed_sha256",
        "decompressed_format", "decompressed_format_evidence", "nested_container",
        "nested_after_decompression",
    ]
    member_shards = [
        (Path("members") / Path(path).name).as_posix()
        for path in _csv_shards(output / "members", "narc-members", result["members"], member_fields)
    ]
    inventory_json = {key: value for key, value in result.items() if key != "members"}
    inventory_json["member_records"] = {
        "count": len(result["members"]),
        "complete_csv_shards": member_shards,
        "rows_per_shard": 2000,
        "note": "The ordered CSV shards contain one complete record per member; raw payload bytes are not retained.",
    }
    (output / "narc-inventory.json").write_text(json.dumps(inventory_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _csv(output / "narc-containers.csv", result["containers"], [
        "container_chain", "depth", "parent_narc_path", "parent_file_id", "rom_offset",
        "size", "sha256", "bom", "version", "declared_file_size", "header_size",
        "block_count", "member_count", "named_member_count", "validation",
    ])
    _csv(output / "malformed-narcs.csv", result["malformed"], [
        "parent_narc_path", "parent_file_id", "rom_offset", "size", "sha256", "error",
    ])
    formats = [{"format": key, "count": value} for key, value in result["summary"]["format_counts"].items()]
    _csv(output / "member-format-counts.csv", formats, ["format", "count"])
    s, p = result["summary"], result["provenance"]
    lines = [
        "# NARC and member inventory", "",
        "## Provenance", "",
        f"- Input: `{p['input_label']}`",
        f"- ROM SHA-256: `{p['input_rom_sha256']}`",
        f"- Tool: `narc_inventory {result['tool']['version']}`",
        "- ROM bytes committed: **no**", "",
        "## Confirmed totals", "",
        "| Metric | Count |", "| --- | ---: |",
        f"| Top-level NARC candidates | {s['top_level_narc_count']} |",
        f"| Valid top-level NARCs | {s['valid_top_level_narc_count']} |",
        f"| Malformed top-level NARCs | {s['malformed_top_level_narc_count']} |",
        f"| Nested NARCs | {s['nested_narc_count']} |",
        f"| Total members, including nested containers | {s['total_member_count']} |",
        f"| Named members | {s['named_member_count']} |",
        f"| Compression-marker members (Probable or Confirmed) | {s['compression_marker_count']} |",
        f"| Structurally decoded LZ10/LZ11 members (Confirmed) | {s['confirmed_compressed_member_count']} |",
        f"| Invalid LZ-like leading markers | {s['invalid_lz_marker_count']} |",
        f"| Huffman/RLE markers not decoded in this phase | {s['unsupported_compression_marker_count']} |",
        f"| Unknown members | {s['unknown_member_count']} |", "",
        "## Evidence language", "",
        "Offsets, sizes, hashes, block layouts, and successful structural checks are **Confirmed**. "
        "A leading magic or compression marker without complete structural validation remains **Probable**. "
        "No semantic field names are inferred from payload shape alone.", "",
        "No raw member payload is retained. `narc-inventory.json` and the CSV files preserve the complete "
        "reproducible structure and hash evidence.", "",
    ]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")


def load_inventory(path: Path) -> dict[str, Any]:
    """Load a compact inventory and its complete member CSV sidecar."""
    result = json.loads(path.read_text(encoding="utf-8"))
    if "members" in result:
        return result
    member_files = result.get("member_records", {}).get("complete_csv_shards")
    if not member_files:
        legacy = result.get("member_records", {}).get("complete_csv")
        member_files = [legacy] if legacy else []
    if not member_files:
        raise NarcError(f"inventory {path} has no member records or CSV references")
    integer_fields = {
        "depth", "parent_file_id", "member_index", "container_relative_offset",
        "container_relative_end", "gmif_relative_offset", "gmif_relative_end",
        "size", "declared_decompressed_size", "decompressed_size",
    }
    boolean_fields = {
        "structure_valid", "compressed", "decompression_supported",
        "decompression_valid", "nested_container", "nested_after_decompression",
    }
    rows = []
    for member_file in member_files:
        with (path.parent / member_file).open("r", encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                for key, value in list(row.items()):
                    if value == "":
                        row[key] = None
                    elif key in integer_fields:
                        row[key] = int(value)
                    elif key in boolean_fields:
                        row[key] = value == "True"
                rows.append(row)
    result["members"] = rows
    return result


def compare_inventories(results: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [item["provenance"]["input_label"] for item in results]
    all_formats = sorted({
        format_name
        for item in results
        for format_name in item["summary"]["format_counts"]
    })
    format_counts = []
    for format_name in all_formats:
        row: dict[str, Any] = {"format": format_name}
        for item in results:
            row[item["provenance"]["input_label"]] = item["summary"]["format_counts"].get(format_name, 0)
        row["total"] = sum(row[label] for label in labels)
        format_counts.append(row)
    pairs = []
    containers_csv = []
    members_csv = []
    for left_index, left in enumerate(results):
        for right in results[left_index + 1:]:
            left_label, right_label = left["provenance"]["input_label"], right["provenance"]["input_label"]
            left_containers = {item["container_chain"]: item for item in left["containers"]}
            right_containers = {item["container_chain"]: item for item in right["containers"]}
            paths = sorted(set(left_containers) | set(right_containers))
            pair_container_rows = []
            pair_member_rows = []
            for path in paths:
                a, b = left_containers.get(path), right_containers.get(path)
                if a is None or b is None:
                    status = "right-only" if a is None else "left-only"
                elif a["sha256"] == b["sha256"]:
                    status = "identical"
                else:
                    status = "changed"
                row = {
                    "left": left_label, "right": right_label, "container_chain": path,
                    "status": status, "left_sha256": a and a["sha256"],
                    "right_sha256": b and b["sha256"],
                    "left_member_count": a and a["member_count"],
                    "right_member_count": b and b["member_count"],
                    "member_count_delta": (b["member_count"] - a["member_count"]) if a and b else None,
                }
                pair_container_rows.append(row)
                if a and b:
                    left_members = [m for m in left["members"] if m["container_chain"] == path]
                    right_members = [m for m in right["members"] if m["container_chain"] == path]
                    matcher = difflib.SequenceMatcher(a=[m["sha256"] for m in left_members], b=[m["sha256"] for m in right_members], autojunk=False)
                    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                        width = max(i2 - i1, j2 - j1)
                        for offset in range(width):
                            lm = left_members[i1 + offset] if i1 + offset < i2 else None
                            rm = right_members[j1 + offset] if j1 + offset < j2 else None
                            pair_member_rows.append({
                                "left": left_label, "right": right_label, "container_chain": path,
                                "operation": tag, "left_member_index": lm and lm["member_index"],
                                "right_member_index": rm and rm["member_index"],
                                "left_name": lm and lm["name"], "right_name": rm and rm["name"],
                                "left_sha256": lm and lm["sha256"], "right_sha256": rm and rm["sha256"],
                                "left_size": lm and lm["size"], "right_size": rm and rm["size"],
                                "left_format": lm and lm["probable_format"], "right_format": rm and rm["probable_format"],
                            })
            count_status = Counter(row["status"] for row in pair_container_rows)
            count_ops = Counter(row["operation"] for row in pair_member_rows)
            pairs.append({
                "left": left_label, "right": right_label,
                "container_union": len(pair_container_rows),
                "identical_containers": count_status["identical"],
                "changed_containers": count_status["changed"],
                "left_only_containers": count_status["left-only"],
                "right_only_containers": count_status["right-only"],
                "equal_member_rows": count_ops["equal"], "replaced_member_rows": count_ops["replace"],
                "deleted_member_rows": count_ops["delete"], "inserted_member_rows": count_ops["insert"],
            })
            containers_csv.extend(pair_container_rows)
            members_csv.extend(pair_member_rows)
    return {
        "schema_version": 1, "labels": labels, "format_counts": format_counts,
        "pairwise": pairs, "containers": containers_csv, "members": members_csv,
    }


def write_comparison(result: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    member_fields = list(result["members"][0])
    member_shards = [
        (Path("members") / Path(path).name).as_posix()
        for path in _csv_shards(output / "members", "member-comparison", result["members"], member_fields)
    ]
    comparison_json = {key: value for key, value in result.items() if key not in {"members", "containers"}}
    comparison_json["container_comparison"] = {
        "count": len(result["containers"]),
        "complete_csv": "container-comparison.csv",
        "note": "The CSV contains every path-level container comparison row.",
    }
    comparison_json["member_comparison"] = {
        "count": len(result["members"]),
        "complete_csv_shards": member_shards,
        "rows_per_shard": 2000,
        "note": "The ordered CSV shards contain every member sequence-comparison row.",
    }
    (output / "narc-comparison.json").write_text(json.dumps(comparison_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _csv(output / "pairwise-summary.csv", result["pairwise"], list(result["pairwise"][0]))
    _csv(output / "member-format-counts.csv", result["format_counts"], list(result["format_counts"][0]))
    _csv(output / "container-comparison.csv", result["containers"], list(result["containers"][0]))
    lines = ["# Generation IV NARC/member comparison", "", "All counts are deterministic comparisons of the identified ROM inputs. Region/language and title changes are not conflated into a semantic cause.", "", "| Left | Right | Same containers | Changed | Left-only | Right-only | Equal member rows | Replaced | Deleted | Inserted |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in result["pairwise"]:
        lines.append(f"| {row['left']} | {row['right']} | {row['identical_containers']} | {row['changed_containers']} | {row['left_only_containers']} | {row['right_only_containers']} | {row['equal_member_rows']} | {row['replaced_member_rows']} | {row['deleted_member_rows']} | {row['inserted_member_rows']} |")
    lines.extend(["", "`replace`, `delete`, and `insert` are byte-hash sequence operations, not claims about game-design intent.", ""])
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    analyze = sub.add_parser("analyze")
    analyze.add_argument("rom", type=Path)
    analyze.add_argument("structure", type=Path)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--label")
    compare = sub.add_parser("compare")
    compare.add_argument("inventories", nargs="+", type=Path)
    compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "analyze":
        result = analyze_rom_narcs(args.rom, args.structure, args.label)
        write_inventory(result, args.output)
        print(json.dumps(result["summary"], ensure_ascii=True))
        return 0
    if args.command == "compare":
        results = [load_inventory(path) for path in args.inventories]
        result = compare_inventories(results)
        write_comparison(result, args.output)
        print(json.dumps(result["pairwise"], ensure_ascii=True))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
