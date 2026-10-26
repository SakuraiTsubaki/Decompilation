#!/usr/bin/env python3
"""Reconstruct InitKeys and ReadKeys across Generation III release catalogs."""
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
REG_KEYINPUT = 0x04000130
KEYS_MASK = 0x000003FF
INIT_TEMPLATE = (
    0x4906, 0x2005, 0x8008, 0x4906, 0x2028, 0x8008, 0x4905,
    0x2000, 0x8588, 0x85C8, 0x8608, 0x8508, 0x8548, 0x4770,
)
READ_PREFIX = (
    0xB500, 0x480E, 0x8801, 0x4A0E, 0x1C10, 0x1C03, 0x404B, 0x490D,
    0x8D0A, 0x1C18, 0x4390, 0x8548, 0x85C8, 0x8608, 0x1C0A, 0x2B00,
    0xD014, 0x8D90, 0x4298, 0xD111, 0x8E50, 0x3801, 0x8650, 0x0400,
    0x2800, 0xD10E, 0x8613, 0x4804, 0xE009, 0x0000, 0x0130, 0x0400,
    0x03FF, 0x0000, None, None, None, None,
)
READ_DIRECT_SUFFIX = (
    0x4811, 0x8800, 0x8650, 0x8513, 0x8593, 0x4810, 0x7CC0, 0x2802,
    0xD111, 0x8DD1, 0x2380, 0x009B, 0x1C18, 0x4008, 0x2800, 0xD002,
    0x2001, 0x4308, 0x85D0, 0x8D91, 0x1C18, 0x4008, 0x2800, 0xD002,
    0x2001, 0x4308, 0x8590, 0x8DD1, 0x8ED0, 0x4008, 0x2800, 0xD001,
    0x2001, 0x8690, 0xBC01, 0x4700,
)
READ_POINTER_SUFFIX = (
    0x4812, 0x8800, 0x8650, 0x8513, 0x8593, 0x4811, 0x6800, 0x7CC0,
    0x2802, 0xD111, 0x8DD1, 0x2380, 0x009B, 0x1C18, 0x4008, 0x2800,
    0xD002, 0x2001, 0x4308, 0x85D0, 0x8D91, 0x1C18, 0x4008, 0x2800,
    0xD002, 0x2001, 0x4308, 0x8590, 0x8DD1, 0x8ED0, 0x4008, 0x2800,
    0xD001, 0x2001, 0x8690, 0xBC01, 0x4700,
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


def read_template(profile: str) -> tuple[int | None, ...]:
    if profile == "direct":
        return READ_PREFIX + READ_DIRECT_SUFFIX
    if profile == "pointer":
        return READ_PREFIX + READ_POINTER_SUFFIX
    raise ValueError(f"unsupported profile: {profile}")


def matching_offsets(data: bytes, template: tuple[int | None, ...]) -> list[int]:
    size = len(template) * 2
    prefix = struct.pack("<H", template[0])
    result = []
    start = 0
    while True:
        offset = data.find(prefix, start)
        if offset < 0:
            break
        if offset % 2 == 0 and offset + size <= len(data):
            words = struct.unpack_from(f"<{len(template)}H", data, offset)
            if all(expected is None or actual == expected for actual, expected in zip(words, template)):
                result.append(offset)
        start = offset + 2
    return result


def unique_offset(data: bytes, template: tuple[int | None, ...], name: str) -> int:
    matches = matching_offsets(data, template)
    if len(matches) != 1:
        raise ValueError(f"expected one {name} candidate, found {len(matches)}")
    return matches[0]


def reconstructed_source(profile: str) -> str:
    if profile not in {"direct", "pointer"}:
        raise ValueError(f"unsupported profile: {profile}")
    save_decl = (
        "extern struct SaveBlock2InputOptions gSaveBlock2;"
        if profile == "direct" else
        "extern struct SaveBlock2InputOptions *gSaveBlock2Ptr;"
    )
    option = "gSaveBlock2.optionsButtonMode" if profile == "direct" else "gSaveBlock2Ptr->optionsButtonMode"
    return f"""#include <stdint.h>

typedef uint8_t bool8;
typedef void (*MainCallback)(void);

struct MainInputState
{{
    MainCallback callback1;
    MainCallback callback2;
    uint8_t unknown_008[0x20];
    uint16_t heldKeysRaw;
    uint16_t newKeysRaw;
    uint16_t heldKeys;
    uint16_t newKeys;
    uint16_t newAndRepeatedKeys;
    uint16_t keyRepeatCounter;
    bool8 watchedKeysPressed;
    uint8_t unknown_035;
    uint16_t watchedKeysMask;
}};

struct SaveBlock2InputOptions
{{
    uint8_t unknown_000[0x13];
    uint8_t optionsButtonMode;
}};

extern struct MainInputState gMain;
{save_decl}
extern uint16_t gKeyRepeatContinueDelay;
extern uint16_t gKeyRepeatStartDelay;

#define REG_KEYINPUT (*(volatile uint16_t *)0x04000130)

enum
{{
    A_BUTTON = 1,
    L_BUTTON = 1 << 9,
    KEYS_MASK = 0x03FF,
    OPTIONS_BUTTON_MODE_L_EQUALS_A = 2
}};

void InitKeys(void)
{{
    gKeyRepeatContinueDelay = 5;
    gKeyRepeatStartDelay = 40;
    gMain.heldKeys = 0;
    gMain.newKeys = 0;
    gMain.newAndRepeatedKeys = 0;
    gMain.heldKeysRaw = 0;
    gMain.newKeysRaw = 0;
}}

void ReadKeys(void)
{{
    uint16_t keyInput = REG_KEYINPUT ^ KEYS_MASK;
    gMain.newKeysRaw = keyInput & ~gMain.heldKeysRaw;
    gMain.newKeys = gMain.newKeysRaw;
    gMain.newAndRepeatedKeys = gMain.newKeysRaw;

    if (keyInput != 0 && gMain.heldKeys == keyInput)
    {{
        gMain.keyRepeatCounter--;
        if (gMain.keyRepeatCounter == 0)
        {{
            gMain.newAndRepeatedKeys = keyInput;
            gMain.keyRepeatCounter = gKeyRepeatContinueDelay;
        }}
    }}
    else
    {{
        gMain.keyRepeatCounter = gKeyRepeatStartDelay;
    }}

    gMain.heldKeysRaw = keyInput;
    gMain.heldKeys = gMain.heldKeysRaw;

    if ({option} == OPTIONS_BUTTON_MODE_L_EQUALS_A)
    {{
        if (gMain.newKeys & L_BUTTON)
            gMain.newKeys |= A_BUTTON;
        if (gMain.heldKeys & L_BUTTON)
            gMain.heldKeys |= A_BUTTON;
    }}

    if (gMain.newKeys & gMain.watchedKeysMask)
        gMain.watchedKeysPressed = 1;
}}
"""


def literals(data: bytes, init_offset: int, read_offset: int, profile: str) -> dict[str, str]:
    repeat_continue, repeat_start, g_main = struct.unpack_from("<3I", data, init_offset + 28)
    reg_keyinput, keys_mask, read_g_main, read_repeat_continue = struct.unpack_from("<4I", data, read_offset + 60)
    save_offset = read_offset + (152 if profile == "direct" else 156)
    save_options = struct.unpack_from("<I", data, save_offset)[0]
    if reg_keyinput != REG_KEYINPUT or keys_mask != KEYS_MASK:
        raise ValueError("key register or mask literal mismatch")
    if read_g_main != g_main or read_repeat_continue != repeat_continue:
        raise ValueError("InitKeys and ReadKeys globals disagree")
    iwram = [g_main, repeat_continue, repeat_start] + ([save_options] if profile == "pointer" else [])
    if any(not 0x03000000 <= value <= 0x03007FFF for value in iwram):
        raise ValueError("IWRAM input-state literal leaves IWRAM")
    if profile == "direct" and not 0x02000000 <= save_options <= 0x0203FFFF:
        raise ValueError("direct SaveBlock2 literal leaves EWRAM")
    values = {
        "REG_KEYINPUT": reg_keyinput,
        "KEYS_MASK": keys_mask,
        "gMain": g_main,
        "gKeyRepeatContinueDelay": repeat_continue,
        "gKeyRepeatStartDelay": repeat_start,
        ("gSaveBlock2" if profile == "direct" else "gSaveBlock2Ptr"): save_options,
    }
    return {key: f"0x{value:08X}" for key, value in values.items()}


def function_record(data: bytes, offset: int, length: int, name: str) -> dict[str, object]:
    cfg = thumb_cfg.omit_raw_halfwords(thumb_cfg.trace_thumb_function(data, offset, max_span=length))
    expected_end = ROM_BASE + offset + length
    if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or cfg["calls"]:
        raise ValueError(f"CFG boundary mismatch for {name}")
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
        "control_flow": {
            "instruction_halfwords": cfg["instruction_halfwords"],
            "return_count": len(cfg["returns"]),
            "call_count": 0,
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
    read_pattern = read_template(profile)
    source_path = Path("src/key_input.c")
    (root / source_path).write_text(reconstructed_source(profile), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    outputs: list[Path] = [source_path, catalog_path]
    records = []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        init_offset = unique_offset(data, INIT_TEMPLATE, "InitKeys")
        read_offset = unique_offset(data, read_pattern, "ReadKeys")
        if read_offset != init_offset + 40:
            raise ValueError(f"unexpected InitKeys/ReadKeys spacing: {release_id}")
        functions = [
            function_record(data, init_offset, 28, "InitKeys"),
            function_record(data, read_offset, len(read_pattern) * 2, "ReadKeys"),
        ]
        literal_addresses = literals(data, init_offset, read_offset, profile)
        mapping = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "profile": profile,
            "source": source_path.as_posix(),
            "source_sha256": source_sha256,
            "functions": functions,
            "literal_addresses": literal_addresses,
            "proven_offsets": {
                "heldKeysRaw": 40, "newKeysRaw": 42, "heldKeys": 44, "newKeys": 46,
                "newAndRepeatedKeys": 48, "keyRepeatCounter": 50,
                "watchedKeysPressed": 52, "watchedKeysMask": 54, "optionsButtonMode": 19,
            },
            "constants": {
                "repeat_continue_delay": 5, "repeat_start_delay": 40,
                "l_button": 512, "a_button": 1, "l_equals_a_mode": 2,
            },
            "save_options_access": "direct" if profile == "direct" else "pointer_indirect",
            "origin_reference": index == 0,
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "src/main.c",
                "match_kind": "Thumb control flow, constants, literals, state offsets, and save-option access",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-key-input-map.json")
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
        "functions": ["InitKeys", "ReadKeys"],
        "profile": profile,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/key-input-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)
    languages = ", ".join(dict.fromkeys(record["language"] for record in records))
    access_note = "a direct SaveBlock2 object" if profile == "direct" else "the gSaveBlock2Ptr indirection"
    research_path = Path("research/key-input-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} key input reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. All {len(records)} cataloged releases ({languages}) contain exactly one InitKeys and ReadKeys pair matching the `{profile}` profile. Options are read through {access_note}.\n\n"
        "The pair establishes repeat delays 5 and 40, derives active-high keys from REG_KEYINPUT with mask 0x03FF, implements repeat behavior, applies L-equals-A mode, and records watched-key presses. Per-release maps retain ranges, hashes, validated literals and control-flow counts without ROM instruction bytes. "
        f"Naming and behavior are corroborated by `{reference_repository}` at `{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8", newline="\n",
    )
    outputs.append(research_path)
    test_path = Path("tests/test_key_input_reconstruction.py")
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
            "tool": "tools/key_input_catalog.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/key-input-reconstruction.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("analysis/global-release-catalog.json"))
    parser.add_argument("--game", required=True)
    parser.add_argument("--profile", choices=("direct", "pointer"), required=True)
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
