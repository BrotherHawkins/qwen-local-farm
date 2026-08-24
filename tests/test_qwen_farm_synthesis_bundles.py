from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import qwen_farm_synthesis_bundles


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class SynthesisBundleTests(unittest.TestCase):
    def make_run(self, root: Path) -> Path:
        run_dir = root / ".run" / "farm-results" / "farm-run-test"
        write_json(
            run_dir / "farm-status.json",
            {
                "run_id": "farm-run-test",
                "status": "complete",
                "mode": "summarize",
                "model": "qwen-test:1b",
                "jobs": [
                    {
                        "job_id": "job-0001",
                        "input_path": "article-a.txt",
                        "status": "complete",
                        "warnings": [],
                        "result_json": "jobs/job-0001/result.json",
                    },
                    {
                        "job_id": "job-0002",
                        "input_path": "article-b.txt",
                        "status": "complete_with_warnings",
                        "warnings": ["snippet_count_under_requested"],
                        "result_json": "jobs/job-0002/result.json",
                    },
                    {
                        "job_id": "job-0003",
                        "input_path": "article-c.txt",
                        "status": "complete",
                        "result_json": "jobs/job-0003/result.json",
                    },
                ],
            },
        )
        write_json(
            run_dir / "jobs" / "job-0001" / "result.json",
            {
                "result": {
                    "title": "Evidence Packs",
                    "abstract": "Summary one should be included in the synthesis bundle.",
                    "bullets": ["Evidence packs reduce artifact hunting."],
                    "open_questions": ["How large should the bundle be?"],
                    "confidence": "high",
                    "snippets": [
                        {
                            "text": "The central claim is that small verified evidence packs make synthesis easier.",
                            "reason": "Captures the thesis.",
                            "source_path": "article-a.txt",
                            "start_line": 3,
                            "end_line": 3,
                            "char_start": 120,
                            "char_end": 195,
                            "score": 12,
                            "score_reasons": ["thesis", "claim"],
                        },
                        {
                            "text": "The central claim is that small verified evidence packs make synthesis easier. ",
                            "reason": "Duplicate with whitespace.",
                            "score": 5,
                        },
                    ],
                },
                "raw_response": "Raw model response should not be copied.",
            },
        )
        write_json(
            run_dir / "jobs" / "job-0002" / "result.json",
            {
                "result": {
                    "title": "Mechanism",
                    "abstract": "Summary two gives synthesis orientation.",
                    "bullets": "String bullets are normalized.",
                    "open_questions": [],
                    "confidence": "medium",
                    "snippets": [
                        {
                            "text": "QMD combines BM25 search, an optional cross-encoder reranker, and LLM expansion.",
                            "reason": "Defines the mechanism.",
                            "start_line": 8,
                            "end_line": 9,
                            "score": 10,
                            "score_reasons": ["definition", "operation"],
                        }
                    ],
                }
            },
        )
        write_json(
            run_dir / "jobs" / "job-0003" / "result.json",
            {
                "result": {
                    "title": "Summary Only",
                    "abstract": "This job has summary text but no snippets.",
                    "bullets": [],
                    "open_questions": [],
                    "confidence": "low",
                }
            },
        )
        return run_dir

    def test_build_synthesis_bundle_collects_summaries_and_selected_snippets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(Path(temp_dir))

            bundle = qwen_farm_synthesis_bundles.build_synthesis_bundle(
                run_dir=run_dir,
                label="candidate",
                max_snippets=10,
                per_file=4,
                created_at="2026-08-24T00:00:00Z",
            )

            self.assertEqual(bundle["label"], "candidate")
            self.assertEqual(bundle["run_id"], "farm-run-test")
            self.assertEqual(bundle["counts"]["jobs_seen"], 3)
            self.assertEqual(bundle["counts"]["items"], 3)
            self.assertEqual(bundle["counts"]["items_with_snippets"], 2)
            self.assertEqual(bundle["counts"]["snippet_candidates"], 3)
            self.assertEqual(bundle["counts"]["snippets_selected"], 2)
            self.assertEqual(bundle["counts"]["duplicates_dropped"], 1)
            self.assertEqual(bundle["items"][0]["summary"]["title"], "Evidence Packs")
            self.assertEqual(bundle["items"][1]["summary"]["bullets"], ["String bullets are normalized."])
            self.assertEqual(bundle["items"][2]["snippets"], [])
            self.assertEqual(bundle["items"][0]["snippets"][0]["id"], "snippet-0001")
            self.assertIn("score_reasons", bundle["items"][0]["snippets"][0])

            serialized = json.dumps(bundle)
            self.assertNotIn("Raw model response should not be copied", serialized)

    def test_caps_are_global_but_snippets_stay_attached_to_source_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(Path(temp_dir))

            bundle = qwen_farm_synthesis_bundles.build_synthesis_bundle(
                run_dir=run_dir,
                max_snippets=1,
                per_file=4,
            )

            self.assertEqual(bundle["counts"]["snippets_selected"], 1)
            snippet_counts = [len(item["snippets"]) for item in bundle["items"]]
            self.assertEqual(snippet_counts, [1, 0, 0])
            self.assertIn("central claim", bundle["items"][0]["snippets"][0]["text"])

    def test_records_missing_malformed_failed_and_empty_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "run"
            write_json(
                run_dir / "farm-status.json",
                {
                    "run_id": "farm-run-empty",
                    "mode": "summarize",
                    "model": "qwen-test:1b",
                    "jobs": [
                        {"job_id": "job-0001", "input_path": "failed.txt", "status": "failed"},
                        {
                            "job_id": "job-0002",
                            "input_path": "missing.txt",
                            "status": "complete",
                            "result_json": "jobs/job-0002/result.json",
                        },
                        {
                            "job_id": "job-0003",
                            "input_path": "malformed.txt",
                            "status": "complete",
                            "result_json": "jobs/job-0003/result.json",
                        },
                        {
                            "job_id": "job-0004",
                            "input_path": "empty.txt",
                            "status": "complete",
                            "result_json": "jobs/job-0004/result.json",
                        },
                    ],
                },
            )
            malformed = run_dir / "jobs" / "job-0003" / "result.json"
            malformed.parent.mkdir(parents=True, exist_ok=True)
            malformed.write_text("{nope", encoding="utf-8")
            write_json(run_dir / "jobs" / "job-0004" / "result.json", {"result": {"title": "Only title"}})

            bundle = qwen_farm_synthesis_bundles.build_synthesis_bundle(run_dir=run_dir)

            self.assertEqual(bundle["counts"]["items"], 0)
            self.assertEqual(bundle["counts"]["jobs_skipped"], 4)
            reasons = {item["reason"] for item in bundle["diagnostics"]["skipped_jobs"]}
            self.assertEqual(
                reasons,
                {"job_not_complete", "missing_result_file", "malformed_result_json", "empty_summary"},
            )
            self.assertIn(
                "No summary items included.",
                qwen_farm_synthesis_bundles.render_synthesis_bundle_markdown(bundle),
            )

    def test_write_synthesis_bundle_uses_safe_label_and_markdown_grouping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(Path(temp_dir))
            bundle = qwen_farm_synthesis_bundles.build_synthesis_bundle(run_dir=run_dir, label="bad label/ok")
            json_path, markdown_path = qwen_farm_synthesis_bundles.write_synthesis_bundle(
                bundle,
                Path(temp_dir) / "bundles",
            )

            self.assertEqual(json_path.name, "bad-label-ok.json")
            self.assertEqual(markdown_path.name, "bad-label-ok.md")
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Synthesis Bundle bad label/ok", markdown)
            self.assertIn("## article-a.txt", markdown)
            self.assertIn("Summary: Summary one should be included", markdown)
            self.assertIn("Evidence:", markdown)


if __name__ == "__main__":
    unittest.main()
