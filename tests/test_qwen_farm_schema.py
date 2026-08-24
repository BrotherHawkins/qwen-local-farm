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

    def test_resolve_schema_reference_accepts_index_id_and_path(self) -> None:
        schema_id = "https://qwen-local-farm.local/schemas/farm-doctor.schema.json"

        by_id = qwen_farm_schema.resolve_schema_reference(ROOT, schema_id)
        by_path = qwen_farm_schema.resolve_schema_reference(ROOT, "schemas/farm-doctor.schema.json")

        self.assertEqual(by_id["path"], "schemas/farm-doctor.schema.json")
        self.assertEqual(by_path["id"], schema_id)
        self.assertFalse(by_id["detected"])
        self.assertFalse(by_path["detected"])

    def test_detect_schema_for_known_surfaces(self) -> None:
        cases = [
            (
                {"schema_version": 1, "scope": "overview"},
                "schemas/farm-status-overview.schema.json",
            ),
            (
                {"schema_version": 1, "scope": "run"},
                "schemas/farm-status-run.schema.json",
            ),
            (
                {
                    "schema_version": 1,
                    "environment": {},
                    "ollama": {},
                    "checks": [],
                    "recommendations": [],
                    "report_paths": {},
                },
                "schemas/farm-doctor.schema.json",
            ),
            (
                {
                    "schema_version": "0.1",
                    "run_id": "run-1",
                    "jobs": [],
                    "counts": {},
                    "skipped_files": [],
                },
                "schemas/farm-status.schema.json",
            ),
            (
                {
                    "schema_version": "0.1",
                    "job_id": "job-0001",
                    "structured_valid": True,
                    "result": {},
                    "artifacts": {},
                },
                "schemas/farm-job-result.schema.json",
            ),
        ]

        for artifact, expected_path in cases:
            with self.subTest(expected_path=expected_path):
                detected = qwen_farm_schema.detect_schema(ROOT, artifact)
                self.assertEqual(detected["path"], expected_path)
                self.assertTrue(detected["detected"])

    def test_detect_schema_rejects_unknown_shape(self) -> None:
        with self.assertRaisesRegex(ValueError, "Could not infer"):
            qwen_farm_schema.detect_schema(ROOT, {"schema_version": 1, "hello": "world"})

    def test_validate_artifact_auto_detects_schema_and_returns_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "doctor.json"
            report = qwen_farm_doctor.build_doctor_report(
                root=Path(temp_dir),
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                generated_at="2026-08-24T00:00:00Z",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: {"models": [{"name": "qwen3.5:4b"}]},
                tokenizer_status_fn=ready_tokenizers,
            )
            artifact.write_text(json.dumps(report), encoding="utf-8")

            result = qwen_farm_schema.validate_artifact(ROOT, artifact)

            self.assertTrue(result["valid"])
            self.assertEqual(result["exit_code"], qwen_farm_schema.EXIT_VALID)
            self.assertEqual(result["schema"]["path"], "schemas/farm-doctor.schema.json")
            self.assertTrue(result["schema"]["detected"])

    def test_validate_artifact_reports_schema_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "overview.json"
            artifact.write_text(json.dumps({"schema_version": 1, "scope": "overview", "counts": {}, "runs": []}), encoding="utf-8")

            result = qwen_farm_schema.validate_artifact(ROOT, artifact)

            self.assertFalse(result["valid"])
            self.assertEqual(result["exit_code"], qwen_farm_schema.EXIT_INVALID)
            self.assertIn("$.counts: missing required field 'runs'", result["errors"])

    def test_validate_artifact_reports_input_errors_as_exit_error(self) -> None:
        result = qwen_farm_schema.validate_artifact(ROOT, Path("missing.json"))

        self.assertFalse(result["valid"])
        self.assertEqual(result["exit_code"], qwen_farm_schema.EXIT_ERROR)
        self.assertIn("missing.json", result["errors"][0])

    def test_render_validation_result(self) -> None:
        rendered = qwen_farm_schema.render_validation_result(
            {
                "valid": False,
                "artifact_path": "artifact.json",
                "schema": {"path": "schemas/farm-status.schema.json"},
                "errors": ["$.run_id: missing required field 'run_id'"],
            }
        )

        self.assertIn("Invalid: artifact.json", rendered)
        self.assertIn("Schema: schemas/farm-status.schema.json", rendered)
        self.assertIn("Errors: 1", rendered)
        self.assertIn("- $.run_id: missing required field 'run_id'", rendered)


if __name__ == "__main__":
    unittest.main()
