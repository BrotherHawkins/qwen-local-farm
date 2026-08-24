from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src import (
    qwen_farm,
    qwen_farm_dogfood,
    qwen_farm_doctor,
    qwen_farm_recommend,
    qwen_farm_schema,
    qwen_farm_snippet_packs,
    qwen_farm_status,
    qwen_farm_synthesis_bundles,
    qwen_farm_timing,
)
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


def ready_ollama(method: str, url: str, **_kwargs: object) -> dict[str, Any]:
    if method == "GET" and url.endswith("/api/tags"):
        return {"models": [{"name": "qwen3.5:4b"}]}
    if method == "POST" and url.endswith("/api/chat"):
        return {"message": {"content": "ready"}}
    raise AssertionError(f"Unexpected request: {method} {url}")


def write_recommendation_fixture(path: Path) -> dict[str, Any]:
    recommendation = qwen_farm_recommend.build_recommendation_report(
        root=ROOT,
        default_model="qwen3.5:4b",
        ollama_base_url="http://127.0.0.1:11434",
        generated_at="2026-08-24T00:00:00Z",
        find_ollama_fn=lambda: "ollama",
        request_json_fn=ready_ollama,
        tokenizer_status_fn=ready_tokenizers,
    )
    path.write_text(json.dumps(recommendation), encoding="utf-8")
    return recommendation


def load_schema(name: str) -> dict[str, Any]:
    return qwen_farm_schema.load_json_object(SCHEMAS / name)


def write_package_fixture(root: Path) -> tuple[Path, dict[str, Any]]:
    run_dir = root / "farm-run-schema"
    result_dir = run_dir / "jobs" / "job-0001"
    source_path = root / "input" / "article.txt"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("Source text with one important quote.", encoding="utf-8")

    result = {
        "schema_version": "0.1",
        "job_id": "job-0001",
        "mode": "summarize",
        "status": "complete",
        "structured_valid": True,
        "input": {
            "path": str(source_path),
        },
        "result": {
            "title": "Schema Article",
            "abstract": "A compact summary for schema validation.",
            "bullets": ["First claim", "Second claim"],
            "open_questions": ["What changed later?"],
            "confidence": "high",
            "snippets": [
                {
                    "text": "Source text with one important quote.",
                    "reason": "It carries the core evidence.",
                    "score": 5,
                    "score_reasons": ["specific"],
                    "start_line": 1,
                    "end_line": 1,
                    "start_char": 0,
                    "end_char": 37,
                    "source_path": str(source_path),
                }
            ],
        },
        "artifacts": {
            "markdown": "jobs/job-0001/result.md",
            "raw_response": "jobs/job-0001/raw-response.txt",
        },
        "model": {
            "agent": "default",
            "model": "qwen-test:1b",
        },
        "warnings": [],
        "chunking": {"enabled": False, "chunk_count": 1},
        "snippets": {
            "requested_count": 1,
            "verified_count": 1,
            "selected_count": 1,
            "candidate_count": 1,
            "dropped": {
                "unverified": 0,
                "low_signal": 0,
                "duplicate": 0,
                "too_long": 0,
            },
        },
        "timing": {
            "started_at": "2026-08-24T00:00:00.000Z",
            "completed_at": "2026-08-24T00:00:02.000Z",
            "duration_ms": 2000,
            "calls": [
                {
                    "kind": "single",
                    "mode": "summarize",
                    "file_path": str(source_path),
                    "started_at": "2026-08-24T00:00:00.100Z",
                    "completed_at": "2026-08-24T00:00:01.900Z",
                    "duration_ms": 1800,
                    "status": "complete",
                }
            ],
        },
    }

    status = {
        "schema_version": "0.1",
        "run_id": "farm-run-schema",
        "status": "complete",
        "mode": "summarize",
        "agent": "default",
        "model": "qwen-test:1b",
        "runtime": {
            "profile": "test",
            "model": "qwen-test:1b",
            "summarize": {
                "chunk_strategy": "chars",
                "chunk_chars": 8000,
                "reduce_chars": 8000,
                "snippet_policy": "fixed",
                "snippet_count": 1,
                "snippet_max_chars": 400,
            },
        },
        "input": {
            "path": str(source_path.parent),
            "kind": "folder",
        },
        "output": {
            "path": str(run_dir),
        },
        "counts": {
            "queued": 0,
            "running": 0,
            "complete": 1,
            "complete_with_warnings": 0,
            "failed": 0,
            "skipped": 0,
            "total": 1,
        },
        "jobs": [
            {
                "job_id": "job-0001",
                "status": "complete",
                "input_path": str(source_path),
                "result_json": "jobs/job-0001/result.json",
                "result_md": "jobs/job-0001/result.md",
                "raw_response": "jobs/job-0001/raw-response.txt",
                "error": None,
                "warnings": [],
                "chunking": {"enabled": False, "chunk_count": 1},
                "snippets": result["snippets"],
                "timing": result["timing"],
            }
        ],
        "skipped_files": [],
        "created_at": "2026-08-24T00:00:00Z",
        "updated_at": "2026-08-24T00:00:02Z",
        "timing": {
            "created_at": "2026-08-24T00:00:00Z",
            "started_at": "2026-08-24T00:00:00.000Z",
            "completed_at": "2026-08-24T00:00:02.000Z",
            "duration_ms": 2000,
        },
    }

    qwen_farm_status.write_json(result_dir / "result.json", result)
    qwen_farm_status.write_json(run_dir / "farm-status.json", status)
    return run_dir, status


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

    def test_generated_recommendation_report_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = qwen_farm_recommend.build_recommendation_report(
                root=Path(temp_dir),
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                generated_at="2026-08-24T00:00:00Z",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=ready_ollama,
                tokenizer_status_fn=ready_tokenizers,
            )

            self.assertValid(report, "farm-recommendation.schema.json")

    def test_generated_config_apply_report_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_path = root / "farm-recommendation.json"
            write_recommendation_fixture(recommendation_path)

            report = qwen_farm_recommend.build_config_apply_report(
                root=ROOT,
                recommendation_path=recommendation_path,
                config_path=root / ".qwen-farm.json",
                output_dir=root / "reports",
                generated_at="2026-08-24T00:00:01Z",
            )

            self.assertValid(report, "farm-config-apply.schema.json")

    def test_generated_post_run_packages_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir, status = write_package_fixture(root)

            timing_summary = qwen_farm_timing.build_timing_summary(status)
            snippet_pack = qwen_farm_snippet_packs.build_snippet_pack(
                run_dir=run_dir,
                label="schema-pack",
                created_at="2026-08-24T00:00:03Z",
            )
            synthesis_bundle = qwen_farm_synthesis_bundles.build_synthesis_bundle(
                run_dir=run_dir,
                label="schema-bundle",
                created_at="2026-08-24T00:00:04Z",
                max_estimated_tokens=2000,
            )
            dogfood_record = qwen_farm_dogfood.build_quality_record(
                root=root,
                run_dir=run_dir,
                label="schema-record",
                recorded_at="2026-08-24T00:00:05Z",
            )
            candidate_record = json.loads(json.dumps(dogfood_record))
            candidate_record["label"] = "schema-candidate"
            candidate_record["duration_ms"] = 2200
            dogfood_comparison = qwen_farm_dogfood.compare_records(dogfood_record, candidate_record)

            self.assertValid(timing_summary, "farm-timing-summary.schema.json")
            self.assertValid(snippet_pack, "farm-snippet-pack.schema.json")
            self.assertValid(synthesis_bundle, "farm-synthesis-bundle.schema.json")
            self.assertValid(dogfood_record, "farm-dogfood-record.schema.json")
            self.assertValid(dogfood_comparison, "farm-dogfood-comparison.schema.json")

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
            (
                {
                    "schema_version": "0.1",
                    "run_id": "run-1",
                    "aggregate_by_call_kind": {},
                    "slowest_jobs": [],
                    "slowest_calls": [],
                },
                "schemas/farm-timing-summary.schema.json",
            ),
            (
                {
                    "schema_version": 1,
                    "resource_mode": {},
                    "profile": {},
                    "concurrency": {},
                    "summarize": {},
                    "evidence": {},
                    "next_actions": [],
                },
                "schemas/farm-recommendation.schema.json",
            ),
            (
                {
                    "schema_version": 1,
                    "dry_run": True,
                    "recommendation_path": "farm-recommendation.json",
                    "config_path": ".qwen-farm.json",
                    "proposed_config": {},
                    "changes": [],
                    "not_applied": [],
                },
                "schemas/farm-config-apply.schema.json",
            ),
            (
                {
                    "schema_version": 1,
                    "limits": {"source": "selected"},
                    "snippets": [],
                    "diagnostics": {},
                    "counts": {},
                },
                "schemas/farm-snippet-pack.schema.json",
            ),
            (
                {
                    "schema_version": 1,
                    "limits": {"snippet_source": "selected"},
                    "items": [],
                    "budget": {},
                    "diagnostics": {},
                    "counts": {},
                },
                "schemas/farm-synthesis-bundle.schema.json",
            ),
            (
                {
                    "schema_version": 1,
                    "recorded_at": "2026-08-24T00:00:00Z",
                    "totals": {},
                    "quality": {},
                    "jobs": [],
                },
                "schemas/farm-dogfood-record.schema.json",
            ),
            (
                {
                    "schema_version": 1,
                    "compared_at": "2026-08-24T00:00:00Z",
                    "baseline": {},
                    "candidate": {},
                    "duration_ms": {},
                    "jobs": [],
                },
                "schemas/farm-dogfood-comparison.schema.json",
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

    def test_validate_artifact_auto_detects_recommendation_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "farm-recommendation.json"
            report = qwen_farm_recommend.build_recommendation_report(
                root=Path(temp_dir),
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                generated_at="2026-08-24T00:00:00Z",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=ready_ollama,
                tokenizer_status_fn=ready_tokenizers,
            )
            artifact.write_text(json.dumps(report), encoding="utf-8")

            result = qwen_farm_schema.validate_artifact(ROOT, artifact)

            self.assertTrue(result["valid"])
            self.assertEqual(result["schema"]["path"], "schemas/farm-recommendation.schema.json")
            self.assertTrue(result["schema"]["detected"])

    def test_validate_artifact_auto_detects_config_apply_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_path = root / "farm-recommendation.json"
            artifact = root / "farm-config-apply.json"
            write_recommendation_fixture(recommendation_path)
            report = qwen_farm_recommend.build_config_apply_report(
                root=ROOT,
                recommendation_path=recommendation_path,
                config_path=root / ".qwen-farm.json",
                output_dir=root / "reports",
                generated_at="2026-08-24T00:00:01Z",
            )
            artifact.write_text(json.dumps(report), encoding="utf-8")

            result = qwen_farm_schema.validate_artifact(ROOT, artifact)

            self.assertTrue(result["valid"])
            self.assertEqual(result["schema"]["path"], "schemas/farm-config-apply.schema.json")
            self.assertTrue(result["schema"]["detected"])

    def test_validate_artifact_accepts_recommendation_schema_path_and_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "farm-recommendation.json"
            report = qwen_farm_recommend.build_recommendation_report(
                root=Path(temp_dir),
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                generated_at="2026-08-24T00:00:00Z",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=ready_ollama,
                tokenizer_status_fn=ready_tokenizers,
            )
            artifact.write_text(json.dumps(report), encoding="utf-8")

            by_path = qwen_farm_schema.validate_artifact(
                ROOT,
                artifact,
                "schemas/farm-recommendation.schema.json",
            )
            by_id = qwen_farm_schema.validate_artifact(
                ROOT,
                artifact,
                "https://qwen-local-farm.local/schemas/farm-recommendation.schema.json",
            )

            self.assertTrue(by_path["valid"])
            self.assertTrue(by_id["valid"])
            self.assertEqual(by_path["schema"]["path"], "schemas/farm-recommendation.schema.json")
            self.assertEqual(by_id["schema"]["path"], "schemas/farm-recommendation.schema.json")

    def test_validate_artifact_accepts_config_apply_schema_path_and_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_path = root / "farm-recommendation.json"
            artifact = root / "farm-config-apply.json"
            write_recommendation_fixture(recommendation_path)
            report = qwen_farm_recommend.build_config_apply_report(
                root=ROOT,
                recommendation_path=recommendation_path,
                config_path=root / ".qwen-farm.json",
                output_dir=root / "reports",
                generated_at="2026-08-24T00:00:01Z",
            )
            artifact.write_text(json.dumps(report), encoding="utf-8")

            by_path = qwen_farm_schema.validate_artifact(
                ROOT,
                artifact,
                "schemas/farm-config-apply.schema.json",
            )
            by_id = qwen_farm_schema.validate_artifact(
                ROOT,
                artifact,
                "https://qwen-local-farm.local/schemas/farm-config-apply.schema.json",
            )

            self.assertTrue(by_path["valid"])
            self.assertTrue(by_id["valid"])
            self.assertEqual(by_path["schema"]["path"], "schemas/farm-config-apply.schema.json")
            self.assertEqual(by_id["schema"]["path"], "schemas/farm-config-apply.schema.json")

    def test_validate_artifact_accepts_package_schema_path_and_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir, _status = write_package_fixture(root)
            pack = qwen_farm_snippet_packs.build_snippet_pack(
                run_dir=run_dir,
                label="schema-pack",
                created_at="2026-08-24T00:00:03Z",
            )
            artifact = root / "schema-pack.json"
            artifact.write_text(json.dumps(pack), encoding="utf-8")

            by_path = qwen_farm_schema.validate_artifact(
                ROOT,
                artifact,
                "schemas/farm-snippet-pack.schema.json",
            )
            by_id = qwen_farm_schema.validate_artifact(
                ROOT,
                artifact,
                "https://qwen-local-farm.local/schemas/farm-snippet-pack.schema.json",
            )

            self.assertTrue(by_path["valid"])
            self.assertTrue(by_id["valid"])
            self.assertEqual(by_path["schema"]["path"], "schemas/farm-snippet-pack.schema.json")
            self.assertEqual(by_id["schema"]["path"], "schemas/farm-snippet-pack.schema.json")

    def test_validate_artifact_reports_schema_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "overview.json"
            artifact.write_text(json.dumps({"schema_version": 1, "scope": "overview", "counts": {}, "runs": []}), encoding="utf-8")

            result = qwen_farm_schema.validate_artifact(ROOT, artifact)

            self.assertFalse(result["valid"])
            self.assertEqual(result["exit_code"], qwen_farm_schema.EXIT_INVALID)
            self.assertIn("$.counts: missing required field 'runs'", result["errors"])

    def test_validate_artifact_reports_malformed_recommendation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "farm-recommendation.json"
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "generated_at": "2026-08-24T00:00:00Z",
                        "status": "ready",
                        "agent": "default",
                        "model": "qwen3.5:4b",
                        "resource_mode": {"recommended": "rocket", "confidence": "high", "reason": "bad"},
                        "profile": {"recommended": "local-8gb", "confidence": "high", "reason": "ok"},
                        "concurrency": {
                            "parallel_jobs": {"recommended": 1, "confidence": "high", "reason": "ok"},
                            "ollama_num_parallel": {"recommended": 1, "confidence": "high", "reason": "ok"},
                        },
                        "summarize": {"chunk_strategy": "token", "confidence": "high", "reason": "ok"},
                        "evidence": {"benchmark": {}, "ollama": {}, "runtime": {}, "tokenizers": {}},
                        "warnings": [],
                        "next_actions": [],
                        "report_paths": {"json": "x.json", "markdown": "x.md"},
                    }
                ),
                encoding="utf-8",
            )

            result = qwen_farm_schema.validate_artifact(ROOT, artifact)

            self.assertFalse(result["valid"])
            self.assertEqual(result["exit_code"], qwen_farm_schema.EXIT_INVALID)
            self.assertIn("$.resource_mode.recommended: expected one of", "\n".join(result["errors"]))

    def test_validate_artifact_reports_malformed_config_apply_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "farm-config-apply.json"
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "generated_at": "2026-08-24T00:00:00Z",
                        "status": "maybe",
                        "dry_run": True,
                        "recommendation_path": "farm-recommendation.json",
                        "config_path": ".qwen-farm.json",
                        "backup_path": None,
                        "recommendation": {
                            "status": "ready",
                            "agent": "default",
                            "model": "qwen3.5:4b",
                            "generated_at": "2026-08-24T00:00:00Z",
                        },
                        "existing_config": {},
                        "proposed_config": {},
                        "changes": [],
                        "not_applied": [],
                        "warnings": [],
                        "next_actions": [],
                        "report_paths": {"json": "x.json", "markdown": "x.md"},
                    }
                ),
                encoding="utf-8",
            )

            result = qwen_farm_schema.validate_artifact(ROOT, artifact)

            self.assertFalse(result["valid"])
            self.assertEqual(result["exit_code"], qwen_farm_schema.EXIT_INVALID)
            self.assertIn("$.status: expected one of", "\n".join(result["errors"]))

    def test_validate_artifact_reports_malformed_resource_mode_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "timing-summary.json"
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "run_id": "run-1",
                        "status": "complete",
                        "mode": "summarize",
                        "agent": "default",
                        "model": "qwen3.5:4b",
                        "profile": "local-8gb",
                        "resource_mode": {
                            "requested": "auto",
                            "effective": "rocket",
                            "source": "profile",
                            "reason": "bad",
                            "agent_option_override": None,
                        },
                        "timing": {},
                        "counts": {},
                        "jobs": [],
                        "calls": [],
                        "aggregate_by_call_kind": {},
                        "slowest_jobs": [],
                        "slowest_calls": [],
                    }
                ),
                encoding="utf-8",
            )

            result = qwen_farm_schema.validate_artifact(ROOT, artifact)

            self.assertFalse(result["valid"])
            self.assertEqual(result["exit_code"], qwen_farm_schema.EXIT_INVALID)
            self.assertIn("$.resource_mode.effective: expected one of", "\n".join(result["errors"]))

    def test_validate_artifact_reports_malformed_package_schema_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "bundle.json"
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "created_at": "2026-08-24T00:00:00Z",
                        "label": "malformed",
                        "run_id": "run-1",
                        "run_path": ".run/farm/run-1",
                        "mode": "summarize",
                        "model": "qwen-test:1b",
                        "limits": {"max_snippets": 1, "per_file": 1, "snippet_source": "selected"},
                        "counts": {},
                        "items": [],
                        "diagnostics": {"skipped_jobs": [], "warnings": []},
                        "budget": {},
                    }
                ),
                encoding="utf-8",
            )

            result = qwen_farm_schema.validate_artifact(
                ROOT,
                artifact,
                "schemas/farm-synthesis-bundle.schema.json",
            )

            self.assertFalse(result["valid"])
            self.assertEqual(result["exit_code"], qwen_farm_schema.EXIT_INVALID)
            self.assertIn("$.budget: missing required field 'input'", result["errors"])

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
