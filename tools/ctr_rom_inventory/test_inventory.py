#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("inventory.py")
SPEC = importlib.util.spec_from_file_location("ctr_rom_inventory", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


class InventoryTests(unittest.TestCase):
    def test_synthetic_ncsd_with_ncch_partition(self):
        data = bytearray(0x2000)
        data[0x100:0x104] = b"NCSD"
        data[0x104:0x108] = (0x10).to_bytes(4, "little")
        data[0x108:0x110] = (0x1234).to_bytes(8, "little")
        data[0x120:0x124] = (2).to_bytes(4, "little")
        data[0x124:0x128] = (4).to_bytes(4, "little")
        data[0x190:0x198] = (0x0004000000055D00).to_bytes(8, "little")
        data[0x310:0x312] = (1).to_bytes(2, "little")
        data[0x312:0x314] = (2).to_bytes(2, "little")

        base = 0x400
        data[base + 0x100:base + 0x104] = b"NCCH"
        data[base + 0x104:base + 0x108] = (4).to_bytes(4, "little")
        data[base + 0x108:base + 0x110] = (0x0004000000055D00).to_bytes(8, "little")
        data[base + 0x118:base + 0x120] = (0x0004000000055D00).to_bytes(8, "little")
        product = b"CTR-P-EKJA"
        data[base + 0x150:base + 0x150 + len(product)] = product

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "synthetic.3ds"
            path.write_bytes(data)
            result = MOD.inspect(path)

        self.assertEqual(result["container"]["magic"], "NCSD")
        self.assertEqual(result["container"]["title_version"], 1)
        self.assertEqual(result["container"]["card_revision"], 2)
        self.assertEqual(len(result["container"]["partitions"]), 1)
        ncch = result["container"]["partitions"][0]["ncch"]
        self.assertEqual(ncch["magic"], "NCCH")
        self.assertEqual(ncch["product_code"], "CTR-P-EKJA")
        self.assertEqual(ncch["program_id"], "0004000000055d00")

    def test_unknown_container_is_reported_not_crashed(self):
        data = bytearray(0x400)
        data[0x100:0x104] = b"NOPE"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "unknown.bin"
            path.write_bytes(data)
            result = MOD.inspect(path)
        self.assertFalse(result["container"]["recognized"])
        self.assertEqual(result["container"]["magic"], "NOPE")


if __name__ == "__main__":
    unittest.main()
