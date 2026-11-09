#!/usr/bin/env python3
"""Reconstruct the FRLG Div wrapper variant across Decompilation catalogs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import register_ram_reset_catalog as common


SIGNATURE = bytes.fromhex("06df7047")
LZ_RELATIVE = -4
PROFILE = {
    "repository": "pret/pokefirered",
    "commit": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "path": "src/libagbsyscall.s",
}


def locate(data: bytes) -> list[int]:
    result, start = [], 0
    while True:
        offset = data.find(SIGNATURE, start)
        if offset < 0:
            return result
        result.append(offset)
        start = offset + 1


def source_text() -> str:
    return """.syntax unified
.thumb

.global Div
.type Div, %function
Div:
    swi 0x06
    bx lr
.size Div, . - Div
"""


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str) -> dict:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    roms = common.rom_index(rom_dir)
    source_path = Path("src/div_bios_stub.s")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        lz_path = Path(f"analysis/{release_id}-lz77-bios-stub-map.json")
        lz = json.loads((root / lz_path).read_text(encoding="utf-8"))
        anchor = int(lz["functions"]["LZ77UnCompVram"]["rom_offset"])
        data = roms[sha256].read_bytes()
        matches = locate(data)
        selected = anchor + LZ_RELATIVE
        is_japanese = release["language"] == "Japanese"
        if is_japanese:
            if matches:
                raise ValueError(f"Japanese Div absence changed in {release_id}: {matches}")
            function = None
            availability = "absent"
        else:
            if matches != [selected]:
                raise ValueError(f"global Div layout differs in {release_id}: {matches}")
            function = {
                "name": "Div", "rom_offset": selected,
                "address": f"0x{common.ROM_BASE + selected:08X}",
                "range_end_exclusive": f"0x{common.ROM_BASE + selected + 4:08X}",
                "length": 4, "code_sha256": common.digest(data[selected:selected + 4]),
                "numerator_register": "r0", "denominator_register": "r1",
                "quotient_register": "r0", "remainder_register": "r1",
                "absolute_quotient_register": "r3", "software_interrupt": 6,
                "return": "bx lr", "lz77_vram_relative_offset": LZ_RELATIVE,
            }
            availability = "present"
        evidence = {
            "schema_version": 1, "axis": "Decompilation",
            "target": {"release": release_id, "sha256": sha256,
                       "build_kind": release["build_kind"]},
            "origin_reference": index == 0, "availability": availability,
            "source_applies": function is not None, "source": source_path.as_posix(),
            "source_sha256": common.file_hash(root / source_path), "function": function,
            "verified_layout": {
                "lz77_vram_anchor": lz["functions"]["LZ77UnCompVram"]["address"],
                "expected_relative_offset_when_present": LZ_RELATIVE,
                "signature_match_count": len(matches),
            },
            "cross_reference": {"lz77_bios_stub_map": lz_path.as_posix(),
                                "sha256": common.file_hash(root / lz_path)},
            "naming_basis": PROFILE, "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-div-bios-stub-variant-map.json")
        common.write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id, "language": release["language"],
            "revision": release["revision"], "build_kind": release["build_kind"],
            "sha256": sha256, "origin_reference": index == 0,
            "availability": availability,
            "address": function["address"] if function else None,
            "lz77_vram_relative_offset": LZ_RELATIVE if function else None,
            "evidence": map_path.as_posix(),
        })
    present = sum(item["availability"] == "present" for item in records)
    summary = {
        "schema_version": 1, "axis": "Decompilation", "game": game,
        "library": "libagbsyscall", "function": "Div",
        "family_profile": "frlg-language-variant",
        "origin_reference": releases[0]["id"],
        "origin_availability": records[0]["availability"],
        "release_count": len(records), "present_release_count": present,
        "absent_release_count": len(records) - present,
        "source": source_path.as_posix(), "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/div-bios-stub-variant-summary.json")
    common.write_json(root / summary_path, summary)
    research_path = Path("research/div-bios-stub-variant-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} Div BIOS stub variant reconstruction\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference and lacks `Div`. "
        f"The wrapper is independently reconstructed in {present} of {len(records)} "
        "cataloged builds: all English, German, French, Italian, and Spanish releases, "
        "at -4 from the verified `LZ77UnCompVram` anchor. The committed source applies "
        "only to those builds. Presence and absence are retained without ROM bytes.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_div_bios_stub_variant_catalog.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    common.write_json(root / "manifests/div-bios-stub-variant-reconstruction.json", {
        "schema_version": 1, "axis": "Decompilation", "game": game,
        "function": "Div", "family_profile": "frlg-language-variant",
        "origin_reference": releases[0]["id"],
        "origin_availability": records[0]["availability"],
        "release_count": len(records), "present_release_count": present,
        "generator": {"repository": "SakuraiTsubaki/Decompilation",
                      "tool": "tools/frlg_div_variant_catalog.py",
                      "tool_sha256": common.file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": common.file_hash(root / path)}
                    for path in outputs], "raw_rom_bytes_included": False,
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path,
                        default=Path("analysis/global-release-catalog.json"))
    parser.add_argument("--game", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
