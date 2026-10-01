import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "validate_agb_main_map.py"
SPEC = importlib.util.spec_from_file_location("validate_agb_main_map", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture():
    cfg = {
        "source_sha256": "a" * 64,
        "start_address": 0x08000100,
        "range_end": 0x08000120,
        "return_observed": False,
        "calls": [
            {"source": 0x08000104, "target": 0x08000200},
            {"source": 0x08000108, "target": 0x08000200},
        ],
        "edges": [{"source": 0x0800011E, "target": 0x08000104, "kind": "branch"}],
    }
    address_map = {
        "target": {"sha256": "a" * 64},
        "function": {
            "name": "AgbMain",
            "address": 0x08000100,
            "range_end_exclusive": 0x08000120,
            "nonreturning": True,
            "loop_back_edge": {"source": 0x0800011E, "target": 0x08000104},
        },
        "direct_calls": [
            {"address": 0x08000104, "target": 0x08000200, "name": "FrameStep"},
            {"address": 0x08000108, "target": 0x08000200, "name": "FrameStep"},
        ],
    }
    return cfg, address_map


class Tests(unittest.TestCase):
    def test_complete_map(self):
        cfg, address_map = fixture()
        report = MODULE.validate(cfg, address_map)
        self.assertEqual(report["direct_call_count"], 2)
        self.assertEqual(report["unique_call_target_count"], 1)
        self.assertEqual(report["call_name_counts"], {"FrameStep": 2})
        self.assertFalse(report["raw_rom_bytes_included"])

    def test_identity_and_boundary_mismatches(self):
        cfg, address_map = fixture()
        address_map["target"]["sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            MODULE.validate(cfg, address_map)
        cfg, address_map = fixture()
        address_map["function"]["range_end_exclusive"] += 2
        with self.assertRaisesRegex(ValueError, "function end"):
            MODULE.validate(cfg, address_map)

    def test_missing_call_and_back_edge(self):
        cfg, address_map = fixture()
        address_map["direct_calls"].pop()
        with self.assertRaisesRegex(ValueError, "coverage"):
            MODULE.validate(cfg, address_map)
        cfg, address_map = fixture()
        cfg["edges"].clear()
        with self.assertRaisesRegex(ValueError, "back edge"):
            MODULE.validate(cfg, address_map)

    def test_name_and_return_claim_are_checked(self):
        cfg, address_map = fixture()
        address_map["direct_calls"][0]["name"] = ""
        with self.assertRaisesRegex(ValueError, "non-empty"):
            MODULE.validate(cfg, address_map)
        cfg, address_map = fixture()
        cfg["return_observed"] = True
        with self.assertRaisesRegex(ValueError, "non-returning"):
            MODULE.validate(cfg, address_map)


if __name__ == "__main__":
    unittest.main()
