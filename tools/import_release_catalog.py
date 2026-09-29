#!/usr/bin/env python3
"""Import verified release identities as Decompilation target evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def import_catalog(source_text: str, expected_prefix: str, source_repository: str, source_artifact: str) -> dict:
    source = json.loads(source_text)
    if source.get("game_code_prefix") != expected_prefix:
        raise ValueError("game-code prefix mismatch")
    releases = source.get("releases")
    if not isinstance(releases, list) or not releases:
        raise ValueError("source catalog has no releases")
    required = {"id", "language", "revision", "build_kind", "sha1", "sha256", "header", "validation"}
    for release in releases:
        if not required.issubset(release):
            raise ValueError("source release is incomplete")
        if not all(release["validation"].get(key) for key in (
            "nintendo_logo_valid", "fixed_value_valid", "reserved_area_valid", "header_checksum_valid"
        )):
            raise ValueError(f"source release failed validation: {release['id']}")
    return {
        "schema_version": 1,
        "purpose": "decompilation-release-target-evidence",
        "origin_reference": "Japanese",
        "official_language_scope": source.get("language_priority", []),
        "game_code_prefix": expected_prefix,
        "source": {
            "repository": source_repository,
            "artifact": source_artifact,
            "sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        },
        "observed_files": source.get("observed_files"),
        "unique_identities": source.get("unique_identities"),
        "releases": releases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--game-code-prefix", required=True)
    parser.add_argument("--source-repository", required=True)
    parser.add_argument("--source-artifact", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-artifact", default="analysis/global-release-catalog.json")
    parser.add_argument("--manifest-output", type=Path)
    args = parser.parse_args()
    try:
        text = args.source.read_text(encoding="utf-8")
        result = import_catalog(text, args.game_code_prefix, args.source_repository, args.source_artifact)
        output_text = json.dumps(result, indent=2) + "\n"
        args.output.write_text(output_text, encoding="utf-8", newline="\n")
        if args.manifest_output:
            manifest = {
                "schema_version": 1,
                "generator": {"repository": "SakuraiTsubaki/Decompilation", "tool": "tools/import_release_catalog.py"},
                "inputs": [{"repository": args.source_repository, "path": args.source_artifact, "sha256": result["source"]["sha256"]}],
                "outputs": [{"path": args.output_artifact, "sha256": hashlib.sha256(output_text.encode("utf-8")).hexdigest()}],
            }
            args.manifest_output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
