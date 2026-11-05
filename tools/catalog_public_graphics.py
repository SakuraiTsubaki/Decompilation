#!/usr/bin/env python3
"""Catalog every public graphics artifact and generate a GitHub preview page."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import struct
from pathlib import Path


LANGUAGES = {
    "jp": "Japanese",
    "ko": "Korean",
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "es": "Spanish",
}
RELEASE_LANGUAGE_CODES = {
    "j": "Japanese",
    "e": "English",
    "d": "German",
    "f": "French",
    "i": "Italian",
    "s": "Spanish",
}
LANGUAGE_PRIORITY = {
    "Japanese": 0,
    "Korean": 1,
    "English": 2,
    "Global": 3,
    "German": 4,
    "French": 5,
    "Italian": 6,
    "Spanish": 7,
    "Unspecified": 8,
}
PNG_COLOR_TYPES = {0: "grayscale", 2: "truecolor", 3: "indexed", 4: "grayscale-alpha", 6: "truecolor-alpha"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def png_metadata(data: bytes) -> dict[str, int | str]:
    if len(data) < 33 or not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
        raise ValueError("invalid PNG header")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", data[16:29]
    )
    if width < 1 or height < 1 or compression != 0 or filtering != 0 or interlace not in (0, 1):
        raise ValueError("invalid PNG IHDR")
    if color_type not in PNG_COLOR_TYPES:
        raise ValueError("unsupported PNG color type")
    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": PNG_COLOR_TYPES[color_type],
        "interlaced": bool(interlace),
    }


def jasc_palette_metadata(data: bytes) -> dict[str, int | str]:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("JASC palette is not ASCII") from error
    if len(lines) < 3 or lines[0] != "JASC-PAL" or lines[1] != "0100":
        raise ValueError("invalid JASC palette header")
    try:
        color_count = int(lines[2])
        color_lines = [line for line in lines[3:] if line.strip()]
        colors = [tuple(int(channel) for channel in line.split()) for line in color_lines]
    except ValueError as error:
        raise ValueError("invalid JASC palette value") from error
    if color_count < 1 or len(colors) != color_count:
        raise ValueError("JASC palette color count differs")
    if any(len(color) != 3 or any(channel < 0 or channel > 255 for channel in color)
           for color in colors):
        raise ValueError("JASC palette contains an invalid RGB color")
    return {"version": "0100", "color_count": color_count}


def asset_language(path: Path) -> str:
    stem = path.stem.lower()
    for code, language in LANGUAGES.items():
        if stem.endswith("-" + code) or f"-{code}-" in stem:
            return language
    for code, language in RELEASE_LANGUAGE_CODES.items():
        if f"-{code}-" in stem:
            return language
    if "global" in stem:
        return "Global"
    return "Unspecified"


def contains_path(value: object, target: str) -> bool:
    if isinstance(value, dict):
        if any(value.get(key) == target for key in ("path", "png", "output")):
            return True
        releases = value.get("releases")
        templates = value.get("path_templates")
        if isinstance(releases, dict) and isinstance(templates, dict):
            for template in templates.values():
                if isinstance(template, str) and "{language}" in template:
                    if any(template.replace("{language}", code) == target for code in releases):
                        return True
        return any(contains_path(item, target) for item in value.values())
    if isinstance(value, list):
        return any(contains_path(item, target) for item in value)
    return value == target


def evidence_documents(root: Path) -> list[tuple[Path, object]]:
    documents = []
    excluded = {
        "manifests/public-graphics-catalog.json",
        "analysis/public-graphics-catalog.json",
    }
    for directory in (root / "manifests", root / "analysis"):
        for path in sorted(directory.rglob("*.json")):
            if path.relative_to(root).as_posix() in excluded:
                continue
            try:
                documents.append((path, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError):
                continue
    return documents


def provenance(root: Path, documents: list[tuple[Path, object]], target: str) -> list[dict[str, str]]:
    result = []
    for path, content in documents:
        if contains_path(content, target):
            result.append({"path": path.relative_to(root).as_posix(), "sha256": file_hash(path)})
    return result


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def markdown(game: str, assets: list[dict[str, object]]) -> str:
    lines = [
        f"# {game} public graphics",
        "",
        "This page is generated from the repository's verified `graphics/` tree. Japanese and Korean assets are listed before English and other official languages.",
        "",
    ]
    categories = dict.fromkeys(str(item["category"]) for item in assets)
    for category in categories:
        group = [item for item in assets if item["category"] == category]
        lines.extend((f"## {category.title()}", ""))
        pngs = [item for item in group if item["format"] == "PNG"]
        if pngs:
            lines.extend(("| Preview | File | Language | Size | SHA-256 |", "| --- | --- | --- | --- | --- |"))
            for item in pngs:
                path = str(item["path"])
                meta = item["png"]
                preview = f'<img src="{html.escape(path)}" alt="{html.escape(Path(path).stem)}" width="128">'
                lines.append(
                    f"| {preview} | [`{path}`]({path}) | {item['language']} | "
                    f"{meta['width']}x{meta['height']} | `{str(item['sha256'])[:16]}...` |"
                )
            lines.append("")
        sidecars = [item for item in group if item["format"] == "JSON"]
        if sidecars:
            lines.extend(("Metadata sidecars:", ""))
            lines.extend(f"- [`{item['path']}`]({item['path']}) — `{str(item['sha256'])[:16]}...`" for item in sidecars)
            lines.append("")
        palettes = [item for item in group if item["format"] == "JASC-PAL"]
        if palettes:
            lines.extend(("| Palette | Language | Colors | SHA-256 |", "| --- | --- | --- | --- |"))
            for item in palettes:
                path = str(item["path"])
                lines.append(
                    f"| [`{path}`]({path}) | {item['language']} | "
                    f"{item['palette']['color_count']} | `{str(item['sha256'])[:16]}...` |"
                )
            lines.append("")
    lines.extend(
        (
            "Every entry is tied to at least one existing analysis or manifest record. Full hashes and provenance links are in `analysis/public-graphics-catalog.json`.",
            "",
        )
    )
    return "\n".join(lines)


def build(root: Path, game: str) -> dict[str, object]:
    graphics = root / "graphics"
    paths = sorted(path for path in graphics.rglob("*") if path.is_file() and path.suffix.lower() in (".png", ".json", ".pal"))
    if not paths:
        raise ValueError("repository has no public graphics artifacts")
    documents = evidence_documents(root)
    assets = []
    for path in paths:
        relative = path.relative_to(root)
        relative_text = relative.as_posix()
        data = path.read_bytes()
        owners = provenance(root, documents, relative_text)
        if not owners:
            raise ValueError(f"graphics artifact has no existing provenance: {relative_text}")
        category = relative.parts[1] if len(relative.parts) > 2 else "other"
        item: dict[str, object] = {
            "path": relative_text,
            "sha256": digest(data),
            "size": len(data),
            "format": {".png": "PNG", ".json": "JSON", ".pal": "JASC-PAL"}[path.suffix.lower()],
            "category": category,
            "language": asset_language(relative),
            "origin_reference": asset_language(relative) == "Japanese",
            "provenance": owners,
        }
        if path.suffix.lower() == ".png":
            item["png"] = png_metadata(data)
        elif path.suffix.lower() == ".pal":
            item["palette"] = jasc_palette_metadata(data)
        else:
            json.loads(data.decode("utf-8"))
        assets.append(item)
    assets.sort(
        key=lambda item: (
            str(item["category"]),
            LANGUAGE_PRIORITY[str(item["language"])],
            str(item["path"]),
        )
    )
    catalog = {
        "schema_version": 1,
        "game": game,
        "root": "graphics",
        "asset_count": len(assets),
        "png_count": sum(item["format"] == "PNG" for item in assets),
        "metadata_count": sum(item["format"] == "JSON" for item in assets),
        "palette_count": sum(item["format"] == "JASC-PAL" for item in assets),
        "official_language_priority": ["Japanese", "Korean", "English", "German", "French", "Italian", "Spanish"],
        "assets": assets,
        "raw_rom_bytes_included": False,
    }
    catalog_path = Path("analysis/public-graphics-catalog.json")
    write_json(root / catalog_path, catalog)
    assets_path = Path("ASSETS.md")
    (root / assets_path).write_text(markdown(game, assets), encoding="utf-8", newline="\n")
    research_path = Path("research/public-graphics-catalog.md")
    (root / research_path).write_text(
        f"# {game} public graphics catalog\n\n"
        f"The catalog inventories all {len(assets)} files currently stored below `graphics/`: "
        f"{catalog['png_count']} rendered PNG assets, {catalog['palette_count']} JASC palettes, "
        f"and {catalog['metadata_count']} JSON sidecars. "
        "Each entry records its full hash and points to the pre-existing ROM-derived analysis or "
        "manifest that establishes provenance. `ASSETS.md` supplies a browsable GitHub preview.\n\n"
        "The catalog does not infer a language when the filename does not declare one, and it "
        "does not embed ROM bytes.\n",
        encoding="utf-8",
        newline="\n",
    )
    test_path = Path("tests/test_public_graphics_catalog.py")
    if not (root / test_path).is_file():
        raise ValueError("missing catalog test")
    outputs = [catalog_path, assets_path, research_path, test_path]
    manifest = {
        "schema_version": 1,
        "game": game,
        "asset_count": len(assets),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/catalog_public_graphics.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "inputs": [{"path": item["path"], "sha256": item["sha256"]} for item in assets],
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/public-graphics-catalog.json", manifest)
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--game", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.game)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

