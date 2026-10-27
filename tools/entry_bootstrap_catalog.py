#!/usr/bin/env python3
"""Build publication-safe GBA entry, bootstrap and Thumb-entry catalogs."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gba_bootstrap
import gba_entrypoint
import thumb_cfg


ROM_BASE = 0x08000000


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


def edge_kinds(edges: list[dict]) -> dict[str, int]:
    return dict(sorted({
        kind: sum(1 for edge in edges if edge["kind"] == kind)
        for kind in {edge["kind"] for edge in edges}
    }.items()))


def semantic_entry_source() -> str:
    return """.syntax unified
.arm
.section .text.rom_entry, "ax", %progbits
.global RomEntry
.type RomEntry, %function
RomEntry:
    b ArmBootstrap
.size RomEntry, . - RomEntry
"""


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str) -> dict:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    source_path = Path("src/rom_entry.s")
    (root / source_path).write_text(
        semantic_entry_source(), encoding="utf-8", newline="\n"
    )
    source_sha = file_hash(root / source_path)
    entry_maps, bootstrap_maps, cfg_maps, records = [], [], [], []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        if len(data) < 4:
            raise ValueError(f"ROM is shorter than entry word: {release_id}")
        entry = gba_entrypoint.decode_entry_word(struct.unpack_from("<I", data)[0])
        bootstrap_offset = entry["target_address"] - ROM_BASE
        bootstrap = gba_bootstrap.trace_bootstrap(data, bootstrap_offset)
        transition = bootstrap["transition"]
        if transition["target_state"] != "thumb":
            raise ValueError(f"bootstrap does not enter Thumb state: {release_id}")
        thumb_offset = transition["target_address"] - ROM_BASE
        cfg = thumb_cfg.trace_thumb_function(data, thumb_offset, max_span=0x800)

        agb_path = Path(f"analysis/{release_id}-agb-main-map.json")
        agb = json.loads((root / agb_path).read_text(encoding="utf-8"))
        if int(agb["function"]["address"], 16) != transition["target_address"]:
            raise ValueError(f"bootstrap target differs from AgbMain: {release_id}")
        if int(agb["function"]["range_end_exclusive"], 16) != cfg["range_end"]:
            raise ValueError(f"Thumb CFG end differs from AgbMain: {release_id}")
        if len(agb["direct_calls"]) != len(cfg["calls"]):
            raise ValueError(f"Thumb CFG call count differs from AgbMain: {release_id}")
        if cfg["return_observed"]:
            raise ValueError(f"Thumb entry unexpectedly returns: {release_id}")
        loop = agb["function"]["loop_back_edge"]
        expected_loop = {
            "source": int(loop["source"], 16),
            "target": int(loop["target"], 16),
            "kind": "branch",
        }
        if expected_loop not in cfg["edges"]:
            raise ValueError(f"AgbMain loop edge is absent from CFG: {release_id}")

        common = {
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "raw_rom_bytes_included": False,
        }
        entry_map = {
            "schema_version": 1,
            **common,
            "source": source_path.as_posix(),
            "source_sha256": source_sha,
            "entry": {
                "address": f"0x{entry['entry_address']:08X}",
                "state": "arm",
                "operation": entry["mnemonic"],
                "target_address": f"0x{entry['target_address']:08X}",
                "rom_code_range": {
                    "start_offset": 0,
                    "end_offset_exclusive": 4,
                    "length": 4,
                    "sha256": digest(data[:4]),
                    "raw_bytes_published": False,
                },
            },
        }
        transition_end = transition["instruction_address"] - ROM_BASE + 4
        if transition_end <= bootstrap_offset:
            raise ValueError(f"invalid bootstrap range: {release_id}")
        literal_loads = sum(
            item["kind"] == "ldr-literal" for item in bootstrap["instructions"]
        )
        bootstrap_map = {
            "schema_version": 1,
            **common,
            "bootstrap": {
                "address": f"0x{bootstrap['start_address']:08X}",
                "instruction_count": bootstrap["instruction_count"],
                "literal_load_count": literal_loads,
                "rom_code_range": {
                    "start_offset": bootstrap_offset,
                    "end_offset_exclusive": transition_end,
                    "length": transition_end - bootstrap_offset,
                    "sha256": digest(data[bootstrap_offset:transition_end]),
                    "raw_bytes_published": False,
                },
            },
            "transition": {
                "instruction_address": f"0x{transition['instruction_address']:08X}",
                "register": transition["register"],
                "loaded_at": f"0x{transition['loaded_at']:08X}",
                "literal_address": f"0x{transition['literal_address']:08X}",
                "target_address": f"0x{transition['target_address']:08X}",
                "target_state": transition["target_state"],
            },
        }
        cfg_map = {
            "schema_version": 1,
            **common,
            "function": {
                "name": "AgbMain",
                "address": agb["function"]["address"],
                "range_end_exclusive": agb["function"]["range_end_exclusive"],
                "nonreturning": True,
                "rom_code_range": agb["function"]["rom_code_range"],
            },
            "control_flow": {
                "instruction_halfwords": cfg["instruction_halfwords"],
                "edge_count": len(cfg["edges"]),
                "edge_kinds": edge_kinds(cfg["edges"]),
                "direct_call_count": len(cfg["calls"]),
                "return_count": len(cfg["returns"]),
                "loop_back_edge": loop,
                "raw_halfwords_omitted": True,
            },
            "cross_reference": {
                "agb_main_map": agb_path.as_posix(),
                "agb_main_map_sha256": file_hash(root / agb_path),
            },
        }
        entry_path = Path(f"analysis/{release_id}-entrypoint.json")
        bootstrap_path = Path(f"analysis/{release_id}-bootstrap.json")
        cfg_path = Path(f"analysis/{release_id}-thumb-entry-cfg.json")
        write_json(root / entry_path, entry_map)
        write_json(root / bootstrap_path, bootstrap_map)
        write_json(root / cfg_path, cfg_map)
        entry_maps.append(entry_path)
        bootstrap_maps.append(bootstrap_path)
        cfg_maps.append(cfg_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "entry_target": entry_map["entry"]["target_address"],
            "thumb_target": bootstrap_map["transition"]["target_address"],
            "evidence": {
                "entrypoint": entry_path.as_posix(),
                "bootstrap": bootstrap_path.as_posix(),
                "thumb_cfg": cfg_path.as_posix(),
            },
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/entry-bootstrap-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research = {
        Path("research/entrypoint-reconstruction.md"):
            f"# {game} GBA entrypoint reconstruction\n\nThe Japanese release `{releases[0]['id']}` is the origin reference. All {len(records)} cataloged releases ({languages}) contain a verified ARM branch at the GBA entry address. Per-release evidence stores the target and a four-byte range hash without publishing the encoded instruction word. `src/rom_entry.s` preserves the semantic branch using symbols.\n",
        Path("research/bootstrap-transition.md"):
            f"# {game} ARM-to-Thumb bootstrap transition\n\nAll {len(records)} cataloged releases were traced from the decoded entry target to a literal-backed register branch into Thumb state. Each transition target is required to equal the corresponding verified `AgbMain` address. Maps retain addresses, counts and code hashes but omit ARM instruction words and literal values.\n",
        Path("research/thumb-entry-cfg.md"):
            f"# {game} Thumb entry CFG\n\nAll {len(records)} cataloged releases were conservatively traced from the bootstrap Thumb target through the non-returning `AgbMain` loop. Compact CFG evidence is cross-checked against each release's `AgbMain` map and records only counts, edge kinds, the loop edge and hashes; Thumb halfwords and instruction arrays are omitted.\n",
    }
    for path, text in research.items():
        (root / path).write_text(text, encoding="utf-8", newline="\n")

    test_paths = {
        "entrypoint": Path("tests/test_entrypoint.py"),
        "bootstrap": Path("tests/test_bootstrap.py"),
        "thumb_cfg": Path("tests/test_thumb_entry_cfg.py"),
    }
    common_outputs = [catalog_path, summary_path]
    groups = {
        "entrypoint": [source_path, *common_outputs, *entry_maps,
                       Path("research/entrypoint-reconstruction.md"),
                       test_paths["entrypoint"]],
        "bootstrap": [*common_outputs, *bootstrap_maps,
                      Path("research/bootstrap-transition.md"),
                      test_paths["bootstrap"]],
        "thumb-entry-cfg": [*common_outputs, *cfg_maps,
                            Path("research/thumb-entry-cfg.md"),
                            test_paths["thumb_cfg"]],
    }
    generator = {
        "repository": "SakuraiTsubaki/Decompilation",
        "tool": "tools/entry_bootstrap_catalog.py",
        "tool_sha256": file_hash(Path(__file__)),
    }
    for name, outputs in groups.items():
        missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
        if missing:
            raise ValueError("missing output(s): " + ", ".join(missing))
        write_json(root / f"manifests/{name}.json", {
            "schema_version": 1,
            "game": game,
            "evidence_kind": name,
            "origin_reference": releases[0]["id"],
            "release_count": len(records),
            "generator": generator,
            "outputs": [
                {"path": path.as_posix(), "sha256": file_hash(root / path)}
                for path in outputs
            ],
            "raw_rom_bytes_included": False,
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
