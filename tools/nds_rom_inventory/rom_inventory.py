#!/usr/bin/env python3
"""Inventory Nintendo DS ROM identity without modifying or extracting the ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


HEADER_SIZE = 0x200
HEADER_CRC_END = 0x15E
CHUNK_SIZE = 1024 * 1024


def crc16_nintendo(data: bytes) -> int:
    """Return the CRC-16 used by Nintendo DS headers (init FFFF, poly A001)."""
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def decode_ascii(raw: bytes) -> str:
    return raw.rstrip(b"\0 ").decode("ascii", errors="replace")


@dataclass(frozen=True)
class RomIdentity:
    file: str
    size_bytes: int
    sha256: str
    sha1: str
    md5: str
    title: str
    game_code: str
    maker_code: str
    unit_code: int
    device_capacity_exponent: int
    nominal_capacity_bytes: int
    rom_version: int
    header_crc16_stored: str
    header_crc16_calculated: str
    header_crc16_valid: bool


def inspect_rom(path: Path) -> RomIdentity:
    size = path.stat().st_size
    digests = (hashlib.sha256(), hashlib.sha1(), hashlib.md5())
    header = bytearray()

    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            if len(header) < HEADER_SIZE:
                needed = HEADER_SIZE - len(header)
                header.extend(chunk[:needed])
            for digest in digests:
                digest.update(chunk)

    if len(header) < HEADER_SIZE:
        raise ValueError(f"{path}: too small for a Nintendo DS header")

    capacity_exponent = header[0x14]
    nominal_capacity = 128 * 1024 << capacity_exponent
    stored_crc = int.from_bytes(header[0x15E:0x160], "little")
    calculated_crc = crc16_nintendo(bytes(header[:HEADER_CRC_END]))

    return RomIdentity(
        file=path.name,
        size_bytes=size,
        sha256=digests[0].hexdigest(),
        sha1=digests[1].hexdigest(),
        md5=digests[2].hexdigest(),
        title=decode_ascii(bytes(header[0x00:0x0C])),
        game_code=decode_ascii(bytes(header[0x0C:0x10])),
        maker_code=decode_ascii(bytes(header[0x10:0x12])),
        unit_code=header[0x12],
        device_capacity_exponent=capacity_exponent,
        nominal_capacity_bytes=nominal_capacity,
        rom_version=header[0x1E],
        header_crc16_stored=f"{stored_crc:04x}",
        header_crc16_calculated=f"{calculated_crc:04x}",
        header_crc16_valid=stored_crc == calculated_crc,
    )


def find_roms(inputs: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for item in inputs:
        if item.is_dir():
            found.update(path for path in item.iterdir() if path.is_file() and path.suffix.lower() == ".nds")
        elif item.is_file():
            found.add(item)
        else:
            raise FileNotFoundError(item)
    return sorted(found, key=lambda path: path.name.casefold())


def observation(identities: Iterable[RomIdentity]) -> dict:
    return {
        "schema_version": 1,
        "generated_by": "tools/rom_inventory.py",
        "roms": [asdict(identity) for identity in identities],
    }


VERIFY_FIELDS = (
    "file",
    "size_bytes",
    "sha256",
    "sha1",
    "md5",
    "title",
    "game_code",
    "maker_code",
    "unit_code",
    "device_capacity_exponent",
    "nominal_capacity_bytes",
    "rom_version",
    "header_crc16_stored",
    "header_crc16_calculated",
    "header_crc16_valid",
)


def verify(observed: dict, manifest: dict) -> list[str]:
    errors: list[str] = []
    expected_by_file = {entry["file"]: entry for entry in manifest.get("roms", [])}
    observed_by_file = {entry["file"]: entry for entry in observed.get("roms", [])}

    for filename in sorted(expected_by_file.keys() - observed_by_file.keys()):
        errors.append(f"missing ROM: {filename}")
    for filename in sorted(observed_by_file.keys() - expected_by_file.keys()):
        errors.append(f"unexpected ROM: {filename}")
    for filename in sorted(expected_by_file.keys() & observed_by_file.keys()):
        expected = expected_by_file[filename]
        actual = observed_by_file[filename]
        for field in VERIFY_FIELDS:
            if field in expected and actual.get(field) != expected[field]:
                errors.append(
                    f"{filename}: {field}: expected {expected[field]!r}, got {actual.get(field)!r}"
                )
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="ROM file(s) or directories containing .nds files")
    parser.add_argument("--output", type=Path, help="write the observation as UTF-8 JSON")
    parser.add_argument("--verify", type=Path, metavar="MANIFEST", help="compare against a reviewed manifest")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        identities = [inspect_rom(path) for path in find_roms(args.inputs)]
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    observed = observation(identities)
    rendered = json.dumps(observed, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    if args.verify:
        try:
            manifest = json.loads(args.verify.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"error: cannot read manifest: {error}", file=sys.stderr)
            return 2
        errors = verify(observed, manifest)
        if errors:
            for error in errors:
                print(f"verification failed: {error}", file=sys.stderr)
            return 1
        print(f"verified {len(identities)} ROM(s) against {args.verify}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
