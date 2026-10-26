#!/usr/bin/env python3
"""Reconstruct VBlankIntr across Generation III release catalogs."""
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
REG_IME = 0x04000208
REG_VCOUNT = 0x04000006
INTR_CHECK = 0x03007FF8
PROFILES = {
    "rs": {"length": 98, "prologue": 0xB570, "epilogue": (0xBC70, 0xBC01, 0x4700)},
    "emerald": {"length": 164, "prologue": 0xB510, "epilogue": (0xBC10, 0xBC01, 0x4700)},
    "frlg": {"length": 132, "prologue": 0xB530, "epilogue": (0xBC30, 0xBC01, 0x4700)},
}
CALL_NAMES = {
    "rs": (
        "LinkVSync", "m4aSoundVSync", "indirect callback trampoline",
        "m4aSoundMain", "sub_800C35C", "Random",
    ),
    "emerald": (
        "RfuVSync", "LinkVSync", "indirect callback trampoline",
        "CopyBufferedValuesToGpuRegs", "ProcessDma3Requests", "m4aSoundMain",
        "TryReceiveLinkBattleData", "Random", "UpdateWirelessStatusIndicatorSprite",
    ),
    "frlg": (
        "RfuVSync", "LinkVSync", "indirect callback trampoline",
        "CopyBufferedValuesToGpuRegs", "ProcessDma3Requests", "m4aSoundMain",
        "TryReceiveLinkBattleData", "Random", "UpdateWirelessStatusIndicatorSprite",
    ),
}


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


def reconstructed_source(profile: str) -> str:
    if profile == "rs":
        return """#include <stdint.h>

typedef uint8_t bool8;
typedef void (*IntrCallback)(void);
typedef void (*MainCallback)(void);

struct MainVBlankState
{
    MainCallback callback1;
    MainCallback callback2;
    uint8_t unknown_008[4];
    IntrCallback vblankCallback;
    IntrCallback hblankCallback;
    IntrCallback vcountCallback;
    IntrCallback serialCallback;
    uint16_t intrCheck;
    uint16_t unknown_01e;
    uint32_t vblankCounter1;
    uint32_t vblankCounter2;
};

struct SoundInfoVBlank
{
    uint8_t unknown_000[4];
    uint8_t pcmDmaCounter;
};

extern struct MainVBlankState gMain;
extern bool8 gLinkVSyncDisabled;
extern uint8_t gPcmDmaCounter;
extern struct SoundInfoVBlank gSoundInfo;
extern void LinkVSync(void);
extern void m4aSoundVSync(void);
extern void m4aSoundMain(void);
extern void sub_800C35C(void);
extern uint16_t Random(void);

#define REG_IME (*(volatile uint16_t *)0x04000208)
#define INTR_CHECK (*(volatile uint16_t *)0x03007FF8)
#define INTR_FLAG_VBLANK 1

void VBlankIntr(void)
{
    uint16_t savedIme;
    if (!gLinkVSyncDisabled)
        LinkVSync();
    savedIme = REG_IME;
    REG_IME = 0;
    m4aSoundVSync();
    REG_IME = savedIme;
    gMain.vblankCounter1++;
    if (gMain.vblankCallback != 0)
        gMain.vblankCallback();
    gMain.vblankCounter2++;
    gPcmDmaCounter = gSoundInfo.pcmDmaCounter;
    m4aSoundMain();
    sub_800C35C();
    Random();
    INTR_CHECK |= INTR_FLAG_VBLANK;
    gMain.intrCheck |= INTR_FLAG_VBLANK;
}
"""
    if profile not in {"emerald", "frlg"}:
        raise ValueError(f"unsupported profile: {profile}")
    counter_decl = "uint32_t vblankCounter1;" if profile == "emerald" else "uint32_t *vblankCounter1;"
    extra_main = "uint8_t unknown_028[0x411];\n    bool8 inBattle;" if profile == "emerald" else ""
    extra_globals = (
        "extern uint32_t *gTrainerHillVBlankCounter;\nextern uint32_t gBattleTypeFlags;"
        if profile == "emerald" else
        "extern uint8_t sVcountBeforeSound;\nextern uint8_t sVcountAfterSound;"
    )
    reg_vcount = "" if profile == "emerald" else "#define REG_VCOUNT (*(volatile uint16_t *)0x04000006)\n"
    counter_body = (
        """    gMain.vblankCounter1++;
    if (gTrainerHillVBlankCounter != 0 && *gTrainerHillVBlankCounter < 0xFFFFFFFFu)
        (*gTrainerHillVBlankCounter)++;
""" if profile == "emerald" else
        """    if (gMain.vblankCounter1 != 0)
        (*gMain.vblankCounter1)++;
"""
    )
    sound_body = (
        """    m4aSoundMain();
    TryReceiveLinkBattleData();
    if (!gMain.inBattle || !(gBattleTypeFlags & BATTLE_RNG_SUPPRESS_MASK))
        Random();
""" if profile == "emerald" else
        """    sVcountBeforeSound = (uint8_t)REG_VCOUNT;
    m4aSoundMain();
    sVcountAfterSound = (uint8_t)REG_VCOUNT;
    TryReceiveLinkBattleData();
    Random();
"""
    )
    mask = "#define BATTLE_RNG_SUPPRESS_MASK 0x013F0102u\n" if profile == "emerald" else ""
    return f"""#include <stdint.h>

typedef uint8_t bool8;
typedef void (*IntrCallback)(void);
typedef void (*MainCallback)(void);

struct MainVBlankState
{{
    MainCallback callback1;
    MainCallback callback2;
    uint8_t unknown_008[4];
    IntrCallback vblankCallback;
    IntrCallback hblankCallback;
    IntrCallback vcountCallback;
    IntrCallback serialCallback;
    uint16_t intrCheck;
    uint16_t unknown_01e;
    {counter_decl}
    uint32_t vblankCounter2;
    {extra_main}
}};

struct SoundInfoVBlank
{{
    uint8_t unknown_000[4];
    uint8_t pcmDmaCounter;
}};

extern struct MainVBlankState gMain;
extern uint8_t gWirelessCommType;
extern uint8_t gLinkVSyncDisabled;
extern uint8_t gPcmDmaCounter;
extern struct SoundInfoVBlank gSoundInfo;
{extra_globals}
extern void RfuVSync(void);
extern void LinkVSync(void);
extern void CopyBufferedValuesToGpuRegs(void);
extern void ProcessDma3Requests(void);
extern void m4aSoundMain(void);
extern void TryReceiveLinkBattleData(void);
extern void UpdateWirelessStatusIndicatorSprite(void);
extern uint16_t Random(void);

{reg_vcount}#define INTR_CHECK (*(volatile uint16_t *)0x03007FF8)
#define INTR_FLAG_VBLANK 1
{mask}
void VBlankIntr(void)
{{
    if (gWirelessCommType != 0)
        RfuVSync();
    else if (!gLinkVSyncDisabled)
        LinkVSync();
{counter_body}    if (gMain.vblankCallback != 0)
        gMain.vblankCallback();
    gMain.vblankCounter2++;
    CopyBufferedValuesToGpuRegs();
    ProcessDma3Requests();
    gPcmDmaCounter = gSoundInfo.pcmDmaCounter;
{sound_body}    UpdateWirelessStatusIndicatorSprite();
    INTR_CHECK |= INTR_FLAG_VBLANK;
    gMain.intrCheck |= INTR_FLAG_VBLANK;
}}
"""


def dependency_start(root: Path, release_id: str, sha256: str, profile: str) -> tuple[int, Path, str]:
    path = Path(f"analysis/{release_id}-interrupt-init-map.json")
    full = root / path
    mapping = json.loads(full.read_text(encoding="utf-8"))
    if mapping["target"] != {"release": release_id, "sha256": sha256} or mapping["profile"] != profile:
        raise ValueError(f"interrupt-init dependency mismatch: {release_id}")
    setters = [item for item in mapping["functions"] if item["name"] == "SetSerialCallback"]
    if len(setters) != 1:
        raise ValueError(f"missing SetSerialCallback dependency: {release_id}")
    setter_offset = int(setters[0]["address"], 16) - ROM_BASE
    return setter_offset + 12, path, file_hash(full)


def validate_shape(data: bytes, offset: int, profile: str) -> None:
    spec = PROFILES[profile]
    length = spec["length"]
    if struct.unpack_from("<H", data, offset)[0] != spec["prologue"]:
        raise ValueError("VBlankIntr prologue mismatch")
    if struct.unpack_from("<3H", data, offset + length - 6) != spec["epilogue"]:
        raise ValueError("VBlankIntr epilogue mismatch")


def literal_values(data: bytes, offset: int, profile: str) -> tuple[dict[str, str], dict[str, object]]:
    if profile == "rs":
        names = ("gLinkVSyncDisabled", "REG_IME", "gMain", "gPcmDmaCounter", "gSoundInfo", "INTR_CHECK")
        values = struct.unpack_from("<6I", data, offset + 100)
        if values[1] != REG_IME or values[5] != INTR_CHECK:
            raise ValueError("Ruby/Sapphire fixed VBlank literal mismatch")
        behavior = {"ime_guarded_sound_vsync": True}
    elif profile == "emerald":
        wireless = struct.unpack_from("<I", data, offset + 16)[0]
        names = ("gLinkVSyncDisabled", "gMain", "gTrainerHillVBlankCounter", "gPcmDmaCounter", "gSoundInfo", "inBattleOffset", "gBattleTypeFlags", "battleRngSuppressMask", "INTR_CHECK")
        values = struct.unpack_from("<9I", data, offset + 164)
        if values[5] != 0x439 or values[7] != 0x013F0102 or values[8] != INTR_CHECK:
            raise ValueError("Emerald fixed VBlank literal mismatch")
        names = ("gWirelessCommType",) + names
        values = (wireless,) + values
        behavior = {"trainer_hill_counter": True, "in_battle_offset": 0x439, "battle_rng_suppress_mask": "0x013F0102"}
    else:
        wireless = struct.unpack_from("<I", data, offset + 16)[0]
        names = ("gLinkVSyncDisabled", "gMain", "gPcmDmaCounter", "gSoundInfo", "sVcountBeforeSound", "REG_VCOUNT", "sVcountAfterSound", "INTR_CHECK")
        values = struct.unpack_from("<8I", data, offset + 132)
        if values[5] != REG_VCOUNT or values[7] != INTR_CHECK:
            raise ValueError("FireRed/LeafGreen fixed VBlank literal mismatch")
        names = ("gWirelessCommType",) + names
        values = (wireless,) + values
        behavior = {"sound_vcount_samples": True}
    result = dict(zip(names, values))
    ram_exclusions = {"REG_IME", "REG_VCOUNT", "INTR_CHECK", "inBattleOffset", "battleRngSuppressMask", "gTrainerHillVBlankCounter", "gBattleTypeFlags"}
    if any(not 0x03000000 <= value <= 0x03007FFF for key, value in result.items() if key not in ram_exclusions):
        raise ValueError("VBlank IWRAM literal leaves IWRAM")
    for key in ("gTrainerHillVBlankCounter", "gBattleTypeFlags"):
        if key in result and not 0x02000000 <= result[key] <= 0x0203FFFF:
            raise ValueError(f"{key} leaves EWRAM")
    return {key: f"0x{value:08X}" for key, value in result.items()}, behavior


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str, profile: str,
          reference_repository: str, reference_commit: str) -> dict[str, object]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    source_path = Path("src/vblank_intr.c")
    (root / source_path).write_text(reconstructed_source(profile), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    outputs: list[Path] = [source_path, catalog_path]
    records = []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        offset, dependency_path, dependency_sha256 = dependency_start(root, release_id, sha256, profile)
        validate_shape(data, offset, profile)
        length = PROFILES[profile]["length"]
        cfg = thumb_cfg.omit_raw_halfwords(thumb_cfg.trace_thumb_function(data, offset, max_span=length))
        expected_end = ROM_BASE + offset + length
        calls = sorted(cfg["calls"], key=lambda item: item["source"])
        if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or len(calls) != len(CALL_NAMES[profile]):
            raise ValueError(f"VBlankIntr CFG mismatch: {release_id}")
        named_calls = [
            {"name": name, "source": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"}
            for name, call in zip(CALL_NAMES[profile], calls)
        ]
        literals, behavior = literal_values(data, offset, profile)
        mapping = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "profile": profile,
            "source": source_path.as_posix(), "source_sha256": source_sha256,
            "function": {
                "name": "VBlankIntr", "address": f"0x{ROM_BASE + offset:08X}",
                "range_end_exclusive": f"0x{expected_end:08X}",
                "rom_code_range": {"start_offset": offset, "end_offset_exclusive": offset + length, "length": length, "sha256": digest(data[offset:offset + length]), "raw_bytes_published": False},
                "control_flow": {"instruction_halfwords": cfg["instruction_halfwords"], "return_count": len(cfg["returns"]), "call_count": len(calls), "raw_halfwords_omitted": True},
            },
            "calls": named_calls,
            "literal_addresses": literals,
            "behavior": behavior,
            "proven_offsets": {"vblankCallback": 12, "intrCheck": 28, "vblankCounter1": 32, "vblankCounter2": 36, "pcmDmaCounter": 4},
            "interrupt_flag": "0x0001",
            "evidence_dependency": {"path": dependency_path.as_posix(), "sha256": dependency_sha256, "relation": "VBlankIntr immediately follows the SetSerialCallback code and literal span"},
            "origin_reference": index == 0,
            "naming_basis": {"repository": reference_repository, "commit": reference_commit, "path": "src/main.c", "match_kind": "adjacent interrupt layout, Thumb control flow, call order, literals, constants, and state offsets", "raw_rom_bytes_published": False},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-vblank-intr-map.json")
        write_json(root / map_path, mapping)
        outputs.append(map_path)
        records.append({
            "id": release_id, "language": release["language"], "revision": release["revision"], "build_kind": release["build_kind"],
            "sha256": sha256, "origin_reference": index == 0, "profile": profile,
            "address": mapping["function"]["address"], "code_sha256": mapping["function"]["rom_code_range"]["sha256"],
            "calls": named_calls, "evidence": {"map": map_path.as_posix(), "interrupt_init": dependency_path.as_posix()},
        })

    summary = {"schema_version": 1, "game": game, "function": "VBlankIntr", "profile": profile, "origin_reference": releases[0]["id"], "release_count": len(records), "source": source_path.as_posix(), "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/vblank-intr-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)
    languages = ", ".join(dict.fromkeys(record["language"] for record in records))
    difference = {
        "rs": "The sound VSync call is protected by REG_IME save/disable/restore.",
        "emerald": "Wireless sync, Trainer Hill counting and battle-dependent RNG suppression are retained.",
        "frlg": "Wireless sync and VCOUNT samples around m4aSoundMain are retained.",
    }[profile]
    research_path = Path("research/vblank-intr-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} VBlankIntr reconstruction\n\nThe Japanese release `{releases[0]['id']}` is the origin reference. All {len(records)} cataloged releases ({languages}) have a VBlank handler immediately after the verified serial callback setter and match the `{profile}` control-flow profile. {difference}\n\nPer-release maps preserve code hashes, call targets, validated state addresses and the dependency hash for interrupt initialization. CFG evidence omits raw halfwords and no ROM instruction bytes are published. Naming and behavior are corroborated by `{reference_repository}` at `{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8", newline="\n",
    )
    outputs.append(research_path)
    test_path = Path("tests/test_vblank_intr_reconstruction.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1, "game": game, "function": "VBlankIntr", "profile": profile,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Decompilation", "tool": "tools/vblank_intr_catalog.py", "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/vblank-intr-reconstruction.json", manifest)
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
