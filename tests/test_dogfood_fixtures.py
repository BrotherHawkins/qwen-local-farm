import json
from pathlib import Path
import unittest

from src.sift_farm_extract import EXTRACT_ITEM_TYPES


ROOT = Path(__file__).resolve().parents[1]


class DogfoodFixtureTests(unittest.TestCase):
    def test_extract_lite_expected_signals_reference_existing_inputs(self) -> None:
        manifest_path = ROOT / "dogfood" / "extract_lite" / "expected-signals.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["fixture"], "extract_lite")
        files = manifest["files"]
        self.assertEqual(len(files), 4)

        for entry in files:
            input_path = ROOT / entry["path"]
            self.assertTrue(input_path.exists(), entry["path"])
            self.assertTrue(input_path.read_text(encoding="utf-8").startswith("Source URL: synthetic://"))
            self.assertTrue(set(entry["expected_types"]).issubset(EXTRACT_ITEM_TYPES))
            self.assertGreaterEqual(len(entry["signals"]), 3)

    def test_extract_lite_has_three_small_files_and_one_chunked_file(self) -> None:
        input_dir = ROOT / "dogfood" / "extract_lite" / "inputs"
        sizes = {path.name: len(path.read_text(encoding="utf-8")) for path in input_dir.glob("*.txt")}

        self.assertEqual(len(sizes), 4)
        self.assertLess(sizes["001-evidence-small.txt"], 2500)
        self.assertLess(sizes["002-entities-small.txt"], 2500)
        self.assertLess(sizes["003-work-small.txt"], 2500)
        self.assertGreaterEqual(sizes["004-research-long-chunked.txt"], 7500)


if __name__ == "__main__":
    unittest.main()
