from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src import qwen_farm_recommend


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
            self.assertEqual(report["resource_mode"]["recommended"], "hybrid")
            self.assertEqual(report["profile"]["recommended"], "local-8gb")
            self.assertEqual(report["concurrency"]["parallel_jobs"]["recommended"], 1)
            self.assertEqual(report["concurrency"]["ollama_num_parallel"]["recommended"], 1)
            self.assertEqual(report["summarize"]["chunk_strategy"], "token")
            self.assertEqual(report["summarize"]["chunk_tokens"], 4096)
            self.assertEqual(report["evidence"]["benchmark"]["status"], "complete")
            self.assertEqual(report["next_actions"], [])

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
            self.assertEqual(report["resource_mode"]["recommended"], "auto")
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


if __name__ == "__main__":
    unittest.main()
