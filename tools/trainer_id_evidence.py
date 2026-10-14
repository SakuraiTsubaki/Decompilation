#!/usr/bin/env python3
"""Build publication-safe evidence for Generation III trainer-ID byte helpers."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


VARIANTS = {
    "rs": (("write-word", "write_word_to_mem"), ("copy-word", "copy_word_to_mem")),
    "emerald": (
        ("set-trainer-id", "SetTrainerId"),
        ("get-trainer-id", "GetTrainerId"),
        ("copy-trainer-id", "CopyTrainerId"),
    ),
    "frlg": (("set-trainer-id", "SetTrainerId"), ("copy-trainer-id", "CopyTrainerId")),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def build(
    root: Path,
    rom: Path,
    expected_sha256: str,
    release: str,
    prefix: str,
    variant: str,
    reference_repository: str,
    reference_commit: str,
) -> list[Path]:
    data = rom.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    source_path = root / "src/trainer_id.c"
    records = []
    cfg_paths = []
    for slug, name in VARIANTS[variant]:
        relative = Path(f"analysis/{prefix}-jp-{slug}-cfg.json")
        path = root / relative
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if cfg["source_sha256"] != digest or not cfg.get("raw_halfwords_omitted"):
            raise ValueError(f"{slug} CFG targets another ROM or contains raw words")
        if len(cfg["returns"]) != 1 or cfg["calls"]:
            raise ValueError(f"{slug} must have one return and no calls")
        start = cfg["range_start"]
        end = cfg["range_end"]
        start_offset = start - cfg["rom_base"]
        end_offset = end - cfg["rom_base"]
        records.append(
            {
                "name": name,
                "address": f"0x{start:08X}",
                "range_end_exclusive": f"0x{end:08X}",
                "rom_code_range": {
                    "start_offset": start_offset,
                    "end_offset_exclusive": end_offset,
                    "length": end_offset - start_offset,
                    "sha256": hashlib.sha256(data[start_offset:end_offset]).hexdigest(),
                    "raw_bytes_published": False,
                },
                "cfg": relative.as_posix(),
                "edge_count": len(cfg["edges"]),
                "return_count": len(cfg["returns"]),
            }
        )
        cfg_paths.append(path)

    map_path = root / f"analysis/{prefix}-jp-trainer-id-helpers-map.json"
    report_path = root / "research/trainer-id-helpers-reconstruction.md"
    manifest_path = root / "manifests/trainer-id-helpers-reconstruction.json"
    evidence = {
        "schema_version": 1,
        "target": {"release": release, "sha256": digest},
        "variant": variant,
        "source": "src/trainer_id.c",
        "source_sha256": sha256(source_path),
        "byte_order": "little-endian",
        "trainer_id_length": 4,
        "functions": records,
        "naming_basis": {
            "repository": reference_repository,
            "commit": reference_commit,
            "path": "src/new_game.c",
            "raw_rom_bytes_published": False,
        },
    }
    write_json(map_path, evidence)
    bullets = "\n".join(
        f"- `{record['name']}`: `{record['address']}..{record['range_end_exclusive']}`, "
        f"SHA-256 `{record['rom_code_range']['sha256']}`."
        for record in records
    )
    report_path.write_text(
        f"""# {release} trainer-ID helper reconstruction

The verified Japanese ROM contains the following four-byte trainer-ID helpers:

{bullets}

The setters serialize a 32-bit value in little-endian order. Copy helpers move exactly four bytes; the Emerald-specific getter reconstructs the same little-endian value. Every function has one observed return, and none calls another routine.

Names and behavior are corroborated by `{reference_repository}` commit `{reference_commit}`, `src/new_game.c`. The ROM digests and publication-safe CFGs are authoritative here. No ROM instruction bytes are published.
""",
        encoding="utf-8",
        newline="\n",
    )
    outputs = [source_path, *cfg_paths, map_path, report_path]
    manifest = {
        "schema_version": 1,
        "target": {"release": release, "sha256": digest},
        "functions": [name for _, name in VARIANTS[variant]],
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/trainer_id_evidence.py",
            "tool_sha256": sha256(Path(__file__)),
        },
        "outputs": [
            {"path": path.relative_to(root).as_posix(), "sha256": sha256(path)}
            for path in outputs
        ],
        "raw_rom_bytes_included": False,
    }
    write_json(manifest_path, manifest)
    return [*outputs, manifest_path]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--variant", choices=tuple(VARIANTS), required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(
            args.root,
            args.rom,
            args.expected_sha256,
            args.release,
            args.prefix,
            args.variant,
            args.reference_repository,
            args.reference_commit,
        )
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
