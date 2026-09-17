#!/usr/bin/env python3
"""Fail closed unless a Generation IX target has a verified identity and zero open known defects."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

TERMINAL_STATUSES = {"CLOSED", "INTENDED_QUIRK"}
TARGET_ALIASES = {
    "Scarlet": {"scarlet"},
    "Violet": {"violet"},
    "Z-A": {"z-a", "legends z-a", "pokemon legends z-a", "pokémon legends: z-a"},
}
REQUIRED_COLUMNS = {
    "id", "targets", "category", "name", "affected_scope",
    "upstream_fix", "status", "source", "notes",
}


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def load_target_config(path: Path) -> tuple[dict, list[str]]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, [f"missing target config: {path}"]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return {}, [f"invalid target config {path}: {error}"]

    if data.get("identity_status") != "verified":
        errors.append(
            f"target identity is not verified: {data.get('identity_status')!r}"
        )
    hashes = data.get("hashes")
    if not isinstance(hashes, list) or not hashes:
        errors.append("target config has no recorded cryptographic hashes")
    return data, errors


def row_applies(target: str, raw_targets: str) -> bool:
    aliases = TARGET_ALIASES[target]
    tokens = {normalize(token) for token in raw_targets.split("|") if token.strip()}
    return bool(tokens & aliases)


def validate_registry(path: Path, target: str) -> tuple[int, list[str]]:
    errors: list[str] = []
    try:
        handle = path.open(newline="", encoding="utf-8-sig")
    except FileNotFoundError:
        return 0, [f"missing defect registry: {path}"]

    with handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        missing = REQUIRED_COLUMNS - columns
        if missing:
            return 0, [
                "defect registry missing columns: " + ", ".join(sorted(missing))
            ]

        applicable = 0
        for line_number, row in enumerate(reader, 2):
            if not row_applies(target, row.get("targets", "")):
                continue
            applicable += 1
            bug_id = row.get("id", "").strip() or f"line-{line_number}"
            status = row.get("status", "").strip().upper()
            if status not in TERMINAL_STATUSES:
                errors.append(
                    f"{bug_id}: blocking defect status {status or '<empty>'}"
                )

    if applicable == 0:
        errors.append(f"no registry entries apply to target {target}")
    return applicable, errors


def validate(target: str, target_config: Path, registry: Path) -> list[str]:
    errors: list[str] = []
    _, config_errors = load_target_config(target_config)
    errors.extend(config_errors)

    applicable, registry_errors = validate_registry(registry, target)
    errors.extend(registry_errors)

    if not errors:
        print(
            f"bug-zero gate passed: target={target}, "
            f"verified_registry_entries={applicable}"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=sorted(TARGET_ALIASES), required=True)
    parser.add_argument("--target-config", type=Path, required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("manifests/generation-ix-known-defects.csv"),
    )
    args = parser.parse_args(argv)

    errors = validate(args.target, args.target_config, args.registry)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
