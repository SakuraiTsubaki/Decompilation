#!/usr/bin/env python3
"""Validate the shared decompilation repository without third-party packages."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REQUIRED_PATHS = (
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "LICENSE",
    "analysis/README.md",
    "analysis/template.md",
    "docs/methodology.md",
    "docs/repository-model.md",
    "research/README.md",
    "research/template.md",
    "tools/README.md",
)
BLOCKED_SUFFIXES = {
    ".3ds", ".cci", ".cia", ".gb", ".gba", ".gbc", ".iso",
    ".nds", ".nsp", ".rom", ".xci",
}
TEXT_SUFFIXES = {
    "", ".c", ".cc", ".cfg", ".cpp", ".h", ".hpp", ".inc", ".ini",
    ".json", ".md", ".py", ".s", ".sh", ".toml", ".txt", ".yaml", ".yml",
}
SKIP_PARTS = {".git", ".venv", "node_modules"}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and not any(part in SKIP_PARTS for part in path.parts):
            yield path


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    for relative in REQUIRED_PATHS:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")

    for path in iter_files(root):
        relative = path.relative_to(root)
        if path.suffix.lower() in BLOCKED_SUFFIXES:
            errors.append(f"blocked binary/package file: {relative}")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            data = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"text file is not UTF-8: {relative}")
            continue
        for number, line in enumerate(data.splitlines(), 1):
            if line.endswith((" ", "\t")):
                errors.append(f"trailing whitespace: {relative}:{number}")
        if data and not data.endswith("\n"):
            errors.append(f"missing final newline: {relative}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    errors = validate(root)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1

    print(f"repository validation passed: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
