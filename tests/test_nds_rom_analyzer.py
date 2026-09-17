import tempfile
import unittest
from pathlib import Path
import subprocess
import sys

from tools.nds_rom_analyzer.analyzer import AnalysisError, analyze_rom, compare_results, crc16_nintendo


def make_fixture(path: Path) -> None:
    data = bytearray(b"\xff" * 0x10000)
    data[0:12] = b"TEST STRUCT\0"
    data[12:16] = b"TSTE"
    data[16:18] = b"01"
    data[0x14] = 0
    data[0x1E] = 1
    # ARM9, ARM7, FNT, FAT, overlay tables, banner.
    fields = {
        0x20: 0x4000, 0x24: 0x02000000, 0x28: 0x02000000, 0x2C: 0x100,
        0x30: 0x5000, 0x34: 0x02380000, 0x38: 0x02380000, 0x3C: 0x80,
        0x40: 0x6000, 0x44: 0x14, 0x48: 0x6100, 0x4C: 8,
        0x50: 0x6200, 0x54: 32, 0x58: 0x6300, 0x5C: 0,
        0x68: 0x7000, 0x80: 0x9000, 0x84: 0x4000,
    }
    for offset, value in fields.items():
        data[offset:offset + 4] = value.to_bytes(4, "little")
    # One root directory and one NARC file named sample.
    fnt = bytearray(0x14)
    fnt[0:8] = (8).to_bytes(4, "little") + (0).to_bytes(2, "little") + (1).to_bytes(2, "little")
    fnt[8] = 6
    fnt[9:15] = b"sample"
    fnt[15] = 0
    data[0x6000:0x6014] = fnt
    data[0x6100:0x6108] = (0x8000).to_bytes(4, "little") + (0x8020).to_bytes(4, "little")
    data[0x8000:0x8010] = b"NARC\xff\xfe\0\x01\x20\0\0\0\x10\0\x03\0"
    # Overlay points at file 0.
    overlay = (0, 0x02100000, 0x20, 0x10, 0x02100000, 0x02100004, 0, 0x01000020)
    import struct
    data[0x6200:0x6220] = struct.pack("<8I", *overlay)
    # Version 1 banner with valid CRC.
    banner = bytearray(0x840)
    banner[0:2] = (1).to_bytes(2, "little")
    title = "Synthetic fixture".encode("utf-16le")
    banner[0x240:0x240 + len(title)] = title
    banner[2:4] = crc16_nintendo(banner[0x20:0x840]).to_bytes(2, "little")
    data[0x7000:0x7840] = banner
    data[0x6C:0x6E] = crc16_nintendo(data[0x4000:0x8000]).to_bytes(2, "little")
    data[0x15C:0x15E] = crc16_nintendo(data[0xC0:0x15C]).to_bytes(2, "little")
    data[0x15E:0x160] = crc16_nintendo(data[:0x15E]).to_bytes(2, "little")
    path.write_bytes(data)


class StructureAnalyzerTests(unittest.TestCase):
    def test_complete_fixture_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.nds"
            make_fixture(path)
            result = analyze_rom(path, "fixture")
        self.assertEqual(result["header"]["game_code"], "TSTE")
        self.assertTrue(result["header"]["header_crc16_valid"])
        self.assertEqual(result["summary"]["file_count"], 1)
        self.assertEqual(result["files"][0]["path"], "/sample")
        self.assertEqual(result["files"][0]["format"], "NARC archive")
        self.assertEqual(result["summary"]["arm9_overlay_count"], 1)
        self.assertTrue(result["banner"]["crc_checks"][0]["valid"])
        self.assertEqual(result["secure_area"]["decrypted_crc_validation"], "not_performed")
        self.assertIn("raw_encrypted_crc16_matches_header", result["secure_area"])

    def test_invalid_fat_range_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.nds"
            make_fixture(path)
            data = bytearray(path.read_bytes())
            data[0x6104:0x6108] = (len(data) + 1).to_bytes(4, "little")
            path.write_bytes(data)
            with self.assertRaises(AnalysisError):
                analyze_rom(path)

    def test_direct_cli_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.nds"
            output = root / "output"
            make_fixture(fixture)
            script = Path(__file__).parents[1] / "tools" / "nds_structure_analyzer.py"
            completed = subprocess.run(
                [sys.executable, str(script), str(fixture), "--output", str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output / "structure.json").is_file())

    def test_pairwise_comparison_distinguishes_changed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path = root / "left.nds", root / "right.nds"
            make_fixture(left_path)
            make_fixture(right_path)
            right = bytearray(right_path.read_bytes())
            right[0x8010] ^= 1
            right_path.write_bytes(right)
            left_result = analyze_rom(left_path, "left")
            right_result = analyze_rom(right_path, "right")
            comparison = compare_results([left_result, right_result])
        pair = comparison["pairwise"][0]
        self.assertEqual(pair["shared_paths"], 1)
        self.assertEqual(pair["changed_at_same_path"], 1)


if __name__ == "__main__":
    unittest.main()
