#!/usr/bin/env python3
"""Create a reproducible SHA-256 inventory for a local Switch package or extracted tree.

The input itself is never copied. The output contains only metadata and hashes so it can
be committed safely under the project's no-ROM policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(path: Path, label: str | None = None) -> dict:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    if path.is_file():
        files = [path]
        root_type = "file"
        root = path.parent
    elif path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file())
        root_type = "directory"
        root = path
    else:
        raise ValueError(f"unsupported input type: {path}")

    entries = []
    total_size = 0
    for file_path in files:
        size = file_path.stat().st_size
        total_size += size
        relative = file_path.name if root_type == "file" else file_path.relative_to(root).as_posix()
        entries.append({
            "path": relative,
            "size": size,
            "sha256": sha256_file(file_path),
        })

    return {
        "schema": 1,
        "label": label,
        "input_type": root_type,
        "file_count": len(entries),
        "total_size": total_size,
        "files": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--label")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        result = inventory(args.input, args.label)
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"inventory written: {args.output} "
        f"({result['file_count']} files, {result['total_size']} bytes)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
