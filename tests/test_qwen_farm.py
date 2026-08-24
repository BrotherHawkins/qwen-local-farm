from __future__ import annotations

import json
import tempfile
import threading
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


def warning_processor(**kwargs: object) -> FarmModelResult:
    result = fake_processor(**kwargs)
    return FarmModelResult(
        payload=result.payload,
        markdown=result.markdown,
        raw_response=result.raw_response,
        structured_valid=result.structured_valid,
        warnings=["chunk_warning"],
    )


class FarmRunTests(unittest.TestCase):
    def assertTimingComplete(self, timing: dict[str, object]) -> None:
        self.assertIsInstance(timing.get("started_at"), str)
        self.assertIsInstance(timing.get("completed_at"), str)
        self.assertIsInstance(timing.get("duration_ms"), int)
        self.assertGreaterEqual(int(timing["duration_ms"]), 0)

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
            self.assertEqual(status["runtime"]["model"], "qwen-test:1b")
            self.assertTimingComplete(status["timing"])
            self.assertIsInstance(status["jobs"][0]["timing"].get("queued_at"), str)
            self.assertTimingComplete(status["jobs"][0]["timing"])

            result = qwen_farm.read_json(run_dir / "jobs/job-0001/result.json")
            self.assertEqual(result["timing"]["calls"][0]["kind"], "single")
            self.assertTimingComplete(result["timing"]["calls"][0])

            timing_summary = qwen_farm.read_json(run_dir / "timing-summary.json")
            self.assertEqual(timing_summary["run_id"], status["run_id"])
            self.assertEqual(timing_summary["aggregate_by_call_kind"]["single"]["count"], 2)

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
            self.assertIn("## Timing", one_run)
            self.assertIn("## Runtime", one_run)
            self.assertIn("Profile: `local-8gb`", one_run)

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
