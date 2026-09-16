import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.nds_rom_inventory.rom_inventory import crc16_nintendo, inspect_rom, observation, verify


def synthetic_rom(path: Path, *, title: bytes = b"TEST ROM", code: bytes = b"TSTE", version: int = 3) -> bytes:
    data = bytearray(0x400)
    data[0:12] = title.ljust(12, b"\0")
    data[12:16] = code
    data[16:18] = b"01"
    data[0x12] = 0
    data[0x14] = 0
    data[0x1E] = version
    crc = crc16_nintendo(bytes(data[:0x15E]))
    data[0x15E:0x160] = crc.to_bytes(2, "little")
    path.write_bytes(data)
    return bytes(data)


class RomInventoryTests(unittest.TestCase):
    def test_crc16_known_vector(self):
        self.assertEqual(crc16_nintendo(b"123456789"), 0x4B37)

    def test_inspect_synthetic_header_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.nds"
            data = synthetic_rom(path)
            result = inspect_rom(path)

        self.assertEqual(result.title, "TEST ROM")
        self.assertEqual(result.game_code, "TSTE")
        self.assertEqual(result.maker_code, "01")
        self.assertEqual(result.rom_version, 3)
        self.assertEqual(result.nominal_capacity_bytes, 128 * 1024)
        self.assertTrue(result.header_crc16_valid)
        self.assertEqual(result.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual(result.sha1, hashlib.sha1(data).hexdigest())
        self.assertEqual(result.md5, hashlib.md5(data).hexdigest())

    def test_verify_reports_changed_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.nds"
            synthetic_rom(path)
            observed = observation([inspect_rom(path)])
        manifest = {"roms": [dict(observed["roms"][0])]}
        manifest["roms"][0]["sha256"] = "0" * 64
        errors = verify(observed, manifest)
        self.assertEqual(len(errors), 1)
        self.assertIn("sha256", errors[0])


if __name__ == "__main__":
    unittest.main()
