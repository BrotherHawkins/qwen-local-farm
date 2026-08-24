from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from src import qwen_farm
from src.qwen_farm_model import FarmModelResult


class FakeTokenCounter:
    tokenizer_id = "fake/qwen"
    counts_are_estimated = False

    def count_tokens(self, text: str) -> int:
        return len(text.split())


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


def warning_processor(**kwargs: object) -> FarmModelResult:
    result = fake_processor(**kwargs)
    return FarmModelResult(
        payload=result.payload,
        markdown=result.markdown,
        raw_response=result.raw_response,
        structured_valid=result.structured_valid,
        warnings=["chunk_warning"],
    )


def snippet_processor(**kwargs: object) -> FarmModelResult:
    file_path = str(kwargs["file_path"])
    content = str(kwargs["content"])
    snippet_request = kwargs.get("snippet_request")
    requested = int(snippet_request.get("requested_count", 0)) if isinstance(snippet_request, dict) else 0
    snippets = []
    if requested and "alpha exact evidence" in content:
        snippets.append(
            {
                "text": "alpha exact evidence",
                "reason": "Shows the alpha claim.",
                "source_path": file_path,
                "start_line": 1,
                "end_line": 1,
                "char_start": 0,
                "char_end": 20,
            }
        )
    if requested and "beta exact evidence" in content:
        snippets.append(
            {
                "text": "beta exact evidence",
                "reason": "Shows the beta claim.",
                "source_path": file_path,
                "start_line": 1,
                "end_line": 1,
                "char_start": 0,
                "char_end": 19,
            }
        )
    if file_path == "long.txt":
        snippets.append(
            {
                "text": "invented reduce quote",
                "reason": "This must not survive final selection.",
                "source_path": file_path,
            }
        )

    payload = {
        "title": file_path,
        "abstract": f"Summary for {file_path}",
        "bullets": ["one", "two"],
        "open_questions": [],
        "confidence": "high",
    }
    if snippets:
        payload["snippets"] = snippets
    return FarmModelResult(
        payload=payload,
        markdown=f"# {file_path}\n\nSummary.",
        raw_response="raw",
        structured_valid=True,
        warnings=[],
    )


class FarmRunTests(unittest.TestCase):
    def assertTimingComplete(self, timing: dict[str, object]) -> None:
        self.assertIsInstance(timing.get("started_at"), str)
        self.assertIsInstance(timing.get("completed_at"), str)
        self.assertIsInstance(timing.get("duration_ms"), int)
        self.assertGreaterEqual(int(timing["duration_ms"]), 0)

    def latest_status(self, root: Path) -> dict[str, object]:
        status_paths = list((root / ".run" / "farm").glob("farm-run-*/farm-status.json"))
        self.assertTrue(status_paths)
        return qwen_farm.read_json(max(status_paths, key=lambda path: path.stat().st_mtime))

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
            self.assertTrue((run_dir / "farm-config.resolved.json").exists())
            self.assertTrue((run_dir / "timing-summary.json").exists())
            self.assertTrue((run_dir / "TIMING_SUMMARY.md").exists())
            self.assertTrue((run_dir / "jobs/job-0001/result.md").exists())
            self.assertTrue((run_dir / "jobs/job-0001/result.json").exists())
            self.assertTrue((run_dir / "jobs/job-0001/raw-response.txt").exists())
            self.assertEqual(status["jobs"][0]["result_json"], "jobs/job-0001/result.json")
            self.assertFalse(status["jobs"][0]["chunking"]["enabled"])
            self.assertEqual(status["runtime"]["profile"], "local-8gb")
            self.assertEqual(status["runtime"]["resource_mode"]["requested"], "auto")
            self.assertEqual(status["runtime"]["resource_mode"]["effective"], "gpu")
            self.assertEqual(status["runtime"]["model"], "qwen-test:1b")
            self.assertEqual(status["runtime"]["failure_policy"]["max_attempts"], 2)
            self.assertEqual(status["runtime"]["failure_policy"]["per_file_timeout_seconds"], 600)
            self.assertEqual(status["runtime"]["failure_policy"]["chunk_max_attempts"], 2)
            self.assertEqual(status["runtime"]["failure_policy"]["reduce_max_attempts"], 2)
            self.assertTimingComplete(status["timing"])
            self.assertIsInstance(status["jobs"][0]["timing"].get("queued_at"), str)
            self.assertTimingComplete(status["jobs"][0]["timing"])
            self.assertIn("Max attempts: `2`", (run_dir / "FARM_STATUS.md").read_text(encoding="utf-8"))

            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")
            self.assertEqual(result["timing"]["calls"][0]["kind"], "single")
            self.assertTimingComplete(result["timing"]["calls"][0])

            timing_summary = qwen_farm.read_json(run_dir / "timing-summary.json")
            self.assertEqual(timing_summary["run_id"], status["run_id"])
            self.assertEqual(timing_summary["resource_mode"]["effective"], "gpu")
            self.assertEqual(timing_summary["aggregate_by_call_kind"]["single"]["count"], 2)

    def test_default_summarize_processor_sets_fast_model_options(self) -> None:
        seen: dict[str, object] = {}

        class CapturingClient:
            def __init__(self, base_url: str, model: str, options: dict[str, object]) -> None:
                seen["base_url"] = base_url
                seen["model"] = model
                seen["options"] = options

        def fake_process(**kwargs: object) -> FarmModelResult:
            return fake_processor(**kwargs)

        with patch.object(qwen_farm, "OllamaChatClient", CapturingClient), patch.object(
            qwen_farm, "process_file_with_model", fake_process
        ):
            qwen_farm.default_model_processor(
                mode="summarize",
                file_path="a.txt",
                content="A",
                instructions=None,
                agent={
                    "id": "default",
                    "model": "qwen-test:1b",
                    "system_prompt": "",
                    "options": {"num_ctx": 8192, "num_predict": 256},
                },
                ollama_base_url="http://127.0.0.1:11434",
                timeout=1,
            )

        options = seen["options"]
        assert isinstance(options, dict)
        self.assertEqual(options["num_ctx"], 8192)
        self.assertEqual(options["num_predict"], 256)
        self.assertEqual(options["num_batch"], qwen_farm.SUMMARY_NUM_BATCH)

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

    def test_single_pass_retry_obeys_max_attempts_and_keeps_failed_call_timing(self) -> None:
        attempts = 0

        def flaky_processor(**kwargs: object) -> FarmModelResult:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("transient single-pass failure")
            return fake_processor(**kwargs)

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
                max_attempts=2,
                model_processor=flaky_processor,
            )

            run_dir = Path(status["output"]["path"])
            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")

            self.assertEqual(status["status"], "complete")
            self.assertEqual(attempts, 2)
            self.assertEqual([call["status"] for call in result["timing"]["calls"]], ["failed", "complete"])
            self.assertIn("transient single-pass failure", result["timing"]["calls"][0]["error"])

    def test_prompt_mode_retry_obeys_max_attempts(self) -> None:
        attempts = 0

        def always_failing_processor(**_kwargs: object) -> FarmModelResult:
            nonlocal attempts
            attempts += 1
            raise RuntimeError("prompt failure")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="prompt",
                instructions="Do the thing.",
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                max_attempts=1,
                model_processor=always_failing_processor,
            )

            self.assertEqual(status["status"], "failed")
            self.assertEqual(attempts, 1)
            self.assertIn("prompt failure", status["jobs"][0]["error"])

    def test_invalid_direct_failure_policy_override_fails_before_run_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")
            output = root / "results"

            with self.assertRaisesRegex(ValueError, "--max-attempts"):
                qwen_farm.run_farm(
                    root=root,
                    input_folder=root / "input",
                    output_dir=output,
                    mode="summarize",
                    instructions=None,
                    agent_id="default",
                    default_model="qwen-test:1b",
                    ollama_base_url="http://127.0.0.1:11434",
                    max_attempts=0,
                    model_processor=fake_processor,
                )

            self.assertFalse(output.exists())

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
            self.assertIn("## Timing", one_run)
            self.assertIn("## Runtime", one_run)
            self.assertIn("Profile: `local-8gb`", one_run)

    def test_status_json_returns_empty_overview_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            status = qwen_farm.status_json(root)

            self.assertEqual(status["scope"], "overview")
            self.assertEqual(status["counts"], {"runs": 0})
            self.assertEqual(status["runs"], [])

    def test_status_json_returns_overview_and_single_run_envelopes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")

            run_status = qwen_farm.run_farm(
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

            overview = qwen_farm.status_json(root)
            one_run = qwen_farm.status_json(root, run_status["run_id"])

            self.assertEqual(overview["schema_version"], 1)
            self.assertEqual(overview["scope"], "overview")
            self.assertEqual(overview["counts"], {"runs": 1})
            self.assertEqual(overview["runs"][0]["run_id"], run_status["run_id"])
            self.assertEqual(one_run["schema_version"], 1)
            self.assertEqual(one_run["scope"], "run")
            self.assertEqual(one_run["run_id"], run_status["run_id"])
            self.assertEqual(one_run["run"]["run_id"], run_status["run_id"])

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

    def test_resolve_run_reference_accepts_existing_run_directory_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "runs" / "farm-run-path"
            run_dir.mkdir(parents=True)
            qwen_farm.write_json(run_dir / "farm-status.json", {"run_id": "farm-run-path"})

            self.assertEqual(qwen_farm.resolve_run_reference(root, str(run_dir)), run_dir)

    def test_resolve_run_reference_accepts_indexed_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "runs" / "farm-run-indexed"
            run_dir.mkdir(parents=True)
            qwen_farm.write_json(run_dir / "farm-status.json", {"run_id": "farm-run-indexed"})
            qwen_farm.remember_run(root, "farm-run-indexed", run_dir)

            self.assertEqual(qwen_farm.resolve_run_reference(root, "farm-run-indexed"), run_dir)

    def test_resolve_run_reference_prefers_existing_path_before_run_id_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path_run = root / "runs" / "path-run"
            indexed_run = root / "runs" / "indexed-run"
            path_run.mkdir(parents=True)
            indexed_run.mkdir(parents=True)
            qwen_farm.write_json(path_run / "farm-status.json", {"run_id": "path-run"})
            qwen_farm.write_json(indexed_run / "farm-status.json", {"run_id": "indexed-run"})
            qwen_farm.remember_run(root, str(path_run), indexed_run)

            self.assertEqual(qwen_farm.resolve_run_reference(root, str(path_run)), path_run)

    def test_resolve_run_reference_rejects_stale_index_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing_run = root / "runs" / "missing"
            qwen_farm.remember_run(root, "farm-run-stale", missing_run)

            with self.assertRaisesRegex(FileNotFoundError, "farm-run-stale"):
                qwen_farm.resolve_run_reference(root, "farm-run-stale")

    def test_resolve_run_reference_rejects_directory_without_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "runs" / "farm-run-no-status"
            run_dir.mkdir(parents=True)

            with self.assertRaisesRegex(FileNotFoundError, "missing farm-status.json"):
                qwen_farm.resolve_run_reference(root, str(run_dir))

    def test_resolve_run_reference_rejects_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_file = root / "not-a-run.txt"
            run_file.write_text("not a directory", encoding="utf-8")

            with self.assertRaisesRegex(FileNotFoundError, "not a directory"):
                qwen_farm.resolve_run_reference(root, str(run_file))

    def test_resolve_run_reference_rejects_unknown_reference_with_list_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with self.assertRaisesRegex(FileNotFoundError, "farm list"):
                qwen_farm.resolve_run_reference(root, "farm-run-missing")

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

    def test_summarize_chunks_large_files_and_reduces_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            content = "\n\n".join(["alpha " * 600, "beta " * 600, "gamma " * 600])
            (root / "input" / "long.txt").write_text(content, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions="Summarize everything.",
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )

            run_dir = Path(status["output"]["path"])
            job = status["jobs"][0]
            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")
            chunk_result = qwen_farm.read_json(run_dir / "jobs/job-0001/chunk-results/chunk-0001/result.json")

            self.assertEqual(status["status"], "complete")
            self.assertTrue(job["chunking"]["enabled"])
            self.assertEqual(job["chunking"]["coverage"], "full")
            self.assertGreater(job["chunking"]["chunk_count"], 1)
            self.assertTrue((run_dir / "jobs/job-0001/chunks/chunk-0001.txt").exists())
            self.assertTrue((run_dir / "jobs/job-0001/chunk-results/chunk-0001/result.json").exists())
            self.assertTrue(result["chunking"]["enabled"])
            self.assertEqual(result["chunking"]["coverage"], "full")
            self.assertEqual(result["result"]["title"], "long.txt")
            kinds = [call["kind"] for call in result["timing"]["calls"]]
            self.assertIn("chunk_map", kinds)
            self.assertIn("reduce", kinds)
            self.assertEqual(chunk_result["timing"]["kind"], "chunk_map")
            self.assertTimingComplete(chunk_result["timing"])

    def test_summarize_uses_resolved_chunk_budget(self) -> None:
        observed_inputs: list[tuple[int, int]] = []

        def budget_asserting_processor(**kwargs: object) -> FarmModelResult:
            content = str(kwargs["content"])
            summary_max_input_chars = int(kwargs["summary_max_input_chars"])
            observed_inputs.append((len(content), summary_max_input_chars))
            self.assertLessEqual(len(content), summary_max_input_chars)
            return fake_processor(**kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "medium.txt").write_text("x" * 1200, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_chars=500,
                reduce_chars=700,
                model_processor=budget_asserting_processor,
            )

            run_dir = Path(status["output"]["path"])
            resolved = qwen_farm.read_json(run_dir / "farm-config.resolved.json")

            self.assertTrue(status["jobs"][0]["chunking"]["enabled"])
            self.assertEqual(status["jobs"][0]["chunking"]["chunk_count"], 3)
            self.assertEqual(status["runtime"]["summarize"]["chunk_chars"], 500)
            self.assertEqual(resolved["summarize"]["chunk_chars"], 500)
            self.assertTrue(observed_inputs)

    def test_chunked_summary_records_heading_ancestry_and_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            content = "\n\n".join(
                [
                    "# Article Title",
                    "Intro " * 20,
                    "## First Section",
                    "Alpha " * 30,
                    "## Second Section",
                    "Beta " * 30,
                ]
            )
            (root / "input" / "article.md").write_text(content, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_chars=140,
                reduce_chars=700,
                chunk_overlap_chars=25,
                model_processor=fake_processor,
            )

            run_dir = Path(status["output"]["path"])
            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")
            chunk_records = result["chunking"]["chunks"]
            overlapped = next(chunk for chunk in chunk_records if chunk["overlap"]["source"] == "previous")
            chunk_result = qwen_farm.read_json(run_dir / overlapped["result_json"])
            chunk_input = (run_dir / overlapped["input"]).read_text(encoding="utf-8")
            status_md = (run_dir / "FARM_STATUS.md").read_text(encoding="utf-8")

            self.assertTrue(status["runtime"]["summarize"]["preserve_heading_ancestry"])
            self.assertEqual(status["runtime"]["summarize"]["chunk_overlap_chars"], 25)
            self.assertIn("Preserve heading ancestry: `True`", status_md)
            self.assertIn("Chunk overlap chars: `25`", status_md)
            self.assertTrue(overlapped["heading_ancestry"])
            self.assertLessEqual(overlapped["overlap"]["before_chars"], 25)
            self.assertEqual(chunk_result["input"]["heading_ancestry"], overlapped["heading_ancestry"])
            self.assertEqual(chunk_result["input"]["overlap"]["source"], "previous")
            self.assertIn("Heading context:", chunk_input)
            self.assertIn("Overlap context from previous source text", chunk_input)
            self.assertIn("Chunk text:", chunk_input)

    def test_running_chunk_status_is_visible_during_chunk_map_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "long.txt").write_text(" ".join(f"word{index}" for index in range(80)), encoding="utf-8")
            snapshots: list[dict[str, object]] = []

            def observing_processor(**kwargs: object) -> FarmModelResult:
                if str(kwargs["file_path"]).endswith("#chunk-0001"):
                    snapshots.append(self.latest_status(root))
                return fake_processor(**kwargs)

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_strategy="token",
                chunk_tokens=30,
                reduce_tokens=1000,
                token_counter=FakeTokenCounter(),
                max_attempts=1,
                model_processor=observing_processor,
            )

            self.assertEqual(status["status"], "complete")
            self.assertTrue(snapshots)
            job = snapshots[0]["jobs"][0]  # type: ignore[index]
            progress = job["progress"]  # type: ignore[index]
            current_call = progress["current_call"]
            self.assertEqual(job["status"], "running")  # type: ignore[index]
            self.assertTrue(job["chunking"]["enabled"])  # type: ignore[index]
            self.assertGreater(job["chunking"]["chunk_count"], 1)  # type: ignore[index]
            self.assertEqual(progress["phase"], "chunk_map")
            self.assertEqual(progress["chunks"]["current"], "chunk-0001")
            self.assertEqual(current_call["kind"], "chunk_map")
            self.assertEqual(current_call["status"], "running")
            self.assertEqual(job["timing"]["calls"][-1]["status"], "running")  # type: ignore[index]

    def test_running_reduce_status_is_visible_during_reduce_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "long.txt").write_text(" ".join(f"word{index}" for index in range(80)), encoding="utf-8")
            snapshots: list[dict[str, object]] = []

            def observing_processor(**kwargs: object) -> FarmModelResult:
                if str(kwargs["file_path"]) == "long.txt":
                    snapshots.append(self.latest_status(root))
                return fake_processor(**kwargs)

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_strategy="token",
                chunk_tokens=30,
                reduce_tokens=1000,
                token_counter=FakeTokenCounter(),
                max_attempts=1,
                model_processor=observing_processor,
            )

            self.assertEqual(status["status"], "complete")
            self.assertTrue(snapshots)
            job = snapshots[0]["jobs"][0]  # type: ignore[index]
            progress = job["progress"]  # type: ignore[index]
            current_call = progress["current_call"]
            self.assertEqual(progress["phase"], "reduce")
            self.assertEqual(progress["chunks"]["complete"], progress["chunks"]["total"])
            self.assertEqual(progress["reduce"]["generation"], 1)
            self.assertEqual(progress["reduce"]["batch_index"], 1)
            self.assertEqual(current_call["kind"], "reduce")
            self.assertEqual(current_call["status"], "running")

    def test_retried_chunk_attempts_are_visible_while_retry_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "long.txt").write_text(" ".join(f"word{index}" for index in range(80)), encoding="utf-8")
            snapshots: list[dict[str, object]] = []
            calls: dict[str, int] = {}

            def flaky_processor(**kwargs: object) -> FarmModelResult:
                file_path = str(kwargs["file_path"])
                calls[file_path] = calls.get(file_path, 0) + 1
                if file_path.endswith("#chunk-0002") and calls[file_path] == 1:
                    raise RuntimeError("transient chunk failure")
                if file_path.endswith("#chunk-0002") and calls[file_path] == 2:
                    snapshots.append(self.latest_status(root))
                return fake_processor(**kwargs)

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_strategy="token",
                chunk_tokens=30,
                reduce_tokens=1000,
                token_counter=FakeTokenCounter(),
                max_attempts=1,
                chunk_max_attempts=2,
                reduce_max_attempts=1,
                model_processor=flaky_processor,
            )

            self.assertEqual(status["status"], "complete")
            self.assertTrue(snapshots)
            job = snapshots[0]["jobs"][0]  # type: ignore[index]
            chunk_two_calls = [
                call
                for call in job["timing"]["calls"]  # type: ignore[index]
                if call.get("chunk_id") == "chunk-0002"
            ]
            self.assertEqual([call["status"] for call in chunk_two_calls], ["failed", "running"])
            self.assertEqual([call["attempt"] for call in chunk_two_calls], [1, 2])

    def test_token_strategy_can_single_pass_long_character_input(self) -> None:
        observed_inputs: list[tuple[int, int]] = []

        def observing_processor(**kwargs: object) -> FarmModelResult:
            content = str(kwargs["content"])
            summary_max_input_chars = int(kwargs["summary_max_input_chars"])
            observed_inputs.append((len(content), summary_max_input_chars))
            self.assertEqual(summary_max_input_chars, len(content))
            return fake_processor(**kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            content = "longword" * 1000
            (root / "input" / "long-chars.txt").write_text(content, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_strategy="token",
                chunk_chars=500,
                chunk_tokens=50,
                reduce_tokens=50,
                token_counter=FakeTokenCounter(),
                model_processor=observing_processor,
            )

            run_dir = Path(status["output"]["path"])
            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")

            self.assertFalse(status["jobs"][0]["chunking"]["enabled"])
            self.assertEqual(result["chunking"]["strategy"], "single-pass-token")
            self.assertEqual(result["chunking"]["tokenizer"], "fake/qwen")
            self.assertFalse(result["chunking"]["counts_are_estimated"])
            self.assertEqual(observed_inputs[0][0], len(content))

    def test_token_strategy_chunks_and_records_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            content = "\n\n".join([" ".join(f"word{index}" for index in range(30)) for _ in range(3)])
            (root / "input" / "token-long.txt").write_text(content, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_strategy="token",
                chunk_chars=500,
                chunk_tokens=25,
                reduce_tokens=200,
                token_counter=FakeTokenCounter(),
                model_processor=fake_processor,
            )

            run_dir = Path(status["output"]["path"])
            job = status["jobs"][0]
            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")

            self.assertTrue(job["chunking"]["enabled"])
            self.assertEqual(job["chunking"]["strategy"], "paragraph-token")
            self.assertEqual(job["chunking"]["tokenizer"], "fake/qwen")
            self.assertEqual(result["chunking"]["strategy"], "paragraph-token")
            self.assertEqual(result["chunking"]["chunk_tokens"], 25)
            self.assertFalse(result["chunking"]["counts_are_estimated"])
            self.assertGreater(result["chunking"]["chunk_count"], 1)
            for chunk in result["chunking"]["chunks"]:
                self.assertIsInstance(chunk["chars"], int)
                self.assertLessEqual(chunk["tokens"], 25)

    def test_token_strategy_loads_counter_before_run_folder_creation(self) -> None:
        def failing_loader(**kwargs: object) -> FakeTokenCounter:
            raise RuntimeError("missing tokenizer")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")
            output = root / "results"

            with self.assertRaisesRegex(RuntimeError, "missing tokenizer"):
                qwen_farm.run_farm(
                    root=root,
                    input_folder=root / "input",
                    output_dir=output,
                    mode="summarize",
                    instructions=None,
                    agent_id="default",
                    default_model="qwen-test:1b",
                    ollama_base_url="http://127.0.0.1:11434",
                    chunk_strategy="token",
                    chunk_tokens=100,
                    reduce_tokens=100,
                    token_counter_loader=failing_loader,
                    model_processor=fake_processor,
                )

            self.assertFalse(output.exists())

    def test_token_reduce_budget_overflow_fails_before_reduce_call(self) -> None:
        calls: list[str] = []

        def recording_processor(**kwargs: object) -> FarmModelResult:
            calls.append(str(kwargs["file_path"]))
            return fake_processor(**kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            content = "\n\n".join([" ".join(f"word{index}" for index in range(30)) for _ in range(2)])
            (root / "input" / "token-long.txt").write_text(content, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_strategy="token",
                chunk_tokens=25,
                reduce_tokens=3,
                token_counter=FakeTokenCounter(),
                model_processor=recording_processor,
                max_attempts=1,
            )

            self.assertEqual(status["status"], "failed")
            self.assertIn("exceeds reduce token budget", status["jobs"][0]["error"])
            self.assertTrue(any("#chunk-" in call for call in calls))
            self.assertFalse(any("#reduce" in call for call in calls))

    def test_chunk_retry_recovers_without_rerunning_prior_chunks(self) -> None:
        calls: dict[str, int] = {}

        def flaky_chunk_processor(**kwargs: object) -> FarmModelResult:
            file_path = str(kwargs["file_path"])
            calls[file_path] = calls.get(file_path, 0) + 1
            if file_path.endswith("#chunk-0002") and calls[file_path] == 1:
                raise RuntimeError("transient chunk failure")
            return fake_processor(**kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            content = " ".join(f"word{index}" for index in range(80))
            (root / "input" / "long.txt").write_text(content, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_strategy="token",
                chunk_tokens=30,
                reduce_tokens=1000,
                token_counter=FakeTokenCounter(),
                max_attempts=1,
                chunk_max_attempts=2,
                reduce_max_attempts=1,
                model_processor=flaky_chunk_processor,
            )

            run_dir = Path(status["output"]["path"])
            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")
            failed_calls = [call for call in result["timing"]["calls"] if call["status"] == "failed"]

            self.assertEqual(status["status"], "complete")
            self.assertEqual(calls["long.txt#chunk-0001"], 1)
            self.assertEqual(calls["long.txt#chunk-0002"], 2)
            self.assertEqual(failed_calls[0]["kind"], "chunk_map")
            self.assertEqual(failed_calls[0]["chunk_id"], "chunk-0002")
            self.assertEqual(failed_calls[0]["attempt"], 1)
            self.assertEqual(failed_calls[0]["max_attempts"], 2)

    def test_reduce_retry_recovers_after_transient_failure(self) -> None:
        reduce_attempts = 0

        def flaky_reduce_processor(**kwargs: object) -> FarmModelResult:
            nonlocal reduce_attempts
            file_path = str(kwargs["file_path"])
            if file_path == "long.txt":
                reduce_attempts += 1
                if reduce_attempts == 1:
                    raise RuntimeError("transient reduce failure")
            return fake_processor(**kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            content = " ".join(f"word{index}" for index in range(80))
            (root / "input" / "long.txt").write_text(content, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_strategy="token",
                chunk_tokens=30,
                reduce_tokens=1000,
                token_counter=FakeTokenCounter(),
                max_attempts=1,
                chunk_max_attempts=1,
                reduce_max_attempts=2,
                model_processor=flaky_reduce_processor,
            )

            run_dir = Path(status["output"]["path"])
            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")
            reduce_calls = [call for call in result["timing"]["calls"] if call["kind"] == "reduce"]

            self.assertEqual(status["status"], "complete")
            self.assertEqual(reduce_attempts, 2)
            self.assertEqual([call["status"] for call in reduce_calls], ["failed", "complete"])
            self.assertEqual([call["attempt"] for call in reduce_calls], [1, 2])
            self.assertEqual({call["max_attempts"] for call in reduce_calls}, {2})

    def test_reduce_retry_exhaustion_fails_file_attempt(self) -> None:
        reduce_attempts = 0

        def failing_reduce_processor(**kwargs: object) -> FarmModelResult:
            nonlocal reduce_attempts
            file_path = str(kwargs["file_path"])
            if file_path == "long.txt":
                reduce_attempts += 1
                raise RuntimeError("reduce stayed broken")
            return fake_processor(**kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            content = " ".join(f"word{index}" for index in range(80))
            (root / "input" / "long.txt").write_text(content, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_strategy="token",
                chunk_tokens=30,
                reduce_tokens=1000,
                token_counter=FakeTokenCounter(),
                max_attempts=1,
                chunk_max_attempts=1,
                reduce_max_attempts=1,
                model_processor=failing_reduce_processor,
            )

            self.assertEqual(status["status"], "failed")
            self.assertEqual(reduce_attempts, 1)
            self.assertIn("reduce stayed broken", status["jobs"][0]["error"])

    def test_chunked_snippets_are_selected_from_verified_chunk_snippets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            content = "\n\n".join(
                [
                    "alpha exact evidence " + ("alpha " * 80),
                    "beta exact evidence " + ("beta " * 80),
                ]
            )
            (root / "input" / "long.txt").write_text(content, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                chunk_chars=180,
                reduce_chars=1000,
                snippets="3",
                model_processor=snippet_processor,
            )

            run_dir = Path(status["output"]["path"])
            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")
            snippet_texts = [snippet["text"] for snippet in result["result"]["snippets"]]

            self.assertEqual(status["status"], "complete_with_warnings")
            self.assertIn("alpha exact evidence", snippet_texts)
            self.assertIn("beta exact evidence", snippet_texts)
            self.assertNotIn("invented reduce quote", snippet_texts)
            self.assertEqual(result["snippets"]["requested_count"], 3)
            self.assertEqual(result["snippets"]["verified_count"], 2)
            self.assertEqual(result["snippets"]["selected_count"], 2)
            self.assertEqual(result["snippets"]["candidate_count"], 2)
            self.assertEqual(result["snippets"]["dropped"]["unverified"], 0)
            self.assertIn("score", result["result"]["snippets"][0])
            self.assertIn("score_reasons", result["result"]["snippets"][0])
            self.assertIn("snippet_count_under_requested", result["warnings"])

    def test_invalid_config_fails_before_run_folder_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")
            (root / ".qwen-farm.json").write_text('{"unknown": true}', encoding="utf-8")
            output = root / "results"

            with self.assertRaisesRegex(ValueError, "Unknown config field"):
                qwen_farm.run_farm(
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

            self.assertFalse(output.exists())

    def test_config_model_overrides_agent_model(self) -> None:
        seen_models: list[str] = []

        def recording_processor(**kwargs: object) -> FarmModelResult:
            agent = kwargs["agent"]
            assert isinstance(agent, dict)
            seen_models.append(str(agent["model"]))
            return fake_processor(**kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "agents" / "custom.json").write_text(
                json.dumps({"model": "agent-model:1b"}),
                encoding="utf-8",
            )
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")
            (root / ".qwen-farm.json").write_text(json.dumps({"model": "config-model:1b"}), encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="custom",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=recording_processor,
            )

            self.assertEqual(seen_models, ["config-model:1b"])
            self.assertEqual(status["model"], "config-model:1b")
            self.assertEqual(status["runtime"]["model"], "config-model:1b")

    def test_resource_mode_cpu_forces_agent_num_gpu_zero(self) -> None:
        seen_options: list[dict[str, object]] = []

        def recording_processor(**kwargs: object) -> FarmModelResult:
            agent = kwargs["agent"]
            assert isinstance(agent, dict)
            seen_options.append(dict(agent.get("options") or {}))
            return fake_processor(**kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "agents" / "gpuish.json").write_text(
                json.dumps({"model": "qwen-test:1b", "options": {"num_gpu": 30}}),
                encoding="utf-8",
            )
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="gpuish",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                resource_mode="cpu",
                model_processor=recording_processor,
            )

            self.assertEqual(seen_options[0]["num_gpu"], 0)
            self.assertEqual(status["runtime"]["resource_mode"]["requested"], "cpu")
            self.assertEqual(status["runtime"]["resource_mode"]["effective"], "cpu")
            self.assertEqual(status["runtime"]["resource_mode"]["agent_option_override"]["before"], 30)

    def test_resource_mode_gpu_rejects_cpu_agent_before_run_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "agents" / "cpu-agent.json").write_text(
                json.dumps({"model": "qwen-test:1b", "options": {"num_gpu": 0}}),
                encoding="utf-8",
            )
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")
            output = root / "results"

            with self.assertRaisesRegex(ValueError, "conflicts"):
                qwen_farm.run_farm(
                    root=root,
                    input_folder=root / "input",
                    output_dir=output,
                    mode="summarize",
                    instructions=None,
                    agent_id="cpu-agent",
                    default_model="qwen-test:1b",
                    ollama_base_url="http://127.0.0.1:11434",
                    resource_mode="gpu",
                    model_processor=fake_processor,
                )

            self.assertFalse(output.exists())

    def test_chunk_warnings_mark_run_complete_with_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "long.txt").write_text("x" * 9000, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=warning_processor,
            )

            self.assertEqual(status["status"], "complete_with_warnings")
            self.assertEqual(status["jobs"][0]["warnings"], ["chunk_warning"])

    def test_prompt_mode_does_not_chunk_large_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "long.txt").write_text("x" * 9000, encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="prompt",
                instructions="Do the thing.",
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )

            run_dir = Path(status["output"]["path"])
            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")

            self.assertFalse(status["jobs"][0]["chunking"]["enabled"])
            self.assertFalse(result["chunking"]["enabled"])
            self.assertFalse((run_dir / "jobs/job-0001/chunks").exists())

    def test_reduce_payload_batches_stay_under_budget(self) -> None:
        payloads = [
            {
                "title": f"Chunk {index}",
                "abstract": "a" * 120,
                "bullets": ["b" * 120],
                "open_questions": [],
                "confidence": "medium",
            }
            for index in range(8)
        ]

        batches = qwen_farm.reduce_payload_batches("source.txt", payloads, max_chars=700)

        self.assertGreater(len(batches), 1)
        for batch in batches:
            self.assertLessEqual(len(qwen_farm.render_reduce_input("source.txt", batch)), 700)

    def test_parallel_jobs_limit_and_status_running_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            for name in ["a.md", "b.md", "c.md"]:
                (root / "input" / name).write_text(name, encoding="utf-8")
            output = root / "results"

            lock = threading.Lock()
            release = threading.Event()
            two_running = threading.Event()
            active = 0
            max_active = 0
            run_status: dict[str, object] = {}
            run_error: list[BaseException] = []

            def blocking_processor(**kwargs: object) -> FarmModelResult:
                nonlocal active, max_active
                with lock:
                    active += 1
                    max_active = max(max_active, active)
                    if active == 2:
                        two_running.set()
                try:
                    self.assertTrue(release.wait(5), "Timed out waiting to release worker")
                    return fake_processor(**kwargs)
                finally:
                    with lock:
                        active -= 1

            def run() -> None:
                try:
                    run_status.update(
                        qwen_farm.run_farm(
                            root=root,
                            input_folder=root / "input",
                            output_dir=output,
                            mode="summarize",
                            instructions=None,
                            agent_id="default",
                            default_model="qwen-test:1b",
                            ollama_base_url="http://127.0.0.1:11434",
                            parallel_jobs=2,
                            model_processor=blocking_processor,
                        )
                    )
                except BaseException as exc:
                    run_error.append(exc)

            thread = threading.Thread(target=run)
            thread.start()
            try:
                self.assertTrue(two_running.wait(5), "Expected two concurrent jobs to start")
                run_dirs = [path for path in output.iterdir() if path.is_dir()]
                self.assertEqual(len(run_dirs), 1)
                status = qwen_farm.read_json(run_dirs[0] / "farm-status.json")

                self.assertEqual(status["counts"]["running"], 2)
                self.assertEqual(status["counts"]["queued"], 1)
                self.assertEqual(max_active, 2)
            finally:
                release.set()
                thread.join(5)

            self.assertFalse(thread.is_alive())
            if run_error:
                raise run_error[0]
            self.assertEqual(run_status["status"], "complete")
            self.assertEqual(max_active, 2)

    def test_parallel_job_failure_does_not_stop_queued_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.md").write_text("A", encoding="utf-8")
            (root / "input" / "fail.txt").write_text("fail", encoding="utf-8")
            (root / "input" / "z.md").write_text("Z", encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=None,
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                parallel_jobs=2,
                model_processor=fake_processor,
            )

            run_dir = Path(status["output"]["path"])

            self.assertEqual(status["status"], "partial")
            self.assertEqual(status["counts"]["complete"], 2)
            self.assertEqual(status["counts"]["failed"], 1)
            self.assertEqual([job["job_id"] for job in status["jobs"]], ["job-0001", "job-0002", "job-0003"])
            failed_job = status["jobs"][1]
            self.assertTimingComplete(failed_job["timing"])
            self.assertEqual(failed_job["timing"]["calls"][0]["status"], "failed")
            self.assertIn("planned failure", failed_job["timing"]["calls"][0]["error"])
            self.assertTrue((run_dir / "jobs/job-0001/result.json").exists())
            self.assertTrue((run_dir / "jobs/job-0002/log.md").exists())
            self.assertTrue((run_dir / "jobs/job-0003/result.json").exists())
