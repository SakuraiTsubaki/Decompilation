#!/usr/bin/env python3
"""Read-only Nintendo 3DS NCSD/NCCH inventory tool.

Produces deterministic JSON metadata and SHA-256 hashes without extracting,
decrypting, or modifying the input image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import BinaryIO, Any

MEDIA_UNIT = 0x200
HEADER_MIN = 0x200


def read_exact_at(f: BinaryIO, offset: int, size: int) -> bytes:
    f.seek(offset)
    data = f.read(size)
    if len(data) != size:
        raise ValueError(f"short read at 0x{offset:X}: wanted {size}, got {len(data)}")
    return data


def u16le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def u64le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def sha256_range(f: BinaryIO, offset: int, size: int, chunk_size: int = 1024 * 1024) -> str:
    if offset < 0 or size < 0:
        raise ValueError("negative offset/size")
    h = hashlib.sha256()
    f.seek(offset)
    remaining = size
    while remaining:
        chunk = f.read(min(chunk_size, remaining))
        if not chunk:
            raise ValueError(f"short read while hashing range 0x{offset:X}+0x{size:X}")
        h.update(chunk)
        remaining -= len(chunk)
    return h.hexdigest()


def ascii_field(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii", errors="replace").rstrip()


def bounded_range(offset: int, size: int, file_size: int) -> dict[str, Any]:
    end = offset + size
    return {
        "offset": offset,
        "size": size,
        "end": end,
        "within_file": 0 <= offset <= end <= file_size,
    }


def parse_ncch_header(header: bytes, base_offset: int, file_size: int) -> dict[str, Any]:
    if len(header) < HEADER_MIN or header[0x100:0x104] != b"NCCH":
        raise ValueError("not an NCCH header")

    content_size = u32le(header, 0x104) * MEDIA_UNIT

    def region(off_field: int, size_field: int) -> dict[str, Any]:
        rel_off = u32le(header, off_field) * MEDIA_UNIT
        size = u32le(header, size_field) * MEDIA_UNIT
        return {
            "relative_offset": rel_off,
            **bounded_range(base_offset + rel_off, size, file_size),
        }

    return {
        "magic": "NCCH",
        "base_offset": base_offset,
        "content_size": content_size,
        "content_range": bounded_range(base_offset, content_size, file_size),
        "partition_id": f"{u64le(header, 0x108):016x}",
        "maker_code": ascii_field(header[0x110:0x112]),
        "version": u16le(header, 0x112),
        "program_id": f"{u64le(header, 0x118):016x}",
        "product_code": ascii_field(header[0x150:0x160]),
        "extended_header_sha256": header[0x160:0x180].hex(),
        "extended_header_size": u32le(header, 0x180),
        "flags": header[0x188:0x190].hex(),
        "plain_region": region(0x190, 0x194),
        "logo_region": region(0x198, 0x19C),
        "exefs": {
            **region(0x1A0, 0x1A4),
            "hash_region_size": u32le(header, 0x1A8) * MEDIA_UNIT,
            "superblock_sha256": header[0x1C0:0x1E0].hex(),
        },
        "romfs": {
            **region(0x1B0, 0x1B4),
            "hash_region_size": u32le(header, 0x1B8) * MEDIA_UNIT,
            "superblock_sha256": header[0x1E0:0x200].hex(),
        },
    }


def parse_ncsd(f: BinaryIO, header: bytes, file_size: int, deep_hash: bool) -> dict[str, Any]:
    if header[0x100:0x104] != b"NCSD":
        raise ValueError("not an NCSD header")

    image_size = u32le(header, 0x104) * MEDIA_UNIT
    partitions = []

    for index in range(8):
        entry_off = 0x120 + index * 8
        rel_off = u32le(header, entry_off) * MEDIA_UNIT
        size = u32le(header, entry_off + 4) * MEDIA_UNIT
        if size == 0:
            continue

        info: dict[str, Any] = {
            "index": index,
            "fs_type": header[0x110 + index],
            "crypto_type": header[0x118 + index],
            "partition_id_table": f"{u64le(header, 0x190 + index * 8):016x}",
            **bounded_range(rel_off, size, file_size),
        }

        if info["within_file"] and size >= HEADER_MIN:
            part_header = read_exact_at(f, rel_off, HEADER_MIN)
            magic = part_header[0x100:0x104]
            info["magic"] = magic.decode("ascii", errors="replace")
            if magic == b"NCCH":
                info["ncch"] = parse_ncch_header(part_header, rel_off, file_size)
            if deep_hash:
                info["sha256"] = sha256_range(f, rel_off, size)

        partitions.append(info)

    return {
        "magic": "NCSD",
        "declared_image_size": image_size,
        "declared_image_within_file": image_size <= file_size,
        "media_id": f"{u64le(header, 0x108):016x}",
        "title_version": u16le(header, 0x310) if len(header) >= 0x314 else None,
        "card_revision": u16le(header, 0x312) if len(header) >= 0x314 else None,
        "partitions": partitions,
    }


def inspect(path: Path, deep_hash: bool = False) -> dict[str, Any]:
    file_size = path.stat().st_size
    if file_size < HEADER_MIN:
        raise ValueError(f"file too small for NCSD/NCCH header: {file_size} bytes")

    with path.open("rb") as f:
        whole_hash = sha256_range(f, 0, file_size)
        header_size = min(max(0x400, HEADER_MIN), file_size)
        header = read_exact_at(f, 0, header_size)
        magic = header[0x100:0x104]

        result: dict[str, Any] = {
            "schema": "ctr-rom-inventory/v1",
            "input": {
                "filename": path.name,
                "size": file_size,
                "sha256": whole_hash,
            },
        }

        if magic == b"NCSD":
            if file_size >= 0x314 and len(header) < 0x314:
                header = read_exact_at(f, 0, 0x314)
            result["container"] = parse_ncsd(f, header, file_size, deep_hash)
        elif magic == b"NCCH":
            result["container"] = parse_ncch_header(header[:HEADER_MIN], 0, file_size)
            if deep_hash:
                result["container"]["sha256"] = whole_hash
        else:
            result["container"] = {
                "magic": magic.decode("ascii", errors="replace"),
                "recognized": False,
            }

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory a Nintendo 3DS NCSD/NCCH image without modifying it."
    )
    parser.add_argument("input", type=Path, help="Path to .3ds/.cci/.cxi/.ncch-style input")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON to this path")
    parser.add_argument(
        "--deep-hash",
        action="store_true",
        help="Also SHA-256 each declared NCSD partition (slower).",
    )
    args = parser.parse_args()

    data = inspect(args.input, deep_hash=args.deep_hash)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
