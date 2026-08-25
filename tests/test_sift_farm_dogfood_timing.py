from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import sift_farm_dogfood_timing


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class DogfoodTimingHistoryTests(unittest.TestCase):
    def make_run(self, root: Path, *, with_summary: bool = True) -> Path:
        run_dir = root / ".run" / "farm-results" / "farm-run-timing"
        status = {
            "run_id": "farm-run-timing",
            "status": "complete",
            "mode": "summarize",
            "agent": "default",
            "model": "qwen-test:1b",
            "runtime": {
                "profile": "local-test",
                "model": "qwen-test:1b",
                "concurrency": {"jobs": 1, "chunks": 1},
                "summarize": {
                    "chunk_strategy": "token",
                    "chunk_tokens": 4096,
                    "reduce_tokens": 4096,
                    "snippet_policy": "auto",
                    "snippet_max_chars": 600,
                },
            },
            "timing": {"duration_ms": 1500},
            "jobs": [
                {
                    "job_id": "job-0001",
                    "input_path": "article-1.txt",
                    "status": "complete",
                    "warnings": [],
                    "timing": {
                        "queue_wait_ms": 10,
                        "duration_ms": 500,
                        "calls": [
                            {
                                "kind": "single",
                                "file_path": "article-1.txt",
                                "duration_ms": 450,
                                "status": "complete",
                            }
                        ],
                    },
                    "chunking": {"enabled": False, "strategy": "single-pass"},
                    "result_json": "jobs/job-0001/result.json",
                },
                {
                    "job_id": "job-0002",
                    "input_path": "article-2.txt",
                    "status": "complete_with_warnings",
                    "warnings": ["snippet_count_under_requested"],
                    "timing": {
                        "queue_wait_ms": 50,
                        "duration_ms": 900,
                        "calls": [
                            {"kind": "chunk_map", "chunk_id": "chunk-0001", "duration_ms": 300, "status": "complete"},
                            {"kind": "chunk_map", "chunk_id": "chunk-0002", "duration_ms": 350, "status": "complete"},
                            {"kind": "reduce", "duration_ms": 100, "status": "complete"},
                        ],
                    },
                    "chunking": {"enabled": True, "chunk_count": 2},
                },
            ],
        }
        write_json(run_dir / "farm-status.json", status)
        write_json(
            run_dir / "jobs" / "job-0001" / "result.json",
            {
                "result": {
                    "abstract": "Do not persist full summary text.",
                    "snippets": [{"text": "Sensitive exact source snippet."}],
                },
                "artifacts": {"raw_response": "jobs/job-0001/raw-response.txt"},
            },
        )
        (run_dir / "jobs" / "job-0001" / "raw-response.txt").write_text(
            "Raw response should not be copied.",
            encoding="utf-8",
        )
        if with_summary:
            write_json(
                run_dir / "timing-summary.json",
                {
                    "run_id": "farm-run-timing",
                    "timing": {"duration_ms": 1500},
                    "aggregate_by_call_kind": {
                        "single": {"count": 1, "duration_ms": 450},
                        "chunk_map": {"count": 2, "duration_ms": 650},
                        "reduce": {"count": 1, "duration_ms": 100},
                    },
                    "slowest_jobs": [
                        {
                            "job_id": "job-0002",
                            "input_path": "article-2.txt",
                            "status": "complete_with_warnings",
                            "duration_ms": 900,
                            "queue_wait_ms": 50,
                        }
                    ],
                    "slowest_calls": [
                        {
                            "job_id": "job-0001",
                            "input_path": "article-1.txt",
                            "kind": "single",
                            "file_path": "article-1.txt",
                            "duration_ms": 450,
                            "status": "complete",
                        }
                    ],
                },
            )
        return run_dir

    def test_build_timing_record_extracts_compact_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = self.make_run(root)

            record = sift_farm_dogfood_timing.build_timing_record(
                root=root,
                run_dir=run_dir,
                label="baseline",
                recorded_at="2026-08-24T00:00:00Z",
            )

            self.assertEqual(record["label"], "baseline")
            self.assertEqual(record["run_id"], "farm-run-timing")
            self.assertEqual(record["agent"], "default")
            self.assertEqual(record["profile"], "local-test")
            self.assertEqual(record["totals"]["duration_ms"], 1500)
            self.assertEqual(record["totals"]["jobs"], 2)
            self.assertEqual(record["totals"]["chunks"], 3)
            self.assertEqual(record["totals"]["calls"], 4)
            self.assertEqual(record["totals"]["queue_wait_ms"], 60)
            self.assertEqual(record["totals"]["call_duration_ms"], 1200)
            self.assertEqual(record["totals"]["by_call_kind"]["chunk_map"]["count"], 2)
            self.assertEqual(record["totals"]["by_call_kind"]["chunk_map"]["duration_ms"], 650)
            self.assertEqual(record["jobs"][1]["warning_count"], 1)
            self.assertEqual(record["slowest_jobs"][0]["job_id"], "job-0002")
            self.assertEqual(record["slowest_calls"][0]["kind"], "single")

            serialized = json.dumps(record)
            self.assertNotIn("Sensitive exact source snippet", serialized)
            self.assertNotIn("Raw response should not be copied", serialized)
            self.assertNotIn("Do not persist full summary", serialized)

    def test_build_timing_record_falls_back_without_timing_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = self.make_run(root, with_summary=False)

            record = sift_farm_dogfood_timing.build_timing_record(root=root, run_dir=run_dir, label=None)

            self.assertEqual(record["slowest_jobs"][0]["job_id"], "job-0002")
            self.assertEqual(record["slowest_calls"][0]["kind"], "single")
            self.assertEqual(record["totals"]["by_call_kind"]["reduce"]["duration_ms"], 100)

    def test_build_timing_record_handles_missing_optional_timing_fields(self) -> None:
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
                    "jobs": [{"job_id": "job-0001", "input_path": "old.txt", "status": "complete"}],
                },
            )

            record = sift_farm_dogfood_timing.build_timing_record(root=root, run_dir=run_dir)

            self.assertEqual(record["totals"]["jobs"], 1)
            self.assertEqual(record["totals"]["chunks"], 1)
            self.assertEqual(record["totals"]["calls"], 0)
            self.assertEqual(record["jobs"][0]["queue_wait_ms"], None)

    def test_compare_timing_records_calculates_deltas_and_notes(self) -> None:
        baseline = {
            "label": "base",
            "run_id": "run-base",
            "status": "complete",
            "model": "qwen-test:1b",
            "profile": "local-test",
            "commit": "abc1234",
            "runtime": {
                "concurrency": {"jobs": 1},
                "summarize": {"chunk_strategy": "token", "chunk_tokens": 4096, "reduce_tokens": 4096},
            },
            "totals": {
                "duration_ms": 1000,
                "jobs": 1,
                "chunks": 2,
                "calls": 3,
                "queue_wait_ms": 5,
                "call_duration_ms": 900,
                "by_call_kind": {"chunk_map": {"count": 2, "duration_ms": 700}, "reduce": {"count": 1, "duration_ms": 200}},
            },
            "jobs": [
                {
                    "job_id": "job-0001",
                    "input_path": "a.txt",
                    "status": "complete",
                    "duration_ms": 1000,
                    "queue_wait_ms": 5,
                    "chunk_count": 2,
                    "call_count": 3,
                    "call_duration_ms": 900,
                    "warning_count": 0,
                    "by_call_kind": {"chunk_map": {"count": 2, "duration_ms": 700}},
                }
            ],
        }
        candidate = {
            "label": "candidate",
            "run_id": "run-candidate",
            "status": "complete",
            "model": "qwen-test:1b",
            "profile": "larger-test",
            "commit": "def5678",
            "runtime": {
                "concurrency": {"jobs": 2},
                "summarize": {"chunk_strategy": "token", "chunk_tokens": 4096, "reduce_tokens": 4096},
            },
            "totals": {
                "duration_ms": 800,
                "jobs": 1,
                "chunks": 2,
                "calls": 3,
                "queue_wait_ms": 15,
                "call_duration_ms": 700,
                "by_call_kind": {"chunk_map": {"count": 2, "duration_ms": 550}, "reduce": {"count": 1, "duration_ms": 150}},
            },
            "slowest_jobs": [{"job_id": "job-0001", "input_path": "a.txt", "duration_ms": 800}],
            "slowest_calls": [{"job_id": "job-0001", "kind": "chunk_map", "target": "chunk-0001", "duration_ms": 300}],
            "jobs": [
                {
                    "job_id": "job-0001",
                    "input_path": "a.txt",
                    "status": "complete",
                    "duration_ms": 800,
                    "queue_wait_ms": 15,
                    "chunk_count": 2,
                    "call_count": 3,
                    "call_duration_ms": 700,
                    "warning_count": 0,
                    "by_call_kind": {"chunk_map": {"count": 2, "duration_ms": 550}},
                }
            ],
        }

        comparison = sift_farm_dogfood_timing.compare_timing_records(
            baseline,
            candidate,
            compared_at="2026-08-24T00:00:01Z",
        )
        markdown = sift_farm_dogfood_timing.render_timing_comparison_markdown(comparison)

        self.assertEqual(comparison["totals"]["duration_ms"]["delta"], -200)
        self.assertEqual(comparison["totals"]["queue_wait_ms"]["delta"], 10)
        self.assertEqual(comparison["by_call_kind"]["chunk_map"]["duration_ms"]["delta"], -150)
        self.assertEqual(comparison["jobs"][0]["duration_ms"]["delta"], -200)
        self.assertFalse(comparison["comparability"]["comparable"])
        self.assertIn("profile differs", "\n".join(comparison["comparability"]["notes"]))
        self.assertIn("concurrency.jobs differs", "\n".join(comparison["comparability"]["notes"]))
        self.assertIn("Dogfood Timing Comparison base -> candidate", markdown)
        self.assertIn("| Duration Ms | 1000 | 800 | -200 |", markdown)
        self.assertIn("profile differs", markdown)

    def test_write_helpers_use_safe_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            record_path = sift_farm_dogfood_timing.write_timing_record(
                {"label": "bad label/ok", "run_id": "run"},
                output / "runs",
            )
            comparison = {
                "baseline": {"label": "bad base"},
                "candidate": {"label": "bad candidate"},
                "totals": {},
                "by_call_kind": {},
                "jobs": [],
            }
            json_path, md_path = sift_farm_dogfood_timing.write_timing_comparison(
                comparison,
                output / "comparisons",
            )

            self.assertEqual(record_path.name, "bad-label-ok.json")
            self.assertEqual(json_path.name, "bad-base--bad-candidate.json")
            self.assertTrue(record_path.exists())
            self.assertTrue(md_path.exists())


if __name__ == "__main__":
    unittest.main()
