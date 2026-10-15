#!/usr/bin/env python3
"""Verify Gen III Random/SeedRng Thumb shapes without publishing ROM bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


ROM_BASE = 0x08000000
MULTIPLIER = 1103515245
INCREMENT = 24691

RANDOM_PATTERNS = {
    "standard": (0x4A04, 0x6811, 0x4804, 0x4348, 0x4904, 0x1840, 0x6010, 0x0C00, 0x4770),
    "emerald": (0x4A06, 0x6811, 0x4806, 0x4348, 0x4906, 0x1840, 0x6010,
                0x4A06, 0x6811, 0x3101, 0x6011, 0x0C00, 0x4770),
}
SEED_PATTERNS = {
    "standard": (0x0400, 0x0C00, 0x4901, 0x6008, 0x4770),
    "emerald": (0x0400, 0x0C00, 0x4902, 0x6008, 0x4902, 0x2000, 0x7008, 0x4770),
}


def words(data: bytes, offset: int, count: int) -> tuple[int, ...]:
    return struct.unpack_from(f"<{count}H", data, offset)


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def code_record(data: bytes, offset: int, length: int) -> dict[str, object]:
    return {
        "address": f"0x{ROM_BASE + offset:08X}",
        "range_end_exclusive": f"0x{ROM_BASE + offset + length:08X}",
        "rom_code_range": {
            "start_offset": offset,
            "end_offset_exclusive": offset + length,
            "length": length,
            "sha256": hashlib.sha256(data[offset:offset + length]).hexdigest(),
            "raw_bytes_published": False,
        },
    }


def analyze(data: bytes, random_offset: int, seed_offset: int, variant: str) -> dict[str, object]:
    random_pattern = RANDOM_PATTERNS[variant]
    seed_pattern = SEED_PATTERNS[variant]
    if words(data, random_offset, len(random_pattern)) != random_pattern:
        raise ValueError("Random instruction shape does not match the selected variant")
    if words(data, seed_offset, len(seed_pattern)) != seed_pattern:
        raise ValueError("SeedRng instruction shape does not match the selected variant")

    if variant == "standard":
        rng_address = u32(data, random_offset + 20)
        if u32(data, random_offset + 24) != MULTIPLIER or u32(data, random_offset + 28) != INCREMENT:
            raise ValueError("Random LCG constants do not match the ISO C parameters")
        if u32(data, seed_offset + 12) != rng_address:
            raise ValueError("Random and SeedRng do not address the same state")
        globals_record = {"gRngValue": f"0x{rng_address:08X}"}
    else:
        rng_address = u32(data, random_offset + 28)
        if u32(data, random_offset + 32) != MULTIPLIER or u32(data, random_offset + 36) != INCREMENT:
            raise ValueError("Random LCG constants do not match the ISO C parameters")
        rand_count = u32(data, random_offset + 40)
        unknown = u32(data, seed_offset + 20)
        if u32(data, seed_offset + 16) != rng_address:
            raise ValueError("Random and SeedRng do not address the same state")
        globals_record = {
            "gRngValue": f"0x{rng_address:08X}",
            "sRandCount": f"0x{rand_count:08X}",
            "sUnknown": f"0x{unknown:08X}",
        }

    return {
        "schema_version": 1,
        "variant": variant,
        "algorithm": {
            "state_bits": 32,
            "multiplier": MULTIPLIER,
            "increment": INCREMENT,
            "return_bits": "state[31:16]",
        },
        "globals": globals_record,
        "functions": {
            "Random": code_record(data, random_offset, len(random_pattern) * 2),
            "SeedRng": code_record(data, seed_offset, len(seed_pattern) * 2),
        },
        "raw_rom_bytes_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--random-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--seed-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--variant", choices=tuple(RANDOM_PATTERNS), required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--prefix")
    args = parser.parse_args()
    data = args.rom.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != args.expected_sha256.lower():
        parser.error("ROM SHA-256 mismatch")
    try:
        result = analyze(data, args.random_offset, args.seed_offset, args.variant)
    except (IndexError, struct.error, ValueError) as error:
        parser.error(str(error))
    result["target"] = {"release": args.release, "sha256": digest}
    result["naming_basis"] = {
        "repository": args.reference_repository,
        "commit": args.reference_commit,
        "path": "src/random.c",
        "raw_rom_bytes_published": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.root is not None:
        if not args.prefix:
            parser.error("--prefix is required with --root")
        relative_outputs = [
            Path("src/random.c"),
            Path(f"analysis/{args.prefix}-jp-random-cfg.json"),
            Path(f"analysis/{args.prefix}-jp-seed-rng-cfg.json"),
            args.output.relative_to(args.root),
            Path("research/rng-reconstruction.md"),
            Path("tests/test_rng_reconstruction.py"),
        ]
        missing = [path.as_posix() for path in relative_outputs if not (args.root / path).is_file()]
        if missing:
            parser.error("missing manifest output(s): " + ", ".join(missing))
        manifest = {
            "schema_version": 1,
            "target": result["target"],
            "functions": ["Random", "SeedRng"],
            "generator": {
                "repository": "SakuraiTsubaki/Decompilation",
                "tool": "tools/rng_evidence.py",
                "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            "outputs": [
                {
                    "path": path.as_posix(),
                    "sha256": hashlib.sha256((args.root / path).read_bytes()).hexdigest(),
                }
                for path in relative_outputs
            ],
            "raw_rom_bytes_included": False,
        }
        manifest_path = args.root / "manifests/rng-reconstruction.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
