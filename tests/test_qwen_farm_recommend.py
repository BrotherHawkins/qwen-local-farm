from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src import qwen_farm_recommend


ROOT = Path(__file__).resolve().parents[1]


def ready_tokenizers(**_kwargs: object) -> dict[str, object]:
    return {
        "ready": True,
        "cache_dir": ".run/tokenizers/hf-cache",
        "models": [{"model": "qwen3.5:4b", "ready": True, "offline_verified": True}],
    }


def missing_tokenizers(**_kwargs: object) -> dict[str, object]:
    return {
        "ready": False,
        "cache_dir": ".run/tokenizers/hf-cache",
        "models": [{"model": "qwen3.5:4b", "ready": False, "offline_verified": False}],
    }


def ready_ollama(method: str, url: str, **_kwargs: object) -> dict[str, Any]:
    if method == "GET" and url.endswith("/api/tags"):
        return {"models": [{"name": "qwen3.5:4b"}]}
    if method == "POST" and url.endswith("/api/chat"):
        return {"message": {"content": "ready"}}
    raise AssertionError(f"Unexpected request: {method} {url}")


def recommendation_fixture(status: str = "ready") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": "2026-08-24T00:00:00Z",
        "status": status,
        "agent": "default",
        "model": "qwen3.5:4b",
        "resource_mode": {
            "recommended": "hybrid",
            "confidence": "medium",
            "reason": "Use GPU when available with fallback expectations.",
        },
        "profile": {
            "recommended": "local-8gb",
            "confidence": "medium",
            "reason": "Resolved profile and tiny benchmark completed.",
        },
        "concurrency": {
            "parallel_jobs": {
                "recommended": 1,
                "current": 1,
                "confidence": "high",
                "reason": "Keep one farm worker.",
            },
            "ollama_num_parallel": {
                "recommended": 1,
                "current": None,
                "confidence": "medium",
                "reason": "Keep Ollama parallelism aligned.",
            },
        },
        "summarize": {
            "chunk_strategy": "token",
            "chunk_tokens": 4096,
            "reduce_tokens": 4096,
            "chunk_chars": 8000,
            "reduce_chars": 8000,
            "token_safety_margin": 0.1,
            "confidence": "high",
            "reason": "Tokenizer is ready.",
        },
        "evidence": {
            "benchmark": {},
            "ollama": {},
            "runtime": {},
            "tokenizers": {},
        },
        "warnings": [],
        "next_actions": [],
        "report_paths": {
            "json": ".run/recommendations/farm-recommendation.json",
            "markdown": ".run/recommendations/FARM_RECOMMENDATION.md",
        },
    }


class FarmRecommendTests(unittest.TestCase):
    def test_ready_recommendation_uses_tiny_probe_and_token_chunking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            agents = root / "agents"
            agents.mkdir()
            (agents / "default.json").write_text(
                json.dumps({"id": "default", "model": "qwen3.5:4b", "options": {"num_ctx": 8192}}),
                encoding="utf-8",
            )
            report = qwen_farm_recommend.build_recommendation_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                generated_at="2026-08-24T00:00:00Z",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=ready_ollama,
                tokenizer_status_fn=ready_tokenizers,
            )

            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["status"], "ready")
            self.assertEqual(report["agent"], "default")
            self.assertEqual(report["model"], "qwen3.5:4b")
            self.assertEqual(report["model_metadata"]["family"], "qwen")
            self.assertEqual(report["model_metadata"]["support"], "tested")
            self.assertEqual(report["resource_mode"]["recommended"], "gpu")
            self.assertEqual(report["profile"]["recommended"], "local-8gb")
            self.assertEqual(report["concurrency"]["parallel_jobs"]["recommended"], 1)
            self.assertEqual(report["concurrency"]["ollama_num_parallel"]["recommended"], 1)
            self.assertEqual(report["summarize"]["chunk_strategy"], "token")
            self.assertEqual(report["summarize"]["chunk_tokens"], 4096)
            self.assertEqual(report["evidence"]["benchmark"]["status"], "complete")
            self.assertEqual(report["next_actions"], [])

    def test_experimental_non_qwen_recommendation_prefers_character_chunking(self) -> None:
        def llama_ollama(method: str, url: str, **_kwargs: object) -> dict[str, Any]:
            if method == "GET" and url.endswith("/api/tags"):
                return {"models": [{"name": "llama3.1:8b"}]}
            if method == "POST" and url.endswith("/api/chat"):
                return {"message": {"content": "ready"}}
            raise AssertionError(f"Unexpected request: {method} {url}")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            agents = root / "agents"
            agents.mkdir()
            (agents / "llama-local.json").write_text(
                json.dumps(
                    {
                        "id": "llama-local",
                        "model": "llama3.1:8b",
                        "model_family": "llama",
                        "backend": "ollama",
                        "support": "experimental",
                        "tokenizer": {"strategy": "none"},
                        "options": {"num_ctx": 4096},
                    }
                ),
                encoding="utf-8",
            )

            report = qwen_farm_recommend.build_recommendation_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                agent_id="llama-local",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=llama_ollama,
                tokenizer_status_fn=ready_tokenizers,
            )

            markdown = qwen_farm_recommend.render_recommendation_markdown(report)

            self.assertEqual(report["model_metadata"]["family"], "llama")
            self.assertEqual(report["model_metadata"]["support"], "experimental")
            self.assertEqual(report["summarize"]["chunk_strategy"], "character")
            self.assertIn("not dogfood-tested", report["summarize"]["reason"])
            self.assertIn("Model family: `llama`", markdown)
            self.assertIn("Model support: `experimental`", markdown)

    def test_missing_ollama_degrades_to_needs_setup_without_probe(self) -> None:
        def failing_request(*_args: object, **_kwargs: object) -> dict[str, Any]:
            raise OSError("connection refused")

        with tempfile.TemporaryDirectory() as temp_dir:
            report = qwen_farm_recommend.build_recommendation_report(
                root=Path(temp_dir),
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                find_ollama_fn=lambda: None,
                request_json_fn=failing_request,
                tokenizer_status_fn=missing_tokenizers,
            )

            self.assertEqual(report["status"], "needs_setup")
            self.assertEqual(report["resource_mode"]["recommended"], "gpu")
            self.assertEqual(report["summarize"]["chunk_strategy"], "character")
            self.assertEqual(report["evidence"]["benchmark"]["status"], "skipped")
            self.assertIn("ollama.install", [item["id"] for item in report["next_actions"]])

    def test_cpu_agent_recommends_cpu_resource_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            agents = root / "agents"
            agents.mkdir()
            (agents / "qwen8-cpu.json").write_text(
                json.dumps(
                    {
                        "id": "qwen8-cpu",
                        "model": "qwen3.5:4b",
                        "options": {"num_ctx": 4096, "num_gpu": 0},
                    }
                ),
                encoding="utf-8",
            )

            report = qwen_farm_recommend.build_recommendation_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                agent_id="qwen8-cpu",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=ready_ollama,
                tokenizer_status_fn=ready_tokenizers,
            )

            self.assertEqual(report["resource_mode"]["recommended"], "cpu")
            self.assertEqual(report["resource_mode"]["confidence"], "high")

    def test_explicit_resource_mode_cpu_recommends_cpu(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = qwen_farm_recommend.build_recommendation_report(
                root=Path(temp_dir),
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                resource_mode="cpu",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=ready_ollama,
                tokenizer_status_fn=ready_tokenizers,
            )

            self.assertEqual(report["resource_mode"]["recommended"], "cpu")
            self.assertEqual(report["evidence"]["runtime"]["resource_mode"]["requested"], "cpu")
            self.assertEqual(report["evidence"]["runtime"]["resource_mode"]["effective"], "cpu")

    def test_local_24gb_profile_still_recommends_single_worker_without_parallel_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = qwen_farm_recommend.build_recommendation_report(
                root=Path(temp_dir),
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                profile="local-24gb",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=ready_ollama,
                tokenizer_status_fn=ready_tokenizers,
            )

            self.assertEqual(report["profile"]["recommended"], "local-24gb")
            self.assertEqual(report["concurrency"]["parallel_jobs"]["current"], 2)
            self.assertEqual(report["concurrency"]["parallel_jobs"]["recommended"], 1)
            self.assertIn("parallel load", "\n".join(report["warnings"]))

    def test_write_report_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "recommendations"
            report = qwen_farm_recommend.build_recommendation_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                output_dir=output,
                find_ollama_fn=lambda: "ollama",
                request_json_fn=ready_ollama,
                tokenizer_status_fn=ready_tokenizers,
            )

            json_path, markdown_path = qwen_farm_recommend.write_recommendation_report(report)

            self.assertEqual(json_path, output / "farm-recommendation.json")
            self.assertEqual(markdown_path, output / "FARM_RECOMMENDATION.md")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["schema_version"], 1)
            self.assertIn("# Farm Recommendation", markdown_path.read_text(encoding="utf-8"))

    def test_apply_preview_does_not_write_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_path = root / "farm-recommendation.json"
            config_path = root / ".qwen-farm.json"
            output = root / "reports"
            recommendation_path.write_text(json.dumps(recommendation_fixture()), encoding="utf-8")

            report = qwen_farm_recommend.build_config_apply_report(
                root=ROOT,
                recommendation_path=recommendation_path,
                config_path=config_path,
                output_dir=output,
                generated_at="2026-08-24T00:00:01Z",
            )

            self.assertEqual(report["status"], "preview")
            self.assertTrue(report["dry_run"])
            self.assertFalse(config_path.exists())
            self.assertEqual(report["proposed_config"]["profile"], "local-8gb")
            self.assertEqual(report["proposed_config"]["resource_mode"], "hybrid")
            self.assertEqual(report["proposed_config"]["summarize"]["chunk_strategy"], "token")
            self.assertIn("resource_mode", [item["path"] for item in report["changes"]])
            self.assertNotIn("resource_mode", [item["path"] for item in report["not_applied"]])
            self.assertIn("OLLAMA_NUM_PARALLEL", [item["path"] for item in report["not_applied"]])

    def test_apply_write_writes_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_path = root / "farm-recommendation.json"
            config_path = root / ".qwen-farm.json"
            recommendation_path.write_text(json.dumps(recommendation_fixture()), encoding="utf-8")

            report = qwen_farm_recommend.build_config_apply_report(
                root=ROOT,
                recommendation_path=recommendation_path,
                config_path=config_path,
                output_dir=root / "reports",
                write=True,
                generated_at="2026-08-24T00:00:01Z",
            )

            self.assertEqual(report["status"], "applied")
            self.assertFalse(report["dry_run"])
            self.assertIsNone(report["backup_path"])
            written = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(written["model"], "qwen3.5:4b")
            self.assertEqual(written["resource_mode"], "hybrid")
            self.assertEqual(written["concurrency"]["jobs"], 1)

    def test_apply_write_backs_up_existing_config_and_preserves_safe_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_path = root / "farm-recommendation.json"
            config_path = root / ".qwen-farm.json"
            recommendation_path.write_text(json.dumps(recommendation_fixture()), encoding="utf-8")
            config_path.write_text(
                json.dumps(
                    {
                        "profile": "local-4gb",
                        "summarize": {
                            "snippet_policy": "auto",
                            "snippet_count": None,
                            "snippet_min_count": 2,
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = qwen_farm_recommend.build_config_apply_report(
                root=ROOT,
                recommendation_path=recommendation_path,
                config_path=config_path,
                output_dir=root / "reports",
                write=True,
            )

            self.assertIsNotNone(report["backup_path"])
            self.assertTrue(Path(str(report["backup_path"])).exists())
            written = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(written["profile"], "local-8gb")
            self.assertEqual(written["summarize"]["snippet_policy"], "auto")
            self.assertEqual(written["summarize"]["chunk_strategy"], "token")

    def test_apply_blocks_invalid_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_path = root / "farm-recommendation.json"
            config_path = root / ".qwen-farm.json"
            recommendation_path.write_text(json.dumps(recommendation_fixture()), encoding="utf-8")
            config_path.write_text(json.dumps({"surprise": True}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Existing farm config is invalid"):
                qwen_farm_recommend.build_config_apply_report(
                    root=ROOT,
                    recommendation_path=recommendation_path,
                    config_path=config_path,
                    output_dir=root / "reports",
                    write=True,
                )

    def test_apply_blocks_needs_setup_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_path = root / "farm-recommendation.json"
            recommendation_path.write_text(json.dumps(recommendation_fixture("needs_setup")), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "needs_setup"):
                qwen_farm_recommend.build_config_apply_report(
                    root=ROOT,
                    recommendation_path=recommendation_path,
                    config_path=root / ".qwen-farm.json",
                    output_dir=root / "reports",
                    write=True,
                )

    def test_apply_blocks_recommendation_schema_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation = recommendation_fixture()
            recommendation["resource_mode"]["recommended"] = "rocket"
            recommendation_path = root / "farm-recommendation.json"
            recommendation_path.write_text(json.dumps(recommendation), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "schema validation"):
                qwen_farm_recommend.build_config_apply_report(
                    root=ROOT,
                    recommendation_path=recommendation_path,
                    config_path=root / ".qwen-farm.json",
                    output_dir=root / "reports",
                )

    def test_apply_ready_with_warnings_keeps_warning_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation = recommendation_fixture("ready_with_warnings")
            recommendation["warnings"] = ["Tokenizer warning"]
            recommendation_path = root / "farm-recommendation.json"
            recommendation_path.write_text(json.dumps(recommendation), encoding="utf-8")

            report = qwen_farm_recommend.build_config_apply_report(
                root=ROOT,
                recommendation_path=recommendation_path,
                config_path=root / ".qwen-farm.json",
                output_dir=root / "reports",
            )

            self.assertIn("Tokenizer warning", report["warnings"])
            self.assertIn("ready_with_warnings", "\n".join(report["warnings"]))

    def test_write_apply_report_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_path = root / "farm-recommendation.json"
            output = root / "reports"
            recommendation_path.write_text(json.dumps(recommendation_fixture()), encoding="utf-8")
            report = qwen_farm_recommend.build_config_apply_report(
                root=ROOT,
                recommendation_path=recommendation_path,
                config_path=root / ".qwen-farm.json",
                output_dir=output,
            )

            json_path, markdown_path = qwen_farm_recommend.write_config_apply_report(report)

            self.assertEqual(json_path, output / "farm-config-apply.json")
            self.assertEqual(markdown_path, output / "FARM_CONFIG_APPLY.md")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["schema_version"], 1)
            self.assertIn("# Farm Config Apply", markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
