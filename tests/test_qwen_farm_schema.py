from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src import qwen_farm, qwen_farm_doctor, qwen_farm_schema, qwen_farm_status
from src.qwen_farm_model import FarmModelResult


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"


def fake_processor(**kwargs: object) -> FarmModelResult:
    file_path = str(kwargs["file_path"])
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
        raw_response="Title: ok",
        structured_valid=True,
        warnings=[],
    )


def ready_tokenizers(**_kwargs: object) -> dict[str, object]:
    return {
        "ready": True,
        "cache_dir": ".run/tokenizers/hf-cache",
        "models": [{"model": "qwen3.5:4b", "ready": True, "offline_verified": True}],
    }


def load_schema(name: str) -> dict[str, Any]:
    return qwen_farm_schema.load_json_object(SCHEMAS / name)


class FarmSchemaTests(unittest.TestCase):
    def assertValid(self, instance: dict[str, Any], schema_name: str) -> None:
        errors = qwen_farm_schema.validate(instance, load_schema(schema_name))
        self.assertEqual(errors, [], "\n".join(errors))

    def test_all_schema_files_are_json_objects_with_metadata(self) -> None:
        for path in sorted(SCHEMAS.glob("*.schema.json")):
            with self.subTest(path=path.name):
                schema = qwen_farm_schema.load_json_object(path)
                self.assertEqual(schema.get("$schema"), "https://json-schema.org/draft/2020-12/schema")
                self.assertIsInstance(schema.get("$id"), str)
                self.assertIsInstance(schema.get("title"), str)
                self.assertIsInstance(schema.get("description"), str)
                self.assertEqual(schema.get("type"), "object")
                self.assertIsInstance(schema.get("required"), list)

    def test_schema_index_points_to_existing_files(self) -> None:
        index = qwen_farm_schema.load_json_object(SCHEMAS / "index.json")

        self.assertEqual(index["schema_version"], 1)
        self.assertGreater(len(index["schemas"]), 0)
        for record in index["schemas"]:
            with self.subTest(path=record["path"]):
                schema_path = ROOT / record["path"]
                self.assertTrue(schema_path.exists())
                schema = qwen_farm_schema.load_json_object(schema_path)
                self.assertEqual(record["id"], schema["$id"])

    def test_generated_farm_status_and_job_result_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.txt").write_text("A", encoding="utf-8")

            status = qwen_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=root / "results",
                mode="summarize",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=fake_processor,
            )
            run_dir = Path(status["output"]["path"])
            result = qwen_farm.read_json(run_dir / "jobs" / "job-0001" / "result.json")

            self.assertValid(status, "farm-status.schema.json")
            self.assertValid(result, "farm-job-result.schema.json")

    def test_status_json_envelopes_validate(self) -> None:
        status = {
            "schema_version": "0.1",
            "run_id": "farm-run-1",
            "status": "complete",
            "mode": "summarize",
            "jobs": [],
        }

        overview = qwen_farm_status.farm_overview_json([status])
        run = qwen_farm_status.run_status_json(status)

        self.assertValid(overview, "farm-status-overview.schema.json")
        self.assertValid(run, "farm-status-run.schema.json")

    def test_generated_doctor_report_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = qwen_farm_doctor.build_doctor_report(
                root=Path(temp_dir),
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                generated_at="2026-08-24T00:00:00Z",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: {"models": [{"name": "qwen3.5:4b"}]},
                tokenizer_status_fn=ready_tokenizers,
                platform_name="TestOS",
                python_version=(3, 13, 0),
            )

            self.assertValid(report, "farm-doctor.schema.json")

    def test_validation_reports_path_aware_errors(self) -> None:
        schema = load_schema("farm-status-overview.schema.json")
        malformed = {
            "schema_version": 1,
            "scope": "overview",
            "counts": {},
            "runs": [{"run_id": "run-1", "status": "bogus"}],
        }

        errors = qwen_farm_schema.validate(malformed, schema)

        self.assertIn("$.counts: missing required field 'runs'", "\n".join(errors))
        self.assertIn("$.runs[0]: missing required field 'mode'", "\n".join(errors))
        self.assertIn("$.runs[0].status: expected one of", "\n".join(errors))

    def test_validate_file_loads_instance_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            instance = root / "instance.json"
            schema = root / "schema.json"
            instance.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
            schema.write_text(
                json.dumps(
                    {
                        "type": "object",
                        "required": ["schema_version"],
                        "properties": {"schema_version": {"const": 1}},
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(qwen_farm_schema.validate_file(instance, schema), [])


if __name__ == "__main__":
    unittest.main()
