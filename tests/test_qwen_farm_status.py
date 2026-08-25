from __future__ import annotations

import unittest

from src import qwen_farm_status


class StatusCalculationTests(unittest.TestCase):
    def test_final_run_status_complete(self) -> None:
        self.assertEqual(qwen_farm_status.final_run_status([{"status": "complete"}]), "complete")

    def test_final_run_status_partial(self) -> None:
        jobs = [{"status": "complete"}, {"status": "failed"}]

        self.assertEqual(qwen_farm_status.final_run_status(jobs), "partial")

    def test_final_run_status_failed_when_all_failed(self) -> None:
        self.assertEqual(qwen_farm_status.final_run_status([{"status": "failed"}]), "failed")

    def test_final_run_status_complete_with_warnings(self) -> None:
        jobs = [{"status": "complete", "warnings": ["repaired"]}]

        self.assertEqual(qwen_farm_status.final_run_status(jobs), "complete_with_warnings")

    def test_count_jobs_includes_skipped(self) -> None:
        counts = qwen_farm_status.count_jobs(
            [{"status": "queued"}, {"status": "running"}, {"status": "complete"}],
            skipped=2,
        )

        self.assertEqual(counts["total"], 3)
        self.assertEqual(counts["queued"], 1)
        self.assertEqual(counts["running"], 1)
        self.assertEqual(counts["complete"], 1)
        self.assertEqual(counts["skipped"], 2)

    def test_status_markdown_shows_selected_verified_requested_when_different(self) -> None:
        markdown = qwen_farm_status.render_status_markdown(
            {
                "run_id": "run-1",
                "status": "complete",
                "mode": "summarize",
                "agent": "default",
                "model": "qwen-test",
                "runtime": {
                    "summarize": {},
                    "concurrency": {},
                },
                "counts": {"total": 1},
                "jobs": [
                    {
                        "job_id": "job-0001",
                        "status": "complete",
                        "input_path": "input.txt",
                        "result_md": "jobs/job-0001/result.md",
                        "timing": {},
                        "chunking": {"enabled": False, "strategy": "single-pass"},
                        "snippets": {
                            "requested_count": 4,
                            "verified_count": 3,
                            "selected_count": 2,
                        },
                    }
                ],
            }
        )

        self.assertIn("`2/3/4`", markdown)

    def test_status_markdown_shows_active_job_progress(self) -> None:
        markdown = qwen_farm_status.render_status_markdown(
            {
                "run_id": "run-1",
                "status": "running",
                "mode": "summarize",
                "agent": "default",
                "model": "qwen-test",
                "runtime": {
                    "summarize": {},
                    "concurrency": {},
                },
                "counts": {"total": 1, "running": 1},
                "jobs": [
                    {
                        "job_id": "job-0001",
                        "status": "running",
                        "input_path": "input.txt",
                        "result_md": None,
                        "timing": {},
                        "chunking": {"enabled": True, "strategy": "paragraph-token", "chunk_count": 4, "coverage": "full"},
                        "snippets": {},
                        "progress": {
                            "phase": "chunk_map",
                            "message": "Summarizing chunk 2 of 4.",
                            "updated_at": "2026-08-24T12:00:00Z",
                            "chunks": {
                                "total": 4,
                                "queued": 2,
                                "running": 1,
                                "complete": 1,
                                "failed": 0,
                                "current": "chunk-0002",
                            },
                            "reduce": {
                                "generation": None,
                                "batch_index": None,
                                "batch_total": None,
                                "complete": 0,
                            },
                            "current_call": {
                                "kind": "chunk_map",
                                "chunk_id": "chunk-0002",
                                "started_at": "2026-08-24T12:00:00Z",
                                "status": "running",
                            },
                        },
                    }
                ],
            }
        )

        self.assertIn("## Active Jobs", markdown)
        self.assertIn("chunk_map", markdown)
        self.assertIn("1/4 chunks complete, chunk-0002 running", markdown)

    def test_status_markdown_shows_retry_provenance(self) -> None:
        markdown = qwen_farm_status.render_status_markdown(
            {
                "run_id": "run-retry",
                "status": "complete",
                "mode": "summarize",
                "agent": "default",
                "model": "qwen-test",
                "runtime": {
                    "summarize": {},
                    "concurrency": {},
                },
                "counts": {"total": 1, "complete": 1},
                "retry": {
                    "source_run_id": "run-source",
                    "source_failed_count": 1,
                    "retried_count": 1,
                    "jobs": [
                        {
                            "source_job_id": "job-0002",
                            "retry_job_id": "job-0001",
                            "input_path": "fail.txt",
                            "source_error": "planned failure",
                        }
                    ],
                },
                "jobs": [],
            }
        )

        self.assertIn("## Retry", markdown)
        self.assertIn("Source run: `run-source`", markdown)
        self.assertIn("`job-0002` | `job-0001` | `fail.txt`", markdown)

    def test_farm_overview_json_wraps_runs(self) -> None:
        runs = [
            {
                "run_id": "run-2",
                "status": "complete",
                "mode": "summarize",
                "counts": {"total": 1, "complete": 1},
            },
            {
                "run_id": "run-1",
                "status": "failed",
                "mode": "prompt",
                "counts": {"total": 1, "failed": 1},
            },
        ]

        envelope = qwen_farm_status.farm_overview_json(runs)

        self.assertEqual(envelope["schema_version"], 1)
        self.assertEqual(envelope["scope"], "overview")
        self.assertEqual(envelope["counts"], {"runs": 2})
        self.assertEqual(envelope["runs"], runs)

    def test_farm_overview_json_handles_empty_runs(self) -> None:
        envelope = qwen_farm_status.farm_overview_json([])

        self.assertEqual(envelope["scope"], "overview")
        self.assertEqual(envelope["counts"], {"runs": 0})
        self.assertEqual(envelope["runs"], [])

    def test_run_status_json_wraps_loaded_status(self) -> None:
        status = {"run_id": "run-1", "status": "running", "jobs": [{"progress": {"phase": "reduce"}}]}

        envelope = qwen_farm_status.run_status_json(status)

        self.assertEqual(envelope["schema_version"], 1)
        self.assertEqual(envelope["scope"], "run")
        self.assertEqual(envelope["run_id"], "run-1")
        self.assertEqual(envelope["run"], status)
        self.assertEqual(envelope["run"]["jobs"][0]["progress"]["phase"], "reduce")
