import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "trainer_id_evidence", ROOT / "tools/trainer_id_evidence.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrainerIdEvidenceTests(unittest.TestCase):
    def test_variant_function_sets(self):
        self.assertEqual(
            [name for _, name in MODULE.VARIANTS["rs"]],
            ["write_word_to_mem", "copy_word_to_mem"],
        )
        self.assertEqual(
            [name for _, name in MODULE.VARIANTS["emerald"]],
            ["SetTrainerId", "GetTrainerId", "CopyTrainerId"],
        )
        self.assertEqual(
            [name for _, name in MODULE.VARIANTS["frlg"]],
            ["SetTrainerId", "CopyTrainerId"],
        )


if __name__ == "__main__":
    unittest.main()
