#!/usr/bin/env python3
"""Reconstruct interrupt initialization across Generation III release catalogs."""
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
DMA3 = 0x040000D4
DMA_CONTROL = 0x84000200
INTR_VECTOR = 0x03007FFC
REG_IME = 0x04000208
REG_IE = 0x04000200
REG_DISPSTAT = 0x04000004

RS_INIT = (
    0xB530, 0x4D14, 0x4C14, 0x4B15, 0x4A15, 0x210D, 0xCB01, 0xC201,
    0x3901, 0x2900, 0xDAFA, 0x4813, 0x6005, 0x6044, 0x4912, 0x6081,
    0x6880, 0x4812, 0x6004, 0x2000, None, None, 0x2000, None, None,
    0x2000, None, None, 0x480D, 0x2201, 0x8002, 0x490D, 0x800A, 0x4B0D,
    0x2008, 0x8018, 0x8808, 0x4310, 0x8008, 0xBC30, 0xBC01, 0x4700,
)
COMMON_INIT = (
    0xB530, 0x4D12, 0x4C12, 0x4B13, 0x4A13, 0x210D, 0xCB01, 0xC201,
    0x3901, 0x2900, 0xDAFA, 0x4811, 0x6005, 0x6044, 0x4910, 0x6081,
    0x6880, 0x4810, 0x6004, 0x2000, None, None, 0x2000, None, None,
    0x2000, None, None, 0x490B, 0x2001, 0x8008, 0x2001, None, None,
    0xBC30, 0xBC01, 0x4700,
)
SETTER_STORES = {
    "SetVBlankCallback": 0x60C8,
    "SetHBlankCallback": 0x6108,
    "SetVCountCallback": 0x6148,
    "SetSerialCallback": 0x6188,
}
SETTER_RELATIVE = {
    "rs": (124, 136, 148, 160),
    "frlg": (108, 120, 132, 144),
    "emerald": (108, 120, 132, 168),
}
RESTORE_RELATIVE = 144
RESTORE_CODE = (0x4802, 0x4903, 0x6041, 0x4903, 0x6081, 0x4770)


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


def init_template(profile: str) -> tuple[int | None, ...]:
    if profile == "rs":
        return RS_INIT
    if profile in {"emerald", "frlg"}:
        return COMMON_INIT
    raise ValueError(f"unsupported profile: {profile}")


def matching_init_offsets(data: bytes, profile: str) -> list[int]:
    template = init_template(profile)
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
            fixed_match = all(expected is None or actual == expected for actual, expected in zip(words, template))
            masked = [index for index, expected in enumerate(template) if expected is None]
            bl_match = all(is_bl(words[masked[index]], words[masked[index + 1]]) for index in range(0, len(masked), 2))
            if fixed_match and bl_match:
                result.append(offset)
        start = offset + 2
    return result


def unique_init_offset(data: bytes, profile: str) -> int:
    matches = matching_init_offsets(data, profile)
    if len(matches) != 1:
        raise ValueError(f"expected one InitIntrHandlers candidate, found {len(matches)}")
    return matches[0]


def validate_setter(data: bytes, offset: int, store: int, g_main: int, name: str) -> None:
    words = struct.unpack_from("<4H", data, offset)
    literal = struct.unpack_from("<I", data, offset + 8)[0]
    if words != (0x4901, store, 0x4770, 0x0000) or literal != g_main:
        raise ValueError(f"{name} setter validation failed")


def reconstructed_source(profile: str) -> str:
    if profile not in {"rs", "emerald", "frlg"}:
        raise ValueError(f"unsupported profile: {profile}")
    enable_decl = "" if profile == "rs" else "extern void EnableInterrupts(uint16_t flags);\n"
    emerald_decls = "extern void SerialIntr(void);\nextern void Timer3Intr(void);\n" if profile == "emerald" else ""
    direct_registers = """#define REG_DISPSTAT (*(volatile uint16_t *)0x04000004)
#define REG_IE (*(volatile uint16_t *)0x04000200)
""" if profile == "rs" else ""
    enable_body = """    REG_IE = INTR_FLAG_VBLANK;
    REG_DISPSTAT = DISPSTAT_VBLANK_INTR;
    REG_IE |= INTR_FLAG_VBLANK;
""" if profile == "rs" else "    EnableInterrupts(INTR_FLAG_VBLANK);\n"
    dispstat_enum = "    DISPSTAT_VBLANK_INTR = 8,\n" if profile == "rs" else ""
    restore = """
void RestoreSerialTimer3IntrHandlers(void)
{
    gIntrTable[1] = SerialIntr;
    gIntrTable[2] = Timer3Intr;
}

""" if profile == "emerald" else ""
    return f"""#include <stddef.h>
#include <stdint.h>

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
}};

struct DmaChannelRegisters
{{
    const void *source;
    void *destination;
    uint32_t control;
}};

extern struct MainInterruptState gMain;
extern IntrCallback gIntrTable[14];
extern const IntrCallback gIntrTableTemplate[14];
extern const uint8_t IntrMain[];
extern uint8_t IntrMain_Buffer[0x800];
{enable_decl}{emerald_decls}
#define DMA3 (*(volatile struct DmaChannelRegisters *)0x040000D4)
#define INTR_VECTOR (*(void (**)(void))0x03007FFC)
{direct_registers}#define REG_IME (*(volatile uint16_t *)0x04000208)

enum
{{
    DMA_ENABLE = 1u << 31,
    DMA_32BIT = 1u << 26,
{dispstat_enum}    INTR_FLAG_VBLANK = 1
}};

void SetVBlankCallback(IntrCallback callback);
void SetHBlankCallback(IntrCallback callback);
void SetVCountCallback(IntrCallback callback);
void SetSerialCallback(IntrCallback callback);

void InitIntrHandlers(void)
{{
    unsigned i;
    for (i = 0; i < 14; i++)
        gIntrTable[i] = gIntrTableTemplate[i];

    DMA3.source = IntrMain;
    DMA3.destination = IntrMain_Buffer;
    DMA3.control = DMA_ENABLE | DMA_32BIT | (sizeof(IntrMain_Buffer) / 4);
    INTR_VECTOR = (void (*)(void))IntrMain_Buffer;

    SetVBlankCallback(NULL);
    SetHBlankCallback(NULL);
    SetSerialCallback(NULL);

    REG_IME = 1;
{enable_body}}}

void SetVBlankCallback(IntrCallback callback)
{{
    gMain.vblankCallback = callback;
}}

void SetHBlankCallback(IntrCallback callback)
{{
    gMain.hblankCallback = callback;
}}

void SetVCountCallback(IntrCallback callback)
{{
    gMain.vcountCallback = callback;
}}

{restore}void SetSerialCallback(IntrCallback callback)
{{
    gMain.serialCallback = callback;
}}
"""


def init_literals(data: bytes, offset: int, profile: str) -> dict[str, int]:
    if profile == "rs":
        names = ("IntrMain", "IntrMain_Buffer", "gIntrTableTemplate", "gIntrTable", "DMA3", "DMA_CONTROL", "INTR_VECTOR", "REG_IME", "REG_IE", "REG_DISPSTAT")
        values = struct.unpack_from("<10I", data, offset + 84)
        fixed = {"DMA3": DMA3, "DMA_CONTROL": DMA_CONTROL, "INTR_VECTOR": INTR_VECTOR, "REG_IME": REG_IME, "REG_IE": REG_IE, "REG_DISPSTAT": REG_DISPSTAT}
    else:
        names = ("IntrMain", "IntrMain_Buffer", "gIntrTableTemplate", "gIntrTable", "DMA3", "DMA_CONTROL", "INTR_VECTOR", "REG_IME")
        values = struct.unpack_from("<8I", data, offset + 76)
        fixed = {"DMA3": DMA3, "DMA_CONTROL": DMA_CONTROL, "INTR_VECTOR": INTR_VECTOR, "REG_IME": REG_IME}
    result = dict(zip(names, values))
    if any(result[key] != value for key, value in fixed.items()):
        raise ValueError("fixed interrupt literal validation failed")
    if not all(ROM_BASE <= result[key] < 0x0A000000 for key in ("IntrMain", "gIntrTableTemplate")):
        raise ValueError("ROM pointer literal leaves GBA ROM")
    if not all(0x03000000 <= result[key] <= 0x03007FFF for key in ("gIntrTable", "IntrMain_Buffer")):
        raise ValueError("interrupt work buffer leaves IWRAM")
    return result


def code_record(data: bytes, offset: int, length: int, name: str, call_names: tuple[str, ...] = ()) -> dict[str, object]:
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
            "start_offset": offset, "end_offset_exclusive": offset + length,
            "length": length, "sha256": digest(data[offset:offset + length]),
            "raw_bytes_published": False,
        },
        "calls": calls,
        "control_flow": {
            "instruction_halfwords": cfg["instruction_halfwords"],
            "return_count": len(cfg["returns"]), "call_count": len(cfg["calls"]),
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
    source_path = Path("src/interrupt_init.c")
    (root / source_path).write_text(reconstructed_source(profile), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    outputs: list[Path] = [source_path, catalog_path]
    records = []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        init_offset = unique_init_offset(data, profile)
        values = init_literals(data, init_offset, profile)
        setter_names = tuple(SETTER_STORES)
        setter_offsets = dict(zip(setter_names, (init_offset + delta for delta in SETTER_RELATIVE[profile])))
        setter_g_main = struct.unpack_from("<I", data, setter_offsets["SetVBlankCallback"] + 8)[0]
        if not 0x03000000 <= setter_g_main <= 0x03007FFF:
            raise ValueError("gMain setter literal leaves IWRAM")
        for name in setter_names:
            validate_setter(data, setter_offsets[name], SETTER_STORES[name], setter_g_main, name)
        init_length = len(init_template(profile)) * 2
        init_call_names = (
            ("SetVBlankCallback", "SetHBlankCallback", "SetSerialCallback")
            if profile == "rs" else
            ("SetVBlankCallback", "SetHBlankCallback", "SetSerialCallback", "EnableInterrupts")
        )
        functions = [code_record(data, init_offset, init_length, "InitIntrHandlers", init_call_names)]
        functions.extend(code_record(data, setter_offsets[name], 6, name) for name in setter_names[:3])
        restore_literals = None
        if profile == "emerald":
            restore_offset = init_offset + RESTORE_RELATIVE
            if struct.unpack_from("<6H", data, restore_offset) != RESTORE_CODE:
                raise ValueError("RestoreSerialTimer3IntrHandlers code validation failed")
            restore_values = struct.unpack_from("<3I", data, restore_offset + 12)
            if restore_values[0] != values["gIntrTable"]:
                raise ValueError("restore function gIntrTable differs from InitIntrHandlers")
            restore_literals = {"gIntrTable": restore_values[0], "SerialIntr": restore_values[1], "Timer3Intr": restore_values[2]}
            functions.append(code_record(data, restore_offset, 12, "RestoreSerialTimer3IntrHandlers"))
        functions.append(code_record(data, setter_offsets["SetSerialCallback"], 6, "SetSerialCallback"))
        literal_addresses = {key: f"0x{value:08X}" for key, value in values.items() if key != "DMA_CONTROL"}
        literal_addresses["gMain"] = f"0x{setter_g_main:08X}"
        if restore_literals:
            literal_addresses.update({key: f"0x{value:08X}" for key, value in restore_literals.items() if key != "gIntrTable"})
        mapping = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "profile": profile,
            "source": source_path.as_posix(), "source_sha256": source_sha256,
            "functions": functions,
            "dma": {"channel": 3, "byte_count": 2048, "control": "0x84000200"},
            "literal_addresses": literal_addresses,
            "proven_offsets": {"vblankCallback": 12, "hblankCallback": 16, "vcountCallback": 20, "serialCallback": 24},
            "vblank_enable": "direct IE and DISPSTAT writes" if profile == "rs" else "EnableInterrupts call",
            "serial_timer3_restore": profile == "emerald",
            "origin_reference": index == 0,
            "naming_basis": {
                "repository": reference_repository, "commit": reference_commit, "path": "src/main.c",
                "match_kind": "Thumb control flow, loop count, DMA constants, literals, calls, and callback stores",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-interrupt-init-map.json")
        write_json(root / map_path, mapping)
        outputs.append(map_path)
        records.append({
            "id": release_id, "language": release["language"], "revision": release["revision"],
            "build_kind": release["build_kind"], "sha256": sha256,
            "origin_reference": index == 0, "profile": profile,
            "functions": [{"name": item["name"], "address": item["address"], "code_sha256": item["rom_code_range"]["sha256"]} for item in functions],
            "evidence": {"map": map_path.as_posix()},
        })

    summary = {
        "schema_version": 1, "game": game, "profile": profile,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "source": source_path.as_posix(), "releases": records, "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/interrupt-init-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)
    languages = ", ".join(dict.fromkeys(record["language"] for record in records))
    difference = {
        "rs": "VBlank is enabled with direct IE and DISPSTAT writes.",
        "frlg": "VBlank is enabled through EnableInterrupts.",
        "emerald": "VBlank is enabled through EnableInterrupts and a separate function restores Serial and Timer3 handlers.",
    }[profile]
    research_path = Path("research/interrupt-init-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} interrupt initialization reconstruction\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. All {len(records)} cataloged releases ({languages}) contain exactly one InitIntrHandlers structure and its callback setters matching the `{profile}` profile. {difference}\n\n"
        "The implementation copies 14 table entries, DMA-copies the 0x800-byte interrupt dispatcher with DMA3 control 0x84000200, installs the IWRAM vector, clears callbacks and enables VBlank. Per-release maps retain code ranges, hashes, validated literals and call targets without ROM instruction bytes. "
        f"Naming and behavior are corroborated by `{reference_repository}` at `{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8", newline="\n",
    )
    outputs.append(research_path)
    test_path = Path("tests/test_interrupt_init_reconstruction.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1, "game": game, "profile": profile,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Decompilation", "tool": "tools/interrupt_init_catalog.py", "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/interrupt-init-reconstruction.json", manifest)
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
        build(args.root, args.rom_dir, args.catalog, args.game, args.profile, args.reference_repository, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
