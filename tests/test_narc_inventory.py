import tempfile
import unittest
from pathlib import Path

from tools.narc_inventory import (
    NarcError,
    compare_inventories,
    compression_metadata,
    decompress_lz,
    inventory_narc,
    parse_narc,
)


def make_narc(members: list[bytes], names: list[str] | None = None) -> bytes:
    gmif_payload = bytearray()
    ranges = []
    for member in members:
        start = len(gmif_payload)
        gmif_payload.extend(member)
        ranges.append((start, len(gmif_payload)))
    btaf = bytearray(b"BTAF")
    btaf.extend((12 + len(ranges) * 8).to_bytes(4, "little"))
    btaf.extend(len(ranges).to_bytes(2, "little"))
    btaf.extend(b"\0\0")
    for start, end in ranges:
        btaf.extend(start.to_bytes(4, "little"))
        btaf.extend(end.to_bytes(4, "little"))
    if names is None:
        btnf_payload = b"\0" * 8
    else:
        table = bytearray()
        table.extend((8).to_bytes(4, "little"))
        table.extend((0).to_bytes(2, "little"))
        table.extend((1).to_bytes(2, "little"))
        for name in names:
            encoded = name.encode("shift_jis")
            table.append(len(encoded))
            table.extend(encoded)
        table.append(0)
        btnf_payload = bytes(table)
    btnf = b"BTNF" + (8 + len(btnf_payload)).to_bytes(4, "little") + btnf_payload
    gmif = b"GMIF" + (8 + len(gmif_payload)).to_bytes(4, "little") + gmif_payload
    body = bytes(btaf) + btnf + bytes(gmif)
    return b"NARC\xff\xfe\0\x01" + (16 + len(body)).to_bytes(4, "little") + b"\x10\0\x03\0" + body


def literal_lz10(payload: bytes) -> bytes:
    result = bytearray([0x10])
    result.extend(len(payload).to_bytes(3, "little"))
    for offset in range(0, len(payload), 8):
        result.append(0)
        result.extend(payload[offset:offset + 8])
    return bytes(result)


class NarcParserTests(unittest.TestCase):
    def test_normal_narc_and_btnf_names(self):
        result = parse_narc(make_narc([b"AAAA", b"BBBB"], ["first.bin", "second.bin"]))
        self.assertEqual(result["member_count"], 2)
        self.assertEqual(result["named_member_count"], 2)
        self.assertEqual(result["members"][0]["name"], "/first.bin")
        self.assertEqual(result["members"][1]["name"], "/second.bin")
        self.assertEqual([b["magic"] for b in result["blocks"]], ["BTAF", "BTNF", "GMIF"])

    def test_bad_block_size_is_rejected(self):
        data = bytearray(make_narc([b"AAAA"]))
        data[20:24] = (0x7FFFFFFF).to_bytes(4, "little")
        with self.assertRaises(NarcError):
            parse_narc(bytes(data))

    def test_member_start_after_end_is_rejected(self):
        data = bytearray(make_narc([b"AAAA"]))
        data[28:32] = (4).to_bytes(4, "little")
        data[32:36] = (2).to_bytes(4, "little")
        with self.assertRaises(NarcError):
            parse_narc(bytes(data))

    def test_out_of_range_member_is_rejected(self):
        data = bytearray(make_narc([b"AAAA"]))
        data[32:36] = (0x1000).to_bytes(4, "little")
        with self.assertRaises(NarcError):
            parse_narc(bytes(data))

    def test_nested_narc_is_recursively_inventoried(self):
        child = make_narc([b"child"], ["child.bin"])
        root = make_narc([child], ["nested.narc"])
        container, members, nested = inventory_narc(
            root, parent_path="/root.narc", parent_file_id=7, parent_rom_offset=0x1000
        )
        self.assertEqual(container["member_count"], 1)
        self.assertTrue(members[0]["nested_container"])
        self.assertEqual(len(nested), 1)
        self.assertEqual(len(members), 2)

    def test_lz10_and_compressed_nested_narc(self):
        child = make_narc([b"child"])
        compressed = literal_lz10(child)
        self.assertEqual(decompress_lz(compressed), child)
        self.assertTrue(compression_metadata(compressed)["decompression_valid"])
        _container, members, nested = inventory_narc(
            make_narc([compressed]), parent_path="/root.narc", parent_file_id=1, parent_rom_offset=0
        )
        self.assertTrue(members[0]["nested_after_decompression"])
        self.assertEqual(len(nested), 1)

    def test_identical_and_changed_member_comparison(self):
        def result(label: str, payload: bytes):
            container, members, nested = inventory_narc(
                make_narc([b"same", payload]), parent_path="/a.narc",
                parent_file_id=1, parent_rom_offset=0,
            )
            return {
                "provenance": {"input_label": label},
                "containers": [container] + nested,
                "members": members,
            }
        comparison = compare_inventories([result("left", b"old"), result("right", b"new")])
        pair = comparison["pairwise"][0]
        self.assertEqual(pair["changed_containers"], 1)
        self.assertGreaterEqual(pair["equal_member_rows"], 1)
        self.assertGreaterEqual(pair["replaced_member_rows"], 1)


if __name__ == "__main__":
    unittest.main()
