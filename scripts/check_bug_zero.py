#!/usr/bin/env python3
"""Fail closed unless a target has a verified identity and zero open known defects."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

TERMINAL_STATUSES = {"CLOSED", "INTENDED_QUIRK"}
TARGET_ALIASES = {
    "X": {"x", "pokemon x", "pokémon x", "pocket monsters x"},
    "Y": {"y", "pokemon y", "pokémon y", "pocket monsters y"},
    "Omega Ruby": {
        "omega ruby", "pokemon omega ruby", "pokémon omega ruby",
        "pocket monsters omega ruby", "or",
    },
    "Alpha Sapphire": {
        "alpha sapphire", "pokemon alpha sapphire", "pokémon alpha sapphire",
        "pocket monsters alpha sapphire", "as",
    },
    "Scarlet": {"scarlet"},
    "Violet": {"violet"},
    "Z-A": {"z-a", "legends z-a", "pokemon legends z-a", "pokémon legends: z-a"},
}
GENERATION_VI_TARGETS = {"X", "Y", "Omega Ruby", "Alpha Sapphire"}
GENERATION_IX_TARGETS = {"Scarlet", "Violet", "Z-A"}
GENVI_SCOPE_TARGETS = {
    "xy": {"X", "Y"},
    "oras": {"Omega Ruby", "Alpha Sapphire"},
    "xy+oras": GENERATION_VI_TARGETS,
    "genvi": GENERATION_VI_TARGETS,
    "generation vi": GENERATION_VI_TARGETS,
}
GENIX_REQUIRED_COLUMNS = {
    "id", "targets", "category", "name", "affected_scope",
    "upstream_fix", "status", "source", "notes",
}
GENVI_SEED_REQUIRED_COLUMNS = {
    "id", "scope", "category", "name", "reported_versions",
    "verification", "source",
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


def targets_row_applies(target: str, raw_targets: str) -> bool:
    aliases = TARGET_ALIASES[target]
    tokens = {normalize(token) for token in raw_targets.split("|") if token.strip()}
    return bool(tokens & aliases)


def scope_row_applies(target: str, raw_scope: str) -> bool:
    scope = normalize(raw_scope)
    mapped = GENVI_SCOPE_TARGETS.get(scope)
    if mapped is not None:
        return target in mapped
    return targets_row_applies(target, raw_scope)


def infer_seed_status(verification: str) -> str:
    normalized = verification.strip().upper()
    if normalized in TERMINAL_STATUSES:
        return normalized
    if normalized in {"OFFICIALLY_FIXED", "OFFICIAL_FIX_CORRELATED"}:
        return "UPSTREAM_FIXED_VERIFY"
    return "REPRODUCTION_NEEDED_ON_LATEST"


def validate_registry(path: Path, target: str) -> tuple[int, list[str]]:
    errors: list[str] = []
    try:
        handle = path.open(newline="", encoding="utf-8-sig")
    except FileNotFoundError:
        return 0, [f"missing defect registry: {path}"]

    with handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        is_standard = GENIX_REQUIRED_COLUMNS <= columns
        is_genvi_seed = GENVI_SEED_REQUIRED_COLUMNS <= columns
        if not is_standard and not is_genvi_seed:
            expected = sorted(GENIX_REQUIRED_COLUMNS)
            seed_expected = sorted(GENVI_SEED_REQUIRED_COLUMNS)
            return 0, [
                "defect registry schema not recognized; expected standard columns "
                + ", ".join(expected)
                + " or Generation VI seed columns "
                + ", ".join(seed_expected)
            ]

        applicable = 0
        for line_number, row in enumerate(reader, 2):
            if is_standard:
                applies = targets_row_applies(target, row.get("targets", ""))
                status = row.get("status", "").strip().upper()
            else:
                applies = scope_row_applies(target, row.get("scope", ""))
                status = infer_seed_status(row.get("verification", ""))

            if not applies:
                continue

            applicable += 1
            bug_id = row.get("id", "").strip() or f"line-{line_number}"
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


def default_registry_for(target: str) -> Path:
    if target in GENERATION_VI_TARGETS:
        return Path("manifests/generation-vi-known-defects.csv")
    if target in GENERATION_IX_TARGETS:
        return Path("manifests/generation-ix-known-defects.csv")
    raise ValueError(f"no default defect registry for target {target}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=sorted(TARGET_ALIASES), required=True)
    parser.add_argument("--target-config", type=Path, required=True)
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args(argv)

    registry = args.registry or default_registry_for(args.target)
    errors = validate(args.target, args.target_config, registry)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
