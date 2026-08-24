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
