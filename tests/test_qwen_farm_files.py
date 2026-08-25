from __future__ import annotations

import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from src import qwen_farm_files


class RunIdTests(unittest.TestCase):
    def test_make_run_id_uses_timestamp_and_suffix(self) -> None:
        run_id = qwen_farm_files.make_run_id(datetime(2026, 8, 23, 14, 30, 22), "a7f3")

        self.assertEqual(run_id, "farm-run-2026-08-23-143022-a7f3")
        self.assertRegex(run_id, r"^farm-run-\d{4}-\d{2}-\d{2}-\d{6}-[0-9a-f]{4}$")

    def test_job_id_for_uses_four_digits(self) -> None:
        self.assertEqual(qwen_farm_files.job_id_for(1), "job-0001")
        self.assertEqual(qwen_farm_files.job_id_for(42), "job-0042")


class FarmHomeTests(unittest.TestCase):
    def test_farm_home_defaults_under_run_farm(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(qwen_farm_files.farm_home(Path("/repo")), Path("/repo/.run/farm"))

    def test_farm_home_uses_environment_override(self) -> None:
        with patch.dict("os.environ", {"QWEN_FARM_HOME": "/tmp/qwen-farm"}):
            self.assertEqual(qwen_farm_files.farm_home(Path("/repo")), Path("/tmp/qwen-farm"))


class DiscoveryTests(unittest.TestCase):
    def test_discover_text_files_skips_generated_binary_and_minified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "notes").mkdir()
            (root / "notes" / "a.md").write_text("hello", encoding="utf-8")
            (root / "script.js").write_text("console.log('ok')", encoding="utf-8")
            (root / "bundle.min.js").write_text("minified", encoding="utf-8")
            (root / "image.png").write_bytes(b"\x89PNG\r\n")
            (root / "binary.dat").write_bytes(b"a\x00b")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "dep.txt").write_text("skip me", encoding="utf-8")

            result = qwen_farm_files.discover_text_files(root)

        self.assertEqual([item.relative_path for item in result.files], ["notes/a.md", "script.js"])
        self.assertIn("bundle.min.js", result.skipped)
        self.assertIn("image.png", result.skipped)
        self.assertIn("binary.dat", result.skipped)
        self.assertIn("node_modules/dep.txt", result.skipped)

    def test_discover_text_files_applies_include_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "articles").mkdir()
            (root / "notes").mkdir()
            (root / "articles" / "a.txt").write_text("A", encoding="utf-8")
            (root / "notes" / "b.md").write_text("B", encoding="utf-8")
            (root / "c.txt").write_text("C", encoding="utf-8")

            result = qwen_farm_files.discover_text_files(root, include=["articles/*.txt"])

        self.assertEqual([item.relative_path for item in result.files], ["articles/a.txt"])
        self.assertIn("notes/b.md", result.skipped)
        self.assertIn("c.txt", result.skipped)
        details = {item["path"]: item["reason"] for item in result.skipped_details or []}
        self.assertEqual(details["notes/b.md"], "not_included_by_pattern")

    def test_discover_text_files_applies_exclude_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "raw").mkdir()
            (root / "articles").mkdir()
            (root / "raw" / "page.txt").write_text("raw", encoding="utf-8")
            (root / "articles" / "keep.txt").write_text("keep", encoding="utf-8")

            result = qwen_farm_files.discover_text_files(root, exclude=["**/raw/**"])

        self.assertEqual([item.relative_path for item in result.files], ["articles/keep.txt"])
        self.assertIn("raw/page.txt", result.skipped)
        detail = next(item for item in result.skipped_details or [] if item["path"] == "raw/page.txt")
        self.assertEqual(detail["reason"], "excluded_by_pattern")
        self.assertEqual(detail["pattern"], "**/raw/**")

    def test_discover_text_files_exclude_wins_over_include(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "articles").mkdir()
            (root / "articles" / "keep.txt").write_text("keep", encoding="utf-8")
            (root / "articles" / "draft.txt").write_text("draft", encoding="utf-8")

            result = qwen_farm_files.discover_text_files(
                root,
                include=["articles/*.txt"],
                exclude=["**/draft.txt"],
            )

        self.assertEqual([item.relative_path for item in result.files], ["articles/keep.txt"])
        detail = next(item for item in result.skipped_details or [] if item["path"] == "articles/draft.txt")
        self.assertEqual(detail["reason"], "excluded_by_pattern")

    def test_discover_text_files_include_does_not_force_unsafe_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "good.txt").write_text("good", encoding="utf-8")
            (root / "image.png").write_bytes(b"\x89PNG\r\n")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "dep.txt").write_text("dep", encoding="utf-8")

            result = qwen_farm_files.discover_text_files(root, include=["**/*", "*.png"])

        self.assertEqual([item.relative_path for item in result.files], ["good.txt"])
        details = {item["path"]: item["reason"] for item in result.skipped_details or []}
        self.assertEqual(details["image.png"], "built_in_skipped_suffix")
        self.assertEqual(details["node_modules/dep.txt"], "built_in_skipped_dir")

    def test_make_run_id_pattern_when_suffix_generated(self) -> None:
        run_id = qwen_farm_files.make_run_id(datetime(2026, 8, 23, 14, 30, 22))

        self.assertTrue(re.match(r"^farm-run-2026-08-23-143022-[0-9a-f]{4}$", run_id))

    def test_text_detection_accepts_sample_ending_inside_utf8_character(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "box.txt"
            path.write_bytes(("a" * 8191).encode("utf-8") + "│ text".encode("utf-8"))

            self.assertTrue(qwen_farm_files.is_probably_text_file(path))
