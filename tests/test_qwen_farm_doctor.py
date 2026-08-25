from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import qwen_farm_doctor


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


class FarmDoctorTests(unittest.TestCase):
    def test_build_doctor_report_ready_with_fake_ollama_and_tokenizers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            report = qwen_farm_doctor.build_doctor_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                generated_at="2026-08-24T00:00:00Z",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: {"models": [{"name": "qwen3.5:4b"}]},
                tokenizer_status_fn=ready_tokenizers,
                platform_name="TestOS",
                python_version=(3, 13, 0),
            )

            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["status"], "ready")
            self.assertEqual(report["environment"]["os"], "TestOS")
            self.assertTrue(report["ollama"]["endpoint_ready"])
            self.assertEqual(report["ollama"]["models"], ["qwen3.5:4b"])
            self.assertEqual(report["agent"]["model"], "qwen3.5:4b")
            self.assertEqual(report["agent"]["model_metadata"]["family"], "qwen")
            self.assertEqual(report["agent"]["model_metadata"]["backend"], "ollama")
            self.assertEqual(report["agent"]["model_metadata"]["support"], "tested")
            self.assertTrue(report["agent"]["model_installed"])
            self.assertEqual(report["runtime"]["profile"], "local-8gb")
            self.assertEqual(report["runtime"]["resource_mode"]["requested"], "auto")
            self.assertEqual(report["runtime"]["resource_mode"]["effective"], "gpu")
            self.assertTrue(report["tokenizers"]["ready"])
            self.assertEqual(report["runs"], {"known_count": 0, "latest": []})
            self.assertEqual(report["profile_recommendation"]["status"], "missing")
            self.assertIn("setup-doctor.md", report["report_paths"]["markdown"])

    def test_missing_ollama_is_needs_setup_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            report = qwen_farm_doctor.build_doctor_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                find_ollama_fn=lambda: None,
                request_json_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("connection refused")),
                tokenizer_status_fn=ready_tokenizers,
            )

            self.assertEqual(report["status"], "needs_setup")
            self.assertFalse(report["ollama"]["found"])
            self.assertFalse(report["ollama"]["endpoint_ready"])
            self.assertIn("ollama.install", [item["id"] for item in report["recommendations"]])

    def test_unreachable_endpoint_is_warning_when_executable_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            report = qwen_farm_doctor.build_doctor_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("connection refused")),
                tokenizer_status_fn=ready_tokenizers,
            )

            self.assertEqual(report["status"], "ready_with_warnings")
            self.assertEqual(report["agent"]["model_installed"], "unknown")
            self.assertIn("ollama.start", [item["id"] for item in report["recommendations"]])

    def test_missing_selected_model_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            report = qwen_farm_doctor.build_doctor_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: {"models": [{"name": "other:1b"}]},
                tokenizer_status_fn=ready_tokenizers,
            )

            self.assertEqual(report["status"], "ready_with_warnings")
            self.assertFalse(report["agent"]["model_installed"])
            self.assertIn("model.setup", [item["id"] for item in report["recommendations"]])

    def test_missing_tokenizer_readiness_is_optional_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            report = qwen_farm_doctor.build_doctor_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: {"models": [{"name": "qwen3.5:4b"}]},
                tokenizer_status_fn=missing_tokenizers,
            )

            self.assertEqual(report["status"], "ready_with_warnings")
            self.assertFalse(report["tokenizers"]["ready"])
            self.assertIn("tokenizer.setup", [item["id"] for item in report["recommendations"]])

    def test_render_markdown_includes_major_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = qwen_farm_doctor.build_doctor_report(
                root=Path(temp_dir),
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: {"models": [{"name": "qwen3.5:4b"}]},
                tokenizer_status_fn=ready_tokenizers,
            )

            markdown = qwen_farm_doctor.render_doctor_markdown(report)

            self.assertIn("# Farm Doctor", markdown)
            self.assertIn("## Ollama", markdown)
            self.assertIn("## Agent And Runtime", markdown)
            self.assertIn("Resource mode effective", markdown)
            self.assertIn("Model family: `qwen`", markdown)
            self.assertIn("Model support: `tested`", markdown)
            self.assertIn("## Profile Recommendation", markdown)
            self.assertIn("## Recommendations", markdown)

    def test_doctor_reports_experimental_non_qwen_agent_metadata(self) -> None:
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

            report = qwen_farm_doctor.build_doctor_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                agent_id="llama-local",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: {"models": [{"name": "llama3.1:8b"}]},
                tokenizer_status_fn=ready_tokenizers,
            )

            markdown = qwen_farm_doctor.render_doctor_markdown(report)

            self.assertEqual(report["agent"]["model_metadata"]["family"], "llama")
            self.assertEqual(report["agent"]["model_metadata"]["support"], "experimental")
            self.assertIn("Model family: `llama`", markdown)
            self.assertIn("Model support: `experimental`", markdown)

    def test_doctor_reports_latest_profile_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recommendation_dir = root / ".run" / "recommendations"
            recommendation_dir.mkdir(parents=True)
            (recommendation_dir / "farm-recommendation.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "generated_at": "2026-08-24T00:00:00Z",
                        "agent": "default",
                        "model": "qwen3.5:4b",
                        "resource_mode": {"recommended": "hybrid"},
                        "profile": {"recommended": "local-8gb"},
                        "concurrency": {
                            "parallel_jobs": {"recommended": 1},
                            "ollama_num_parallel": {"recommended": 1},
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = qwen_farm_doctor.build_doctor_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: {"models": [{"name": "qwen3.5:4b"}]},
                tokenizer_status_fn=ready_tokenizers,
            )

            self.assertTrue(report["profile_recommendation"]["exists"])
            self.assertEqual(report["profile_recommendation"]["profile"], "local-8gb")
            self.assertEqual(report["profile_recommendation"]["resource_mode"], "hybrid")

    def test_write_doctor_report_writes_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "reports"
            report = qwen_farm_doctor.build_doctor_report(
                root=root,
                default_model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                output_dir=output,
                find_ollama_fn=lambda: "ollama",
                request_json_fn=lambda *_args, **_kwargs: {"models": [{"name": "qwen3.5:4b"}]},
                tokenizer_status_fn=ready_tokenizers,
            )

            markdown_path, json_path = qwen_farm_doctor.write_doctor_report(report)

            self.assertEqual(markdown_path, output / "setup-doctor.md")
            self.assertEqual(json_path, output / "setup-doctor.json")
            self.assertIn("# Farm Doctor", markdown_path.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["schema_version"], 1)

    def test_calculate_report_status(self) -> None:
        self.assertEqual(qwen_farm_doctor.calculate_report_status([]), "unknown")
        self.assertEqual(qwen_farm_doctor.calculate_report_status([{"status": "ok"}]), "ready")
        self.assertEqual(qwen_farm_doctor.calculate_report_status([{"status": "warn"}]), "ready_with_warnings")
        self.assertEqual(qwen_farm_doctor.calculate_report_status([{"status": "unknown"}]), "ready_with_warnings")
        self.assertEqual(qwen_farm_doctor.calculate_report_status([{"status": "fail"}]), "needs_setup")


if __name__ == "__main__":
    unittest.main()
