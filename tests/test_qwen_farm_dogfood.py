from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import qwen_farm_dogfood


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class DogfoodHistoryTests(unittest.TestCase):
    def make_run(self, root: Path) -> Path:
        run_dir = root / ".run" / "farm-results" / "farm-run-test"
        write_json(
            run_dir / "farm-status.json",
            {
                "run_id": "farm-run-test",
                "status": "complete",
                "mode": "summarize",
                "model": "qwen-test:1b",
                "runtime": {
                    "profile": "local-test",
                    "model": "qwen-test:1b",
                    "summarize": {
                        "chunk_strategy": "token",
                        "chunk_tokens": 4096,
                        "snippet_policy": "auto",
                        "snippet_max_chars": 600,
                    },
                },
                "timing": {"duration_ms": 1200},
                "jobs": [
                    {
                        "job_id": "job-0001",
                        "input_path": "article-1.txt",
                        "status": "complete",
                        "warnings": [],
                        "timing": {"duration_ms": 500},
                        "chunking": {"enabled": False, "strategy": "single-pass"},
                        "snippets": {
                            "requested_count": 2,
                            "verified_count": 2,
                            "selected_count": 1,
                            "candidate_count": 3,
                            "dropped": {
                                "unverified": 0,
                                "low_signal": 1,
                                "duplicate": 1,
                                "too_long": 0,
                            },
                        },
                        "result_md": "jobs/job-0001/result.md",
                    },
                    {
                        "job_id": "job-0002",
                        "input_path": "article-2.txt",
                        "status": "complete_with_warnings",
                        "warnings": ["snippet_count_under_requested"],
                        "timing": {"duration_ms": 700},
                        "chunking": {"enabled": True, "chunk_count": 3},
                        "snippets": {
                            "requested_count": 4,
                            "verified_count": 2,
                            "selected_count": 2,
                            "candidate_count": 2,
                            "dropped": {"unverified": 1},
                        },
                    },
                ],
            },
        )
        write_json(
            run_dir / "jobs" / "job-0001" / "result.json",
            {
                "result": {
                    "abstract": "Do not persist full summaries in dogfood history.",
                    "snippets": [{"text": "Sensitive exact source snippet."}],
                },
                "raw_response": "Raw response should not be copied.",
            },
        )
        return run_dir

    def test_build_quality_record_extracts_compact_metrics_and_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = self.make_run(root)
            notes = root / "notes.json"
            write_json(
                notes,
                {
                    "quality": {"summary_accuracy": 4, "overall": 5, "bad": 9},
                    "notes": ["Good enough."],
                    "jobs": {
                        "article-1.txt": {
                            "quality": {"snippet_usefulness": 5},
                            "notes": ["Strong snippet."],
                        }
                    },
                },
            )

            record = qwen_farm_dogfood.build_quality_record(
                root=root,
                run_dir=run_dir,
                label="candidate",
                notes_path=notes,
                recorded_at="2026-08-24T00:00:00Z",
            )

            self.assertEqual(record["label"], "candidate")
            self.assertEqual(record["run_id"], "farm-run-test")
            self.assertEqual(record["quality"], {"summary_accuracy": 4, "overall": 5})
            self.assertEqual(record["notes"], ["Good enough."])
            self.assertEqual(record["totals"]["jobs"], 2)
            self.assertEqual(record["totals"]["chunks"], 4)
            self.assertEqual(record["totals"]["warnings"], 1)
            self.assertEqual(record["totals"]["requested_snippets"], 6)
            self.assertEqual(record["totals"]["verified_snippets"], 4)
            self.assertEqual(record["totals"]["selected_snippets"], 3)
            self.assertEqual(record["totals"]["dropped"]["low_signal"], 1)
            self.assertEqual(record["totals"]["dropped"]["duplicate"], 1)
            self.assertEqual(record["totals"]["dropped"]["unverified"], 1)
            self.assertEqual(record["jobs"][0]["quality"], {"snippet_usefulness": 5})
            self.assertEqual(record["jobs"][0]["notes"], ["Strong snippet."])

            serialized = json.dumps(record)
            self.assertNotIn("Sensitive exact source snippet", serialized)
            self.assertNotIn("Raw response should not be copied", serialized)
            self.assertNotIn("Do not persist full summaries", serialized)

    def test_build_quality_record_handles_missing_snippet_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "run"
            write_json(
                run_dir / "farm-status.json",
                {
                    "run_id": "old-run",
                    "status": "complete",
                    "mode": "summarize",
                    "model": "qwen-test:1b",
                    "timing": {},
                    "jobs": [{"job_id": "job-0001", "input_path": "old.txt", "timing": {}, "chunking": {}}],
                },
            )

            record = qwen_farm_dogfood.build_quality_record(root=root, run_dir=run_dir, label=None)

            self.assertEqual(record["totals"]["requested_snippets"], 0)
            self.assertEqual(record["totals"]["selected_snippets"], 0)
            self.assertEqual(record["jobs"][0]["snippets"]["dropped"]["low_signal"], 0)

    def test_write_quality_record_uses_safe_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "runs"
            path = qwen_farm_dogfood.write_quality_record({"label": "bad label/ok", "run_id": "run"}, output)

            self.assertEqual(path.name, "bad-label-ok.json")
            self.assertTrue(path.exists())

    def test_compare_records_calculates_deltas_and_renders_markdown(self) -> None:
        baseline = {
            "label": "base",
            "run_id": "run-base",
            "status": "complete",
            "duration_ms": 1000,
            "totals": {"warnings": 1, "selected_snippets": 2, "dropped": {"low_signal": 2}},
            "quality": {"overall": 3},
            "jobs": [
                {
                    "input_path": "a.txt",
                    "status": "complete",
                    "duration_ms": 600,
                    "warning_count": 1,
                    "snippets": {"selected_count": 1, "verified_count": 1, "requested_count": 2},
                }
            ],
        }
        candidate = {
            "label": "candidate",
            "run_id": "run-candidate",
            "status": "complete",
            "duration_ms": 800,
            "totals": {"warnings": 0, "selected_snippets": 3, "dropped": {"low_signal": 0}},
            "quality": {"overall": 4},
            "notes": ["Cleaner snippets."],
            "jobs": [
                {
                    "input_path": "a.txt",
                    "status": "complete",
                    "duration_ms": 500,
                    "warning_count": 0,
                    "snippets": {"selected_count": 2, "verified_count": 2, "requested_count": 2},
                }
            ],
        }

        comparison = qwen_farm_dogfood.compare_records(baseline, candidate)
        markdown = qwen_farm_dogfood.render_comparison_markdown(comparison)

        self.assertEqual(comparison["duration_ms"]["delta"], -200)
        self.assertEqual(comparison["totals"]["warnings"]["delta"], -1)
        self.assertEqual(comparison["quality"]["overall"]["delta"], 1)
        self.assertIn("Cleaner snippets.", markdown)
        self.assertIn("1/1/2 -> 2/2/2", markdown)


if __name__ == "__main__":
    unittest.main()
