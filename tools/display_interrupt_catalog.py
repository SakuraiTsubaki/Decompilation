#!/usr/bin/env python3
"""Reconstruct display/serial interrupt handlers across Gen III release catalogs."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thumb_cfg


ROM_BASE = 0x08000000
INTR_CHECK = 0x03007FF8
REG_VCOUNT = 0x04000006
FUNCTION_LENGTHS = {"common": 38, "emerald_vcount": 42, "frlg_vcount": 38}

COMMON_HBLANK = (
    0xB510, 0x4C09, 0x6920, 0x2800, 0xD001, None, None, 0x4A07, 0x8810,
    0x2102, 0x4308, 0x8010, 0x8BA0, 0x8BA2, 0x4301, 0x83A1, 0xBC10, 0xBC01, 0x4700,
)
COMMON_SERIAL = (
    0xB510, 0x4C09, 0x69A0, 0x2800, 0xD001, None, None, 0x4A07, 0x8810,
    0x2180, 0x4308, 0x8010, 0x8BA0, 0x8BA2, 0x4301, 0x83A1, 0xBC10, 0xBC01, 0x4700,
)
RS_VCOUNT = (
    0xB510, 0x4C09, 0x6960, 0x2800, 0xD001, None, None, 0x4A07, 0x8810,
    0x2104, 0x4308, 0x8010, 0x8BA0, 0x8BA2, 0x4301, 0x83A1, 0xBC10, 0xBC01, 0x4700,
)
EMERALD_VCOUNT = (
    0xB510, 0x4C0A, 0x6960, 0x2800, 0xD001, None, None, None, None, 0x4A07,
    0x8810, 0x2104, 0x4308, 0x8010, 0x8BA0, 0x8BA2, 0x4301, 0x83A1, 0xBC10, 0xBC01, 0x4700,
)
FRLG_VCOUNT = (
    0xB500, 0x4909, 0x4809, 0x8800, 0x7008, None, None, 0x4A08, 0x8810,
    0x2104, 0x4308, 0x8010, 0x4806, 0x8B82, 0x8B83, 0x4311, 0x8381, 0xBC01, 0x4700,
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def rom_index(directory: Path) -> dict[str, Path]:
    result = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() == ".gba":
            result.setdefault(file_hash(path), path)
    return result


def is_bl(first: int, second: int) -> bool:
    return first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def matches_template(words: tuple[int, ...], template: tuple[int | None, ...]) -> bool:
    if len(words) != len(template):
        return False
    for index, expected in enumerate(template):
        if expected is not None and words[index] != expected:
            return False
    masked = [index for index, expected in enumerate(template) if expected is None]
    return len(masked) % 2 == 0 and all(
        masked[index + 1] == masked[index] + 1 and is_bl(words[masked[index]], words[masked[index + 1]])
        for index in range(0, len(masked), 2)
    )


def matching_offsets(data: bytes, template: tuple[int | None, ...]) -> list[int]:
    size = len(template) * 2
    prefix = struct.pack("<H", template[0])
    matches = []
    start = 0
    while True:
        offset = data.find(prefix, start)
        if offset < 0:
            break
        if offset % 2 == 0 and offset + size <= len(data):
            words = struct.unpack_from(f"<{len(template)}H", data, offset)
            if matches_template(words, template):
                matches.append(offset)
        start = offset + 2
    return matches


def unique_offset(data: bytes, template: tuple[int | None, ...], name: str) -> int:
    matches = matching_offsets(data, template)
    if len(matches) != 1:
        raise ValueError(f"expected one {name} candidate, found {len(matches)}")
    return matches[0]


def profile_templates(profile: str) -> tuple[tuple[int | None, ...], tuple[int | None, ...], tuple[int | None, ...]]:
    if profile == "rs":
        return COMMON_HBLANK, RS_VCOUNT, COMMON_SERIAL
    if profile == "emerald":
        return COMMON_HBLANK, EMERALD_VCOUNT, COMMON_SERIAL
    if profile == "frlg":
        return COMMON_HBLANK, FRLG_VCOUNT, COMMON_SERIAL
    raise ValueError(f"unsupported profile: {profile}")


def reconstructed_source(profile: str) -> str:
    if profile not in {"rs", "emerald", "frlg"}:
        raise ValueError(f"unsupported profile: {profile}")
    extra_externs = ""
    vcount_body = """    if (gMain.vcountCallback != 0)
        gMain.vcountCallback();
"""
    if profile == "emerald":
        extra_externs = "extern void m4aSoundVSync(void);\n"
        vcount_body += "    m4aSoundVSync();\n"
    elif profile == "frlg":
        extra_externs = "extern uint8_t sVcountAtIntr;\nextern void m4aSoundVSync(void);\n"
        vcount_body = "    sVcountAtIntr = (uint8_t)REG_VCOUNT;\n    m4aSoundVSync();\n"
    reg_vcount = "#define REG_VCOUNT (*(volatile uint16_t *)0x04000006)\n" if profile == "frlg" else ""
    return f"""#include <stdint.h>

typedef void (*IntrCallback)(void);
typedef void (*MainCallback)(void);

struct MainInterruptState
{{
    MainCallback callback1;
    MainCallback callback2;
    uint8_t unknown_008[4];
    IntrCallback vblankCallback;
    IntrCallback hblankCallback;
    IntrCallback vcountCallback;
    IntrCallback serialCallback;
    uint16_t intrCheck;
}};

extern struct MainInterruptState gMain;
{extra_externs}{reg_vcount}#define INTR_CHECK (*(volatile uint16_t *)0x03007FF8)

enum
{{
    INTR_FLAG_HBLANK = 0x0002,
    INTR_FLAG_VCOUNT = 0x0004,
    INTR_FLAG_SERIAL = 0x0080
}};

void HBlankIntr(void)
{{
    if (gMain.hblankCallback != 0)
        gMain.hblankCallback();
    INTR_CHECK |= INTR_FLAG_HBLANK;
    gMain.intrCheck |= INTR_FLAG_HBLANK;
}}

void VCountIntr(void)
{{
{vcount_body}    INTR_CHECK |= INTR_FLAG_VCOUNT;
    gMain.intrCheck |= INTR_FLAG_VCOUNT;
}}

void SerialIntr(void)
{{
    if (gMain.serialCallback != 0)
        gMain.serialCallback();
    INTR_CHECK |= INTR_FLAG_SERIAL;
    gMain.intrCheck |= INTR_FLAG_SERIAL;
}}
"""


def literal_values(data: bytes, offsets: dict[str, int], profile: str) -> dict[str, str]:
    common = struct.unpack_from("<2I", data, offsets["HBlankIntr"] + 40)
    serial = struct.unpack_from("<2I", data, offsets["SerialIntr"] + 40)
    if common[1] != INTR_CHECK or serial[1] != INTR_CHECK or common != serial:
        raise ValueError("HBlank/Serial literal validation failed")
    values = {"gMain": common[0], "INTR_CHECK": common[1]}
    if profile == "rs":
        vcount = struct.unpack_from("<2I", data, offsets["VCountIntr"] + 40)
        if vcount != common:
            raise ValueError("Ruby/Sapphire VCount literals differ from common handlers")
    elif profile == "emerald":
        vcount = struct.unpack_from("<2I", data, offsets["VCountIntr"] + 44)
        if vcount != common:
            raise ValueError("Emerald VCount literals differ from common handlers")
    else:
        saved_vcount, reg_vcount, intr_check, g_main = struct.unpack_from("<4I", data, offsets["VCountIntr"] + 40)
        if reg_vcount != REG_VCOUNT or intr_check != INTR_CHECK or g_main != common[0]:
            raise ValueError("FireRed/LeafGreen VCount literal validation failed")
        values.update({"sVcountAtIntr": saved_vcount, "REG_VCOUNT": reg_vcount})
    ram_keys = ["gMain"] + (["sVcountAtIntr"] if profile == "frlg" else [])
    if any(not 0x03000000 <= values[key] <= 0x03007FFF for key in ram_keys):
        raise ValueError("work RAM literal leaves IWRAM")
    return {key: f"0x{value:08X}" for key, value in values.items()}


def handler_record(data: bytes, offset: int, name: str, call_names: tuple[str, ...]) -> dict[str, object]:
    length = 42 if name == "VCountIntr" and len(call_names) == 2 else 38
    cfg = thumb_cfg.omit_raw_halfwords(thumb_cfg.trace_thumb_function(data, offset, max_span=length))
    expected_end = ROM_BASE + offset + length
    if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or len(cfg["calls"]) != len(call_names):
        raise ValueError(f"CFG boundary mismatch for {name}")
    calls = [
        {"name": call_name, "source": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"}
        for call_name, call in zip(call_names, cfg["calls"])
    ]
    return {
        "name": name,
        "address": f"0x{ROM_BASE + offset:08X}",
        "range_end_exclusive": f"0x{expected_end:08X}",
        "rom_code_range": {
            "start_offset": offset,
            "end_offset_exclusive": offset + length,
            "length": length,
            "sha256": digest(data[offset:offset + length]),
            "raw_bytes_published": False,
        },
        "calls": calls,
        "control_flow": {
            "instruction_halfwords": cfg["instruction_halfwords"],
            "return_count": len(cfg["returns"]),
            "call_count": len(cfg["calls"]),
            "raw_halfwords_omitted": True,
        },
    }


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str, profile: str,
          reference_repository: str, reference_commit: str) -> dict[str, object]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    templates = profile_templates(profile)
    source_path = Path("src/display_serial_interrupts.c")
    (root / source_path).write_text(reconstructed_source(profile), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    outputs: list[Path] = [source_path, catalog_path]
    records = []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        offsets = {
            name: unique_offset(data, template, name)
            for name, template in zip(("HBlankIntr", "VCountIntr", "SerialIntr"), templates)
        }
        call_names = {
            "HBlankIntr": ("indirect hblank callback trampoline",),
            "VCountIntr": (
                ("indirect vcount callback trampoline", "m4aSoundVSync") if profile == "emerald"
                else ("m4aSoundVSync",) if profile == "frlg"
                else ("indirect vcount callback trampoline",)
            ),
            "SerialIntr": ("indirect serial callback trampoline",),
        }
        functions = [handler_record(data, offsets[name], name, call_names[name]) for name in offsets]
        literals = literal_values(data, offsets, profile)
        mapping = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "profile": profile,
            "source": source_path.as_posix(),
            "source_sha256": source_sha256,
            "functions": functions,
            "literal_addresses": literals,
            "proven_offsets": {
                "hblankCallback": 16,
                **({"vcountCallback": 20} if profile != "frlg" else {}),
                "serialCallback": 24,
                "intrCheck": 28,
            },
            "interrupt_flags": {"HBLANK": "0x0002", "VCOUNT": "0x0004", "SERIAL": "0x0080"},
            "origin_reference": index == 0,
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "src/main.c",
                "match_kind": "Thumb control flow, callback offsets, interrupt flags, literals, and call order",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-display-serial-interrupt-map.json")
        write_json(root / map_path, mapping)
        outputs.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "profile": profile,
            "functions": [
                {"name": item["name"], "address": item["address"], "code_sha256": item["rom_code_range"]["sha256"]}
                for item in functions
            ],
            "evidence": {"map": map_path.as_posix()},
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "functions": ["HBlankIntr", "VCountIntr", "SerialIntr"],
        "profile": profile,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/display-serial-interrupt-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)
    languages = ", ".join(dict.fromkeys(record["language"] for record in records))
    profile_note = {
        "rs": "VCount invokes the optional vcount callback.",
        "emerald": "VCount invokes the optional callback and then m4aSoundVSync.",
        "frlg": "VCount records REG_VCOUNT and invokes m4aSoundVSync without a vcount callback.",
    }[profile]
    research_path = Path("research/display-serial-interrupt-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} display and serial interrupt reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. All {len(records)} cataloged releases ({languages}) contain exactly one HBlank, VCount and Serial handler matching the `{profile}` structural profile. {profile_note}\n\n"
        "Each handler sets both the shared IWRAM interrupt check and gMain.intrCheck with HBlank 0x0002, VCount 0x0004 or Serial 0x0080. Per-release maps retain ranges, code hashes, validated literals and call targets without publishing ROM instruction bytes. "
        f"Naming and behavior are corroborated by `{reference_repository}` at `{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8", newline="\n",
    )
    outputs.append(research_path)
    test_path = Path("tests/test_display_serial_interrupts.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "game": game,
        "functions": summary["functions"],
        "profile": profile,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Decompilation",
            "tool": "tools/display_interrupt_catalog.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/display-serial-interrupt-reconstruction.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("analysis/global-release-catalog.json"))
    parser.add_argument("--game", required=True)
    parser.add_argument("--profile", choices=("rs", "emerald", "frlg"), required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.profile,
              args.reference_repository, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
