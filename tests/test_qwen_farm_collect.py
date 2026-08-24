from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import qwen_farm, qwen_farm_collect, qwen_farm_schema


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class FarmCollectTests(unittest.TestCase):
    def make_run(self, root: Path) -> Path:
        run_dir = root / ".run" / "farm-results" / "farm-run-collect"
        write_json(
            run_dir / "farm-status.json",
            {
                "run_id": "farm-run-collect",
                "status": "partial",
                "mode": "summarize",
                "agent": "default",
                "model": "qwen-test:1b",
                "jobs": [
                    {
                        "job_id": "job-0001",
                        "input_path": "articles/005-karpathy-llm-wiki-starter-vault.txt",
                        "status": "complete",
                        "warnings": [],
                        "result_md": "jobs/job-0001/result.md",
                        "result_json": "jobs/job-0001/result.json",
                    },
                    {
                        "job_id": "job-0002",
                        "input_path": "articles/009-query-markup-documents.txt",
                        "status": "complete_with_warnings",
                        "warnings": ["snippet_count_under_requested"],
                        "result_json": "jobs/job-0002/result.json",
                    },
                    {
                        "job_id": "job-0003",
                        "input_path": "articles/failed.txt",
                        "status": "failed",
                    },
                    {
                        "job_id": "job-0004",
                        "input_path": "articles/missing.txt",
                        "status": "complete",
                        "result_md": "jobs/job-0004/result.md",
                        "result_json": "jobs/job-0004/result.json",
                    },
                    {
                        "job_id": "job-0005",
                        "input_path": "articles/malformed.txt",
                        "status": "complete",
                        "result_json": "jobs/job-0005/result.json",
                    },
                ],
            },
        )
        (run_dir / "jobs" / "job-0001").mkdir(parents=True)
        (run_dir / "jobs" / "job-0001" / "result.md").write_text("# Karpathy\n\nSummary.", encoding="utf-8")
        write_json(
            run_dir / "jobs" / "job-0001" / "result.json",
            {
                "result": {
                    "title": "LLM Wiki Starter Vault",
                    "abstract": "A compact summary of the starter vault.",
                    "confidence": "high",
                },
                "warnings": [],
            },
        )
        (run_dir / "jobs" / "job-0001" / "raw-response.txt").write_text("raw model text", encoding="utf-8")
        write_json(
            run_dir / "jobs" / "job-0002" / "result.json",
            {
                "result": {
                    "title": "Query Markup Documents",
                    "abstract": "A compact summary of the retrieval workflow.",
                    "confidence": "medium",
                },
                "warnings": ["json_repaired"],
            },
        )
        malformed = run_dir / "jobs" / "job-0005" / "result.json"
        malformed.parent.mkdir(parents=True)
        malformed.write_text("{nope", encoding="utf-8")
        return run_dir

    def test_build_collection_copies_result_artifacts_and_indexes_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = self.make_run(root)
            output_dir = root / "collections"

            collection = qwen_farm_collect.build_collection(
                run_dir=run_dir,
                output_dir=output_dir,
                label="dogfood lite",
                created_at="2026-08-24T00:00:00Z",
            )
            json_path, markdown_path = qwen_farm_collect.write_collection(collection, output_dir)

            self.assertEqual(collection["label"], "dogfood lite")
            self.assertEqual(collection["run_id"], "farm-run-collect")
            self.assertEqual(collection["counts"]["jobs_seen"], 5)
            self.assertEqual(collection["counts"]["items_collected"], 3)
            self.assertEqual(collection["counts"]["markdown_files"], 1)
            self.assertEqual(collection["counts"]["json_files"], 3)
            self.assertEqual(collection["counts"]["jobs_skipped"], 2)
            self.assertEqual(collection["items"][0]["id"], "item-0001")
            self.assertEqual(collection["items"][0]["summary"]["title"], "LLM Wiki Starter Vault")
            self.assertEqual(collection["items"][1]["warnings"], ["snippet_count_under_requested", "json_repaired"])
            self.assertIn("malformed_result_json", collection["items"][2]["diagnostics"])
            self.assertEqual(json_path.name, "farm-collection.json")
            self.assertEqual(markdown_path.name, "FARM_COLLECTION.md")

            collection_dir = output_dir / "dogfood-lite"
            self.assertTrue((collection_dir / "items" / "item-0001-005-karpathy-llm-wiki-starter-vault.md").exists())
            self.assertTrue((collection_dir / "items" / "item-0001-005-karpathy-llm-wiki-starter-vault.json").exists())
            self.assertTrue((collection_dir / "items" / "item-0002-009-query-markup-documents.json").exists())
            self.assertFalse((collection_dir / "items" / "raw-response.txt").exists())
            self.assertFalse((collection_dir / "items" / "item-0003-failed.json").exists())
            self.assertIn("## Diagnostics", markdown_path.read_text(encoding="utf-8"))

    def test_empty_collection_still_writes_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "run"
            write_json(
                run_dir / "farm-status.json",
                {
                    "run_id": "farm-run-empty",
                    "mode": "summarize",
                    "agent": "default",
                    "model": "qwen-test:1b",
                    "jobs": [
                        {"job_id": "job-0001", "input_path": "running.txt", "status": "running"},
                        {"job_id": "job-0002", "input_path": "failed.txt", "status": "failed"},
                    ],
                },
            )

            collection = qwen_farm_collect.build_collection(run_dir=run_dir, output_dir=root / "collections")
            json_path, markdown_path = qwen_farm_collect.write_collection(collection, root / "collections")

            self.assertEqual(collection["counts"]["items_collected"], 0)
            self.assertEqual(collection["counts"]["jobs_skipped"], 2)
            self.assertIn("No items collected.", markdown_path.read_text(encoding="utf-8"))
            self.assertTrue(json_path.exists())

    def test_known_run_id_can_feed_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = self.make_run(root)
            qwen_farm.write_run_index(root, [{"run_id": "farm-run-collect", "path": str(run_dir)}])

            resolved = qwen_farm.resolve_run_reference(root, "farm-run-collect")
            collection = qwen_farm_collect.build_collection(
                run_dir=resolved,
                output_dir=root / "collections",
            )

            self.assertEqual(collection["run_id"], "farm-run-collect")
            self.assertEqual(collection["counts"]["items_collected"], 3)

    def test_collection_schema_validates_and_auto_detects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = self.make_run(root)
            collection = qwen_farm_collect.build_collection(
                run_dir=run_dir,
                output_dir=root / "collections",
                created_at="2026-08-24T00:00:00Z",
            )
            json_path, _markdown_path = qwen_farm_collect.write_collection(collection, root / "collections")

            result = qwen_farm_schema.validate_artifact(ROOT, json_path)

            self.assertTrue(result["valid"], "\n".join(result["errors"]))
            self.assertEqual(result["schema"]["path"], "schemas/farm-collection.schema.json")
            self.assertTrue(result["schema"]["detected"])

    def test_safe_item_stem_keeps_sequence_prefix_and_slug(self) -> None:
        stem = qwen_farm_collect.safe_item_stem(
            item_id="item-0007",
            input_path="folder/Hello There!!.txt",
        )

        self.assertEqual(stem, "item-0007-hello-there")


if __name__ == "__main__":
    unittest.main()
