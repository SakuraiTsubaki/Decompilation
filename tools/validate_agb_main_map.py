#!/usr/bin/env python3
"""Validate a publication-safe AgbMain address map against a verified Thumb CFG."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _pairs(items: list[dict], source_key: str) -> set[tuple[int, int]]:
    return {(item[source_key], item["target"]) for item in items}


def validate(cfg: dict, address_map: dict) -> dict:
    function = address_map["function"]
    if address_map["target"]["sha256"] != cfg["source_sha256"]:
        raise ValueError("map and CFG source SHA-256 values differ")
    if function["address"] != cfg["start_address"]:
        raise ValueError("function start does not match CFG start")
    if function["range_end_exclusive"] != cfg["range_end"]:
        raise ValueError("function end does not match CFG range end")
    if function["nonreturning"] == bool(cfg["return_observed"]):
        raise ValueError("non-returning declaration contradicts CFG return evidence")

    cfg_calls = _pairs(cfg["calls"], "source")
    mapped_calls = _pairs(address_map["direct_calls"], "address")
    if mapped_calls != cfg_calls:
        missing = sorted(cfg_calls - mapped_calls)
        extra = sorted(mapped_calls - cfg_calls)
        raise ValueError(f"direct-call coverage differs: missing={missing}, extra={extra}")
    if any(not item.get("name") for item in address_map["direct_calls"]):
        raise ValueError("every mapped direct call must have a non-empty name")

    back_edge = function["loop_back_edge"]
    expected_edge = {
        "source": back_edge["source"],
        "target": back_edge["target"],
        "kind": "branch",
    }
    if expected_edge not in cfg["edges"]:
        raise ValueError("declared loop back edge is absent from CFG")

    names: dict[str, int] = {}
    for item in address_map["direct_calls"]:
        names[item["name"]] = names.get(item["name"], 0) + 1
    return {
        "schema_version": 1,
        "source_sha256": cfg["source_sha256"],
        "function": function["name"],
        "range_start": function["address"],
        "range_end_exclusive": function["range_end_exclusive"],
        "direct_call_count": len(cfg_calls),
        "unique_call_target_count": len({target for _, target in cfg_calls}),
        "call_name_counts": dict(sorted(names.items())),
        "loop_back_edge": back_edge,
        "return_observed": cfg["return_observed"],
        "raw_rom_bytes_included": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cfg", type=Path)
    parser.add_argument("address_map", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    cfg_bytes = args.cfg.read_bytes()
    map_bytes = args.address_map.read_bytes()
    report = validate(json.loads(cfg_bytes), json.loads(map_bytes))
    report["cfg_file_sha256"] = hashlib.sha256(cfg_bytes).hexdigest()
    report["address_map_file_sha256"] = hashlib.sha256(map_bytes).hexdigest()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
