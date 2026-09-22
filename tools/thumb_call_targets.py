#!/usr/bin/env python3
"""Summarize direct Thumb BL targets from a verified entry CFG."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def summarize(cfg: dict) -> dict:
    calls = cfg.get("calls")
    if not isinstance(calls, list):
        raise ValueError("CFG calls must be a list")
    rom_base = cfg.get("rom_base", 0x08000000)
    source_size = cfg.get("source_size")
    if not isinstance(source_size, int) or source_size <= 0:
        raise ValueError("CFG source_size must be a positive integer")
    grouped: dict[int, list[int]] = defaultdict(list)
    for call in calls:
        source, target = call.get("source"), call.get("target")
        if not isinstance(source, int) or not isinstance(target, int):
            raise ValueError("call source and target must be integers")
        if target & 1:
            raise ValueError("Thumb BL target must be halfword-aligned")
        grouped[target].append(source)
    targets = []
    for target in sorted(grouped):
        sources = sorted(grouped[target])
        in_rom = rom_base <= target < rom_base + source_size
        targets.append({
            "target_address": target,
            "target_offset": target - rom_base if in_rom else None,
            "in_rom": in_rom,
            "call_count": len(sources),
            "source_addresses": sources,
        })
    return {
        "schema_version": 1,
        "source_cfg_sha256": cfg.get("source_sha256"),
        "entry_address": cfg.get("start_address"),
        "call_sites": len(calls),
        "unique_targets": len(targets),
        "repeated_targets": sum(1 for item in targets if item["call_count"] > 1),
        "targets": targets,
    }


def analyze(path: Path, expected_sha256: str | None = None) -> dict:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("CFG SHA-256 mismatch")
    cfg = json.loads(data)
    result = summarize(cfg)
    result["input_cfg_sha256"] = digest
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cfg", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = analyze(args.cfg, args.expected_sha256)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
