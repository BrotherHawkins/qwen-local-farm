from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import sift_farm_snippet_packs


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class SnippetPackTests(unittest.TestCase):
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
                        "result_json": "jobs/job-0001/result.json",
                    },
                    {
                        "job_id": "job-0002",
                        "input_path": "article-b.txt",
                        "status": "complete_with_warnings",
                        "result_json": "jobs/job-0002/result.json",
                    },
                ],
            },
        )
        write_json(
            run_dir / "jobs" / "job-0001" / "result.json",
            {
                "result": {
                    "abstract": "Do not persist full summaries in snippet packs.",
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
                            "text": "A lower-scored operational detail still belongs if the budget allows.",
                            "reason": "Operational caveat.",
                            "score": 4,
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
                    "snippets": [
                        {
                            "text": "QMD combines BM25 search, an optional cross-encoder reranker, and LLM expansion.",
                            "reason": "Defines the mechanism.",
                            "start_line": 8,
                            "end_line": 9,
                            "score": 10,
                            "score_reasons": ["definition", "operation"],
                        }
                    ]
                }
            },
        )
        return run_dir

    def test_build_snippet_pack_collects_compact_verified_snippets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(Path(temp_dir))

            pack = sift_farm_snippet_packs.build_snippet_pack(
                run_dir=run_dir,
                label="candidate",
                max_snippets=10,
                per_file=4,
                created_at="2026-08-24T00:00:00Z",
            )

            self.assertEqual(pack["label"], "candidate")
            self.assertEqual(pack["run_id"], "farm-run-test")
            self.assertEqual(pack["counts"]["jobs_seen"], 2)
            self.assertEqual(pack["counts"]["jobs_with_snippets"], 2)
            self.assertEqual(pack["counts"]["candidates"], 3)
            self.assertEqual(pack["counts"]["selected"], 3)
            self.assertEqual(pack["budget"]["schema_version"], 1)
            self.assertIsNone(pack["budget"]["effective_max_chars"])
            self.assertFalse(pack["budget"]["was_capped"])
            self.assertGreater(pack["budget"]["output"]["chars"], 0)
            self.assertGreater(pack["budget"]["output"]["estimated_tokens"], 0)
            self.assertEqual(pack["snippets"][0]["id"], "snippet-0001")
            self.assertIn(pack["snippets"][0]["input_path"], {"article-a.txt", "article-b.txt"})
            self.assertIn("score_reasons", pack["snippets"][0])

            serialized = json.dumps(pack)
            self.assertNotIn("Do not persist full summaries", serialized)
            self.assertNotIn("Raw model response should not be copied", serialized)

    def test_dedupes_and_applies_caps_with_file_diversity(self) -> None:
        snippets = [
            {"input_path": "a.txt", "job_id": "job-1", "text": "High value claim.", "score": 100},
            {"input_path": "a.txt", "job_id": "job-1", "text": "Second high value claim.", "score": 99},
            {"input_path": "a.txt", "job_id": "job-1", "text": "High value claim. ", "score": 90},
            {"input_path": "b.txt", "job_id": "job-2", "text": "B side evidence.", "score": 1},
            {"input_path": "c.txt", "job_id": "job-3", "text": "C side evidence.", "score": 1},
        ]

        deduped, duplicates = sift_farm_snippet_packs.dedupe_snippets(snippets)
        selected = sift_farm_snippet_packs.apply_caps(deduped, max_snippets=3, per_file=4)
        tiny_budget = sift_farm_snippet_packs.apply_caps(deduped, max_snippets=1, per_file=4)

        self.assertEqual(duplicates, 1)
        self.assertEqual([item["input_path"] for item in selected], ["a.txt", "b.txt", "c.txt"])
        self.assertEqual([item["text"] for item in selected], ["High value claim.", "B side evidence.", "C side evidence."])
        self.assertEqual([item["text"] for item in tiny_budget], ["High value claim."])

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
            write_json(run_dir / "jobs" / "job-0004" / "result.json", {"result": {"snippets": []}})

            pack = sift_farm_snippet_packs.build_snippet_pack(run_dir=run_dir)

            self.assertEqual(pack["counts"]["selected"], 0)
            self.assertEqual(pack["counts"]["jobs_skipped"], 4)
            reasons = {item["reason"] for item in pack["diagnostics"]["skipped_jobs"]}
            self.assertEqual(
                reasons,
                {"job_not_complete", "missing_result_file", "malformed_result_json", "no_selected_snippets"},
            )
            self.assertIn("No snippets selected.", sift_farm_snippet_packs.render_snippet_pack_markdown(pack))

    def test_write_snippet_pack_uses_safe_label_and_markdown_grouping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(Path(temp_dir))
            pack = sift_farm_snippet_packs.build_snippet_pack(run_dir=run_dir, label="bad label/ok")
            json_path, markdown_path = sift_farm_snippet_packs.write_snippet_pack(pack, Path(temp_dir) / "packs")

            self.assertEqual(json_path.name, "bad-label-ok.json")
            self.assertEqual(markdown_path.name, "bad-label-ok.md")
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Snippet Pack bad label/ok", markdown)
            self.assertIn("## article-a.txt", markdown)
            self.assertIn("Why it matters:", markdown)
            self.assertIn("Budget:", markdown)

    def test_invalid_budget_options_fail_before_building_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(Path(temp_dir))

            with self.assertRaisesRegex(ValueError, "--max-chars"):
                sift_farm_snippet_packs.build_snippet_pack(run_dir=run_dir, max_chars=0)
            with self.assertRaisesRegex(ValueError, "--max-estimated-tokens"):
                sift_farm_snippet_packs.build_snippet_pack(run_dir=run_dir, max_estimated_tokens=0)
            with self.assertRaisesRegex(ValueError, "--chars-per-token"):
                sift_farm_snippet_packs.build_snippet_pack(run_dir=run_dir, chars_per_token=0)

    def test_character_budget_drops_whole_snippets_when_feasible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(Path(temp_dir))
            full = sift_farm_snippet_packs.build_snippet_pack(run_dir=run_dir)
            max_chars = full["budget"]["output"]["chars"] - 120

            capped = sift_farm_snippet_packs.build_snippet_pack(run_dir=run_dir, max_chars=max_chars)

            self.assertTrue(capped["budget"]["was_capped"])
            self.assertTrue(capped["budget"]["fit"])
            self.assertLessEqual(capped["budget"]["output"]["chars"], max_chars)
            self.assertGreater(capped["budget"]["dropped"]["snippets"], 0)
            remaining_texts = {snippet["text"] for snippet in capped["snippets"]}
            original_texts = {snippet["text"] for snippet in full["snippets"]}
            self.assertTrue(remaining_texts.issubset(original_texts))
            self.assertEqual(capped["counts"]["selected"], len(capped["snippets"]))

    def test_estimated_token_budget_resolves_to_character_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(Path(temp_dir))

            capped = sift_farm_snippet_packs.build_snippet_pack(
                run_dir=run_dir,
                max_estimated_tokens=160,
                chars_per_token=4.0,
            )

            self.assertEqual(capped["budget"]["effective_max_chars"], 640)
            self.assertLessEqual(capped["budget"]["output"]["chars"], 640)
            self.assertLessEqual(capped["budget"]["output"]["estimated_tokens"], 160)


if __name__ == "__main__":
    unittest.main()
