#!/usr/bin/env python3
"""Summarize Generation IX defect-registry progress for one target."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
import json
from pathlib import Path
import sys

TERMINAL_STATUSES = {"CLOSED", "INTENDED_QUIRK"}
TARGET_ALIASES = {
    "Scarlet": {"scarlet"},
    "Violet": {"violet"},
    "Z-A": {"z-a", "legends z-a", "pokemon legends z-a", "pokémon legends: z-a"},
}


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def row_applies(target: str, raw_targets: str) -> bool:
    aliases = TARGET_ALIASES[target]
    tokens = {normalize(token) for token in raw_targets.split("|") if token.strip()}
    return bool(tokens & aliases)


def summarize(registry: Path, target: str) -> dict:
    with registry.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = [row for row in reader if row_applies(target, row.get("targets", ""))]

    status_counts = Counter((row.get("status") or "<empty>").strip().upper() for row in rows)
    category_counts = Counter((row.get("category") or "<empty>").strip() for row in rows)
    blockers = [
        {
            "id": (row.get("id") or "").strip(),
            "status": (row.get("status") or "").strip().upper(),
            "category": (row.get("category") or "").strip(),
            "name": (row.get("name") or "").strip(),
        }
        for row in rows
        if (row.get("status") or "").strip().upper() not in TERMINAL_STATUSES
    ]

    return {
        "target": target,
        "total": len(rows),
        "terminal": len(rows) - len(blockers),
        "blocking": len(blockers),
        "status_counts": dict(sorted(status_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=sorted(TARGET_ALIASES), required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("manifests/generation-ix-known-defects.csv"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-blockers", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = summarize(args.registry, args.target)
    except (FileNotFoundError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")

    if args.fail_on_blockers and result["blocking"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
