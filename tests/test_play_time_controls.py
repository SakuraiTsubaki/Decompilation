import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "play_time_controls", ROOT / "tools/play_time_controls.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_evidence = MODULE.build_evidence


class PlayTimeControlsEvidenceTests(unittest.TestCase):
    def test_rejects_cfg_from_another_rom(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "analysis").mkdir()
            (root / "research").mkdir()
            (root / "manifests").mkdir()
            (root / "src/play_time_counter.c").write_text("source\n")
            rom = root / "test.gba"
            rom.write_bytes(bytes(64))
            digest = hashlib.sha256(rom.read_bytes()).hexdigest()
            for slug in ("reset", "start", "stop", "set-to-max"):
                (root / f"analysis/test-jp-play-time-counter-{slug}-cfg.json").write_text(
                    json.dumps({"source_sha256": "wrong", "raw_halfwords_omitted": True})
                )
            with self.assertRaisesRegex(ValueError, "targets another ROM"):
                build_evidence(root, rom, digest, "TEST-rev0", "test", "direct", "ref/repo", "abc", "src/play_time.c")

    def test_rejects_start_call_to_wrong_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("src", "analysis", "research", "manifests"):
                (root / name).mkdir()
            (root / "src/play_time_counter.c").write_text("source\n")
            (root / "analysis/test-jp-play-time-counter-update-map.json").write_text('{"source_sha256":""}')
            (root / "manifests/play-time-counter-update-reconstruction.json").write_text('{"outputs":[]}')
            rom = root / "test.gba"
            rom.write_bytes(bytes(64))
            digest = hashlib.sha256(rom.read_bytes()).hexdigest()
            for index, slug in enumerate(("reset", "start", "stop", "set-to-max")):
                address = 0x08000000 + index * 8
                calls = [{"source": address, "target": 0x08000038}] if slug == "start" else []
                cfg = {
                    "source_sha256": digest,
                    "raw_halfwords_omitted": True,
                    "returns": [address + 2],
                    "range_start": address,
                    "range_end": address + 4,
                    "rom_base": 0x08000000,
                    "calls": calls,
                    "edges": [],
                }
                (root / f"analysis/test-jp-play-time-counter-{slug}-cfg.json").write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, "observed SetToMax entry"):
                build_evidence(root, rom, digest, "TEST-rev0", "test", "direct", "ref/repo", "abc", "src/play_time.c")


if __name__ == "__main__":
    unittest.main()
