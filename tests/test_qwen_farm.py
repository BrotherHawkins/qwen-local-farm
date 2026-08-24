from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import qwen_farm
from src.qwen_farm_model import FarmModelResult


def fake_processor(**kwargs: object) -> FarmModelResult:
    file_path = str(kwargs["file_path"])
    if file_path == "fail.txt":
        raise RuntimeError("planned failure")
    payload = {
        "title": file_path,
        "abstract": f"Summary for {file_path}",
        "bullets": ["one", "two"],
        "open_questions": [],
        "confidence": "high",
    }
    return FarmModelResult(
        payload=payload,
        markdown=f"# {file_path}\n\nSummary.",
        raw_response='{"title":"ok"}',
        structured_valid=True,
        warnings=[],
    )


class FarmRunTests(unittest.TestCase):
    def test_run_farm_happy_path_creates_status_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")
            (root / "input" / "b.txt").write_text("B", encoding="utf-8")
            output = root / "results"

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=output,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )

            run_dir = Path(status["output"]["path"])
            self.assertEqual(status["status"], "complete")
            self.assertEqual(status["counts"]["total"], 2)
            self.assertTrue((run_dir / "farm-status.json").exists())
            self.assertTrue((run_dir / "FARM_STATUS.md").exists())
            self.assertTrue((run_dir / "jobs/job-0001/result.md").exists())
            self.assertTrue((run_dir / "jobs/job-0001/result.json").exists())
            self.assertTrue((run_dir / "jobs/job-0001/raw-response.txt").exists())
            self.assertEqual(status["jobs"][0]["result_json"], "jobs/job-0001/result.json")

    def test_run_farm_skips_vendor_and_binary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input" / "node_modules").mkdir(parents=True)
            (root / "input" / "keep.py").write_text("print('ok')", encoding="utf-8")
            (root / "input" / "node_modules" / "dep.txt").write_text("skip", encoding="utf-8")
            (root / "input" / "binary.dat").write_bytes(b"a\x00b")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )

            self.assertEqual(status["counts"]["total"], 1)
            self.assertEqual(status["counts"]["skipped"], 2)
            self.assertIn("node_modules/dep.txt", status["skipped_files"])
            self.assertIn("binary.dat", status["skipped_files"])

    def test_run_farm_continues_after_one_failed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")
            (root / "input" / "fail.txt").write_text("fail", encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )

            self.assertEqual(status["status"], "partial")
            self.assertEqual(status["counts"]["complete"], 1)
            self.assertEqual(status["counts"]["failed"], 1)

    def test_list_and_status_text_find_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )

            listing = qwen_farm.list_runs_text(root)
            overview = qwen_farm.status_text(root)
            one_run = qwen_farm.status_text(root, status["run_id"])

            self.assertIn(status["run_id"], listing)
            self.assertIn("# Farm Overview", overview)
            self.assertIn(f"# Farm Run {status['run_id']}", one_run)

    def test_list_finds_runs_written_to_custom_output_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")
            output = root / "custom-results"

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=output,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )

            self.assertIn(status["run_id"], qwen_farm.list_runs_text(root))
            self.assertIn(status["run_id"], qwen_farm.status_text(root, status["run_id"]))

    def test_list_runs_orders_by_updated_at_across_output_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")

            older = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )
            newer = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=root / "custom-results",
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )

            older_path = Path(older["output"]["path"]) / "farm-status.json"
            newer_path = Path(newer["output"]["path"]) / "farm-status.json"
            older_data = qwen_farm.read_json(older_path)
            newer_data = qwen_farm.read_json(newer_path)
            older_data["updated_at"] = "2026-08-23T10:00:00Z"
            newer_data["updated_at"] = "2026-08-23T11:00:00Z"
            older_path.write_text(json.dumps(older_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            newer_path.write_text(json.dumps(newer_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            listing = qwen_farm.list_runs_text(root).splitlines()

            self.assertTrue(listing[1].startswith(newer["run_id"]))
            self.assertTrue(listing[2].startswith(older["run_id"]))
