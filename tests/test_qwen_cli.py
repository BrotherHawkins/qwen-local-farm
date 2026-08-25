from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

import qwen


class OllamaHostValueTests(unittest.TestCase):
    def test_ollama_host_value_uses_parsed_netloc(self) -> None:
        with patch.object(qwen, "OLLAMA_BASE_URL", "http://0.0.0.0:11434"):
            self.assertEqual(qwen.ollama_host_value(), "0.0.0.0:11434")

    def test_ollama_host_value_falls_back_to_default_host(self) -> None:
        with patch.object(qwen, "OLLAMA_BASE_URL", "not-a-url"):
            self.assertEqual(qwen.ollama_host_value(), "127.0.0.1:11434")


class ParseArgsTests(unittest.TestCase):
    def test_parse_args_defaults_to_status(self) -> None:
        with patch.object(sys, "argv", ["qwen.py"]):
            args = qwen.parse_args()

        self.assertEqual(args.command, "status")

    def test_parse_args_accepts_ask_agent(self) -> None:
        with patch.object(sys, "argv", ["qwen.py", "ask", "hello", "coder"]):
            args = qwen.parse_args()

        self.assertEqual(args.command, "ask")
        self.assertEqual(args.message, "hello")
        self.assertEqual(args.agent, "coder")

    def test_parse_args_accepts_farm_run(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "run",
                "notes",
                "--mode",
                "prompt",
                "--instructions",
                "Summarize risks",
                "--agent",
                "qwen8",
                "--resource-mode",
                "hybrid",
                "--include",
                "articles/*.txt",
                "--include",
                "notes/**/*.md",
                "--exclude",
                "**/raw/**",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "run")
        self.assertEqual(args.input_folder, "notes")
        self.assertEqual(args.mode, "prompt")
        self.assertEqual(args.instructions, "Summarize risks")
        self.assertEqual(args.agent, "qwen8")
        self.assertEqual(args.resource_mode, "hybrid")
        self.assertEqual(args.include, ["articles/*.txt", "notes/**/*.md"])
        self.assertEqual(args.exclude, ["**/raw/**"])

    def test_parse_args_accepts_token_chunk_overrides(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "run",
                "notes",
                "--chunk-strategy",
                "token",
                "--chunk-tokens",
                "6500",
                "--reduce-tokens",
                "6400",
                "--token-safety-margin",
                "0.15",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.chunk_strategy, "token")
        self.assertEqual(args.chunk_tokens, 6500)
        self.assertEqual(args.reduce_tokens, 6400)
        self.assertEqual(args.token_safety_margin, 0.15)

    def test_parse_args_accepts_heading_and_overlap_overrides(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "run",
                "notes",
                "--no-preserve-heading-ancestry",
                "--chunk-overlap-chars",
                "500",
                "--chunk-overlap-tokens",
                "120",
            ],
        ):
            args = qwen.parse_args()

        self.assertFalse(args.preserve_heading_ancestry)
        self.assertEqual(args.chunk_overlap_chars, 500)
        self.assertEqual(args.chunk_overlap_tokens, 120)

    def test_parse_args_accepts_snippet_overrides(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "run",
                "notes",
                "--snippets",
                "auto",
                "--snippet-max-chars",
                "800",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.snippets, "auto")
        self.assertEqual(args.snippet_max_chars, 800)

    def test_parse_args_accepts_failure_policy_overrides(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "run",
                "notes",
                "--max-attempts",
                "3",
                "--per-file-timeout-seconds",
                "900",
                "--chunk-max-attempts",
                "4",
                "--reduce-max-attempts",
                "1",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.max_attempts, 3)
        self.assertEqual(args.per_file_timeout_seconds, 900)
        self.assertEqual(args.chunk_max_attempts, 4)
        self.assertEqual(args.reduce_max_attempts, 1)

    def test_parse_args_accepts_farm_tokenizer_status(self) -> None:
        with patch.object(sys, "argv", ["qwen.py", "farm", "tokenizer", "status", "--model", "qwen3:4b"]):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "tokenizer")
        self.assertEqual(args.tokenizer_command, "status")
        self.assertEqual(args.model, ["qwen3:4b"])

    def test_parse_args_accepts_farm_doctor(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "doctor",
                "--json",
                "--output",
                ".run/reports",
                "--agent",
                "default",
                "--profile",
                "local-8gb",
                "--resource-mode",
                "auto",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "doctor")
        self.assertTrue(args.json)
        self.assertEqual(args.output, ".run/reports")
        self.assertEqual(args.agent, "default")
        self.assertEqual(args.profile, "local-8gb")
        self.assertEqual(args.resource_mode, "auto")

    def test_parse_args_accepts_farm_recommend(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "recommend",
                "--json",
                "--output",
                ".run/recommendations",
                "--agent",
                "qwen8",
                "--profile",
                "local-12gb",
                "--resource-mode",
                "gpu",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "recommend")
        self.assertTrue(args.json)
        self.assertEqual(args.output, ".run/recommendations")
        self.assertEqual(args.agent, "qwen8")
        self.assertEqual(args.profile, "local-12gb")
        self.assertEqual(args.resource_mode, "gpu")
        self.assertIsNone(args.recommend_command)

    def test_parse_args_accepts_farm_recommend_apply(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "recommend",
                "apply",
                ".run/recommendations/farm-recommendation.json",
                "--config",
                ".run/dogfood_0021/.qwen-farm.json",
                "--output",
                ".run/recommendations",
                "--write",
                "--json",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "recommend")
        self.assertEqual(args.recommend_command, "apply")
        self.assertEqual(args.recommendation_path, ".run/recommendations/farm-recommendation.json")
        self.assertEqual(args.config, ".run/dogfood_0021/.qwen-farm.json")
        self.assertEqual(args.output, ".run/recommendations")
        self.assertTrue(args.write)
        self.assertTrue(args.json)

    def test_parse_args_accepts_farm_schema_validate(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "schema",
                "validate",
                "artifact.json",
                "--schema",
                "schemas/farm-doctor.schema.json",
                "--json",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "schema")
        self.assertEqual(args.schema_command, "validate")
        self.assertEqual(args.json_path, "artifact.json")
        self.assertEqual(args.schema, "schemas/farm-doctor.schema.json")
        self.assertTrue(args.json)

    def test_parse_args_accepts_farm_collect(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "collect",
                "farm-run-test",
                "--output",
                ".run/collections",
                "--label",
                "review",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "collect")
        self.assertEqual(args.run_dir, "farm-run-test")
        self.assertEqual(args.output, ".run/collections")
        self.assertEqual(args.label, "review")

    def test_parse_args_accepts_farm_retry_failed(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "retry-failed",
                "farm-run-test",
                "--output",
                ".run/retries",
                "--instructions",
                "Retry with care.",
                "--agent",
                "qwen8",
                "--json",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "retry-failed")
        self.assertEqual(args.run_dir, "farm-run-test")
        self.assertEqual(args.output, ".run/retries")
        self.assertEqual(args.instructions, "Retry with care.")
        self.assertEqual(args.agent, "qwen8")
        self.assertTrue(args.json)

    def test_parse_args_accepts_farm_status_run_id(self) -> None:
        with patch.object(sys, "argv", ["qwen.py", "farm", "status", "farm-run-1"]):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "status")
        self.assertEqual(args.run_id, "farm-run-1")
        self.assertFalse(args.json)

    def test_parse_args_accepts_farm_status_json_overview(self) -> None:
        with patch.object(sys, "argv", ["qwen.py", "farm", "status", "--json"]):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "status")
        self.assertIsNone(args.run_id)
        self.assertTrue(args.json)

    def test_parse_args_accepts_farm_status_json_run_id(self) -> None:
        with patch.object(sys, "argv", ["qwen.py", "farm", "status", "farm-run-1", "--json"]):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "status")
        self.assertEqual(args.run_id, "farm-run-1")
        self.assertTrue(args.json)

    def test_parse_args_accepts_farm_status_json_before_run_id(self) -> None:
        with patch.object(sys, "argv", ["qwen.py", "farm", "status", "--json", "farm-run-1"]):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "status")
        self.assertEqual(args.run_id, "farm-run-1")
        self.assertTrue(args.json)

    def test_parse_args_accepts_farm_dogfood_record(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "dogfood",
                "record",
                ".run/farm-results/run-1",
                "--label",
                "candidate",
                "--notes",
                "notes.json",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "dogfood")
        self.assertEqual(args.dogfood_command, "record")
        self.assertEqual(args.run_dir, ".run/farm-results/run-1")
        self.assertEqual(args.label, "candidate")
        self.assertEqual(args.notes, "notes.json")

    def test_parse_args_accepts_farm_dogfood_compare(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "dogfood",
                "compare",
                "baseline.json",
                "candidate.json",
                "--output",
                ".run/dogfood_history/comparisons",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "dogfood")
        self.assertEqual(args.dogfood_command, "compare")
        self.assertEqual(args.baseline_record, "baseline.json")
        self.assertEqual(args.candidate_record, "candidate.json")
        self.assertEqual(args.output, ".run/dogfood_history/comparisons")

    def test_parse_args_accepts_farm_dogfood_timing_record(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "dogfood",
                "timing",
                "record",
                ".run/farm-results/run-1",
                "--label",
                "timing-candidate",
                "--output",
                ".run/dogfood_timing/runs",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "dogfood")
        self.assertEqual(args.dogfood_command, "timing")
        self.assertEqual(args.timing_command, "record")
        self.assertEqual(args.run_dir, ".run/farm-results/run-1")
        self.assertEqual(args.label, "timing-candidate")
        self.assertEqual(args.output, ".run/dogfood_timing/runs")

    def test_parse_args_accepts_farm_dogfood_timing_compare(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "dogfood",
                "timing",
                "compare",
                "baseline.json",
                "candidate.json",
                "--output",
                ".run/dogfood_timing/comparisons",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "dogfood")
        self.assertEqual(args.dogfood_command, "timing")
        self.assertEqual(args.timing_command, "compare")
        self.assertEqual(args.baseline_record, "baseline.json")
        self.assertEqual(args.candidate_record, "candidate.json")
        self.assertEqual(args.output, ".run/dogfood_timing/comparisons")

    def test_parse_args_accepts_farm_snippets_pack(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "snippets",
                "pack",
                ".run/farm-results/run-1",
                "--label",
                "dogfood-lite",
                "--output",
                ".run/snippet_packs",
                "--max-snippets",
                "12",
                "--per-file",
                "3",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "snippets")
        self.assertEqual(args.snippets_command, "pack")
        self.assertEqual(args.run_dir, ".run/farm-results/run-1")
        self.assertEqual(args.label, "dogfood-lite")
        self.assertEqual(args.output, ".run/snippet_packs")
        self.assertEqual(args.max_snippets, 12)
        self.assertEqual(args.per_file, 3)

    def test_parse_args_accepts_farm_synthesis_bundle(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "qwen.py",
                "farm",
                "synthesis",
                "bundle",
                ".run/farm-results/run-1",
                "--label",
                "dogfood-lite",
                "--output",
                ".run/synthesis_bundles",
                "--max-snippets",
                "12",
                "--per-file",
                "3",
                "--max-chars",
                "60000",
                "--max-estimated-tokens",
                "15000",
                "--chars-per-token",
                "4.5",
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "synthesis")
        self.assertEqual(args.synthesis_command, "bundle")
        self.assertEqual(args.run_dir, ".run/farm-results/run-1")
        self.assertEqual(args.label, "dogfood-lite")
        self.assertEqual(args.output, ".run/synthesis_bundles")
        self.assertEqual(args.max_snippets, 12)
        self.assertEqual(args.per_file, 3)
        self.assertEqual(args.max_chars, 60000)
        self.assertEqual(args.max_estimated_tokens, 15000)
        self.assertEqual(args.chars_per_token, 4.5)


class FarmHandlerTests(unittest.TestCase):
    def test_schema_validate_json_prints_result(self) -> None:
        args = argparse.Namespace(
            farm_command="schema",
            schema_command="validate",
            json_path="artifact.json",
            schema="schemas/farm-doctor.schema.json",
            json=True,
        )
        result = {"schema_version": 1, "valid": True, "exit_code": 0, "errors": []}

        with (
            patch("src.qwen_farm_schema.validate_artifact", return_value=result) as validate_artifact,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        validate_artifact.assert_called_once_with(
            root=qwen.ROOT,
            artifact_path=Path("artifact.json"),
            schema_reference="schemas/farm-doctor.schema.json",
        )
        printed.assert_called_once()
        self.assertEqual(json.loads(printed.call_args.args[0]), result)

    def test_schema_validate_markdown_prints_result(self) -> None:
        args = argparse.Namespace(
            farm_command="schema",
            schema_command="validate",
            json_path="artifact.json",
            schema=None,
            json=False,
        )
        result = {"schema_version": 1, "valid": True, "exit_code": 0, "errors": []}

        with (
            patch("src.qwen_farm_schema.validate_artifact", return_value=result),
            patch("src.qwen_farm_schema.render_validation_result", return_value="Valid: artifact.json") as render,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        render.assert_called_once_with(result)
        printed.assert_called_once_with("Valid: artifact.json")

    def test_schema_validate_exits_on_validation_failure(self) -> None:
        args = argparse.Namespace(
            farm_command="schema",
            schema_command="validate",
            json_path="artifact.json",
            schema=None,
            json=False,
        )
        result = {"schema_version": 1, "valid": False, "exit_code": 1, "errors": ["bad"]}

        with (
            patch("src.qwen_farm_schema.validate_artifact", return_value=result),
            patch("src.qwen_farm_schema.render_validation_result", return_value="Invalid: artifact.json"),
            patch("builtins.print"),
        ):
            with self.assertRaises(SystemExit) as raised:
                qwen.handle_farm(args)

        self.assertEqual(raised.exception.code, 1)

    def test_schema_validate_exits_on_input_error(self) -> None:
        args = argparse.Namespace(
            farm_command="schema",
            schema_command="validate",
            json_path="missing.json",
            schema=None,
            json=True,
        )
        result = {"schema_version": 1, "valid": False, "exit_code": 2, "errors": ["missing"]}

        with (
            patch("src.qwen_farm_schema.validate_artifact", return_value=result),
            patch("builtins.print"),
        ):
            with self.assertRaises(SystemExit) as raised:
                qwen.handle_farm(args)

        self.assertEqual(raised.exception.code, 2)

    def test_farm_doctor_json_prints_json_report(self) -> None:
        args = argparse.Namespace(
            farm_command="doctor",
            json=True,
            output="out",
            agent="default",
            profile="local-8gb",
            resource_mode="cpu",
        )
        report = {"schema_version": 1, "status": "ready"}

        with (
            patch("src.qwen_farm_doctor.build_doctor_report", return_value=report) as build,
            patch("src.qwen_farm_doctor.write_doctor_report") as write,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        self.assertEqual(build.call_args.kwargs["root"], qwen.ROOT)
        self.assertEqual(build.call_args.kwargs["agent_id"], "default")
        self.assertEqual(build.call_args.kwargs["profile"], "local-8gb")
        self.assertEqual(build.call_args.kwargs["resource_mode"], "cpu")
        write.assert_called_once_with(report)
        printed.assert_called_once()
        self.assertEqual(json.loads(printed.call_args.args[0]), report)

    def test_farm_doctor_markdown_prints_markdown_report(self) -> None:
        args = argparse.Namespace(
            farm_command="doctor",
            json=False,
            output=None,
            agent="default",
            profile=None,
            resource_mode=None,
        )
        report = {"schema_version": 1, "status": "ready"}

        with (
            patch("src.qwen_farm_doctor.build_doctor_report", return_value=report),
            patch("src.qwen_farm_doctor.write_doctor_report"),
            patch("src.qwen_farm_doctor.render_doctor_markdown", return_value="# Farm Doctor") as render,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        render.assert_called_once_with(report)
        printed.assert_called_once_with("# Farm Doctor")

    def test_farm_recommend_json_prints_json_report(self) -> None:
        args = argparse.Namespace(
            farm_command="recommend",
            recommend_command=None,
            json=True,
            output="out",
            agent="default",
            profile="local-8gb",
            resource_mode="hybrid",
        )
        report = {"schema_version": 1, "status": "ready"}

        with (
            patch("src.qwen_farm_recommend.build_recommendation_report", return_value=report) as build,
            patch("src.qwen_farm_recommend.write_recommendation_report", return_value=(Path("rec.json"), Path("rec.md"))) as write,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        self.assertEqual(build.call_args.kwargs["root"], qwen.ROOT)
        self.assertEqual(build.call_args.kwargs["agent_id"], "default")
        self.assertEqual(build.call_args.kwargs["profile"], "local-8gb")
        self.assertEqual(build.call_args.kwargs["resource_mode"], "hybrid")
        self.assertEqual(build.call_args.kwargs["output_dir"], Path("out"))
        write.assert_called_once_with(report)
        printed.assert_called_once()
        self.assertEqual(json.loads(printed.call_args.args[0]), report)

    def test_farm_recommend_markdown_prints_paths(self) -> None:
        args = argparse.Namespace(
            farm_command="recommend",
            recommend_command=None,
            json=False,
            output=None,
            agent="default",
            profile=None,
            resource_mode=None,
        )
        report = {"schema_version": 1, "status": "ready"}

        with (
            patch("src.qwen_farm_recommend.build_recommendation_report", return_value=report),
            patch("src.qwen_farm_recommend.write_recommendation_report", return_value=(Path("rec.json"), Path("rec.md"))),
            patch("src.qwen_farm_recommend.render_recommendation_markdown", return_value="# Farm Recommendation") as render,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        render.assert_called_once_with(report)
        printed.assert_has_calls(
            [
                call("# Farm Recommendation"),
                call("Recommendation JSON: rec.json"),
                call("Recommendation Markdown: rec.md"),
            ]
        )

    def test_farm_recommend_apply_json_prints_json_report(self) -> None:
        args = argparse.Namespace(
            farm_command="recommend",
            recommend_command="apply",
            recommendation_path="rec.json",
            config="config.json",
            output="out",
            write=True,
            json=True,
        )
        report = {"schema_version": 1, "status": "applied"}

        with (
            patch("src.qwen_farm_recommend.build_config_apply_report", return_value=report) as build,
            patch("src.qwen_farm_recommend.write_config_apply_report", return_value=(Path("apply.json"), Path("apply.md"))) as write,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        self.assertEqual(build.call_args.kwargs["root"], qwen.ROOT)
        self.assertEqual(build.call_args.kwargs["recommendation_path"], Path("rec.json"))
        self.assertEqual(build.call_args.kwargs["config_path"], Path("config.json"))
        self.assertEqual(build.call_args.kwargs["output_dir"], Path("out"))
        self.assertTrue(build.call_args.kwargs["write"])
        write.assert_called_once_with(report)
        printed.assert_called_once()
        self.assertEqual(json.loads(printed.call_args.args[0]), report)

    def test_farm_recommend_apply_markdown_prints_paths(self) -> None:
        args = argparse.Namespace(
            farm_command="recommend",
            recommend_command="apply",
            recommendation_path=None,
            config=None,
            output=None,
            write=False,
            json=False,
        )
        report = {"schema_version": 1, "status": "preview"}

        with (
            patch("src.qwen_farm_recommend.build_config_apply_report", return_value=report),
            patch("src.qwen_farm_recommend.write_config_apply_report", return_value=(Path("apply.json"), Path("apply.md"))),
            patch("src.qwen_farm_recommend.render_config_apply_markdown", return_value="# Farm Config Apply") as render,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        render.assert_called_once_with(report)
        printed.assert_has_calls(
            [
                call("# Farm Config Apply"),
                call("Apply JSON: apply.json"),
                call("Apply Markdown: apply.md"),
            ]
        )

    def test_status_json_prints_json_envelope(self) -> None:
        args = argparse.Namespace(farm_command="status", run_id="farm-run-1", json=True)
        envelope = {"schema_version": 1, "scope": "run", "run_id": "farm-run-1", "run": {"run_id": "farm-run-1"}}

        with (
            patch("src.qwen_farm.status_json", return_value=envelope) as status_json,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        status_json.assert_called_once_with(qwen.ROOT, "farm-run-1")
        printed.assert_called_once()
        self.assertEqual(json.loads(printed.call_args.args[0]), envelope)

    def test_status_markdown_stays_default(self) -> None:
        args = argparse.Namespace(farm_command="status", run_id=None, json=False)

        with (
            patch("src.qwen_farm.status_text", return_value="# Farm Overview") as status_text,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        status_text.assert_called_once_with(qwen.ROOT, None)
        printed.assert_has_calls([call("# Farm Overview")])

    def test_retry_failed_json_prints_json_result(self) -> None:
        resolved = Path("resolved-run")
        args = argparse.Namespace(
            farm_command="retry-failed",
            run_dir="farm-run-1",
            output="out",
            instructions="Retry instructions.",
            agent="qwen8",
            json=True,
        )
        plan = {"model": "qwen-test:1b"}
        status = {"run_id": "farm-run-2", "status": "complete", "output": {"path": "out/farm-run-2"}}
        result = {
            "schema_version": 1,
            "status": "complete",
            "source_run": {"run_id": "farm-run-1"},
            "retry_run": {"run_id": "farm-run-2"},
            "failure_counts": {"retryable": 1, "non_retryable": 0, "unknown": 0},
            "selected_jobs": [],
            "counts": {},
            "warnings": [],
            "errors": [],
        }

        with (
            patch("src.qwen_farm.resolve_run_reference", return_value=resolved) as resolve,
            patch("src.qwen_farm.build_retry_failed_plan", return_value=plan) as build,
            patch("qwen.ensure_model") as ensure,
            patch("src.qwen_farm.run_retry_failed_plan", return_value=(status, result)) as run_retry,
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        resolve.assert_called_once_with(qwen.ROOT, "farm-run-1")
        self.assertEqual(build.call_args.kwargs["source_run_dir"], resolved)
        self.assertEqual(build.call_args.kwargs["instructions"], "Retry instructions.")
        self.assertEqual(build.call_args.kwargs["agent_id"], "qwen8")
        ensure.assert_called_once_with("qwen-test:1b")
        self.assertEqual(run_retry.call_args.kwargs["output_dir"], Path("out"))
        printed.assert_called_once()
        self.assertEqual(json.loads(printed.call_args.args[0]), result)

    def test_retry_failed_json_keeps_model_status_off_stdout(self) -> None:
        resolved = Path("resolved-run")
        args = argparse.Namespace(
            farm_command="retry-failed",
            run_dir="farm-run-1",
            output="out",
            instructions=None,
            agent=None,
            json=True,
        )
        plan = {"model": "qwen-test:1b"}
        status = {"run_id": "farm-run-2", "status": "complete", "output": {"path": "out/farm-run-2"}}
        result = {
            "schema_version": 1,
            "status": "complete",
            "source_run": {"run_id": "farm-run-1"},
            "retry_run": {"run_id": "farm-run-2"},
            "failure_counts": {"retryable": 1, "non_retryable": 0, "unknown": 0},
            "selected_jobs": [],
            "counts": {},
            "warnings": [],
            "errors": [],
        }
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("src.qwen_farm.resolve_run_reference", return_value=resolved),
            patch("src.qwen_farm.build_retry_failed_plan", return_value=plan),
            patch("qwen.ensure_model", side_effect=lambda _model: sys.stdout.write("Model is available\n")),
            patch("src.qwen_farm.run_retry_failed_plan", return_value=(status, result)),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            qwen.handle_farm(args)

        self.assertEqual(json.loads(stdout.getvalue()), result)
        self.assertNotIn("Model is available", stdout.getvalue())
        self.assertIn("Model is available", stderr.getvalue())

    def test_retry_failed_markdown_prints_summary(self) -> None:
        args = argparse.Namespace(
            farm_command="retry-failed",
            run_dir="farm-run-1",
            output=None,
            instructions=None,
            agent=None,
            json=False,
        )
        status = {"run_id": "farm-run-2", "status": "complete", "output": {"path": ".run/farm/farm-run-2"}}
        result = {
            "source_run": {"run_id": "farm-run-1"},
            "retry_run": {"retried_jobs": 1},
            "failure_counts": {"retryable": 0, "non_retryable": 1, "unknown": 0},
            "warnings": ["Source run does not contain request.instructions; retrying without prior instructions."],
        }

        with (
            patch("src.qwen_farm.resolve_run_reference", return_value=Path("resolved-run")),
            patch("src.qwen_farm.build_retry_failed_plan", return_value={"model": "qwen-test:1b"}),
            patch("qwen.ensure_model"),
            patch("src.qwen_farm.run_retry_failed_plan", return_value=(status, result)),
            patch("builtins.print") as printed,
        ):
            qwen.handle_farm(args)

        printed.assert_has_calls(
            [
                call("Retry run complete: farm-run-2"),
                call("Source run: farm-run-1"),
                call("Retried files: 1"),
                call("Selected failures: 0 retryable, 1 non-retryable, 0 unknown"),
                call("Status: complete"),
                call("Output: .run/farm/farm-run-2"),
                call("Warning: Source run does not contain request.instructions; retrying without prior instructions."),
            ]
        )

    def test_retry_failed_json_error_exits_nonzero(self) -> None:
        args = argparse.Namespace(
            farm_command="retry-failed",
            run_dir="farm-run-1",
            output=None,
            instructions=None,
            agent=None,
            json=True,
        )

        with (
            patch("src.qwen_farm.resolve_run_reference", return_value=Path("resolved-run")),
            patch("src.qwen_farm.build_retry_failed_plan", side_effect=ValueError("Source run has no failed jobs.")),
            patch("builtins.print") as printed,
        ):
            with self.assertRaises(SystemExit) as raised:
                qwen.handle_farm(args)

        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(json.loads(printed.call_args.args[0])["errors"], ["Source run has no failed jobs."])

    def test_snippets_pack_resolves_run_reference_before_building_pack(self) -> None:
        resolved = Path("resolved-run")
        args = argparse.Namespace(
            farm_command="snippets",
            snippets_command="pack",
            run_dir="farm-run-1",
            output="out",
            label="label",
            max_snippets=5,
            per_file=2,
        )

        with (
            patch("src.qwen_farm.resolve_run_reference", return_value=resolved) as resolve,
            patch("src.qwen_farm_snippet_packs.build_snippet_pack", return_value={"counts": {"selected": 1}}) as build,
            patch("src.qwen_farm_snippet_packs.write_snippet_pack", return_value=(Path("pack.json"), Path("pack.md"))),
            patch("builtins.print"),
        ):
            qwen.handle_farm(args)

        resolve.assert_called_once_with(qwen.ROOT, "farm-run-1")
        self.assertEqual(build.call_args.kwargs["run_dir"], resolved)

    def test_synthesis_bundle_resolves_run_reference_before_building_bundle(self) -> None:
        resolved = Path("resolved-run")
        args = argparse.Namespace(
            farm_command="synthesis",
            synthesis_command="bundle",
            run_dir="farm-run-1",
            output="out",
            label="label",
            max_snippets=5,
            per_file=2,
            max_chars=60000,
            max_estimated_tokens=15000,
            chars_per_token=4.5,
        )

        with (
            patch("src.qwen_farm.resolve_run_reference", return_value=resolved) as resolve,
            patch(
                "src.qwen_farm_synthesis_bundles.build_synthesis_bundle",
                return_value={"counts": {"items": 1, "snippets_selected": 1}},
            ) as build,
            patch(
                "src.qwen_farm_synthesis_bundles.write_synthesis_bundle",
                return_value=(Path("bundle.json"), Path("bundle.md")),
            ),
            patch("builtins.print"),
        ):
            qwen.handle_farm(args)

        resolve.assert_called_once_with(qwen.ROOT, "farm-run-1")
        self.assertEqual(build.call_args.kwargs["run_dir"], resolved)
        self.assertEqual(build.call_args.kwargs["max_chars"], 60000)
        self.assertEqual(build.call_args.kwargs["max_estimated_tokens"], 15000)
        self.assertEqual(build.call_args.kwargs["chars_per_token"], 4.5)

    def test_dogfood_record_resolves_run_reference_before_building_record(self) -> None:
        resolved = Path("resolved-run")
        args = argparse.Namespace(
            farm_command="dogfood",
            dogfood_command="record",
            run_dir="farm-run-1",
            output="out",
            label="label",
            notes=None,
        )

        with (
            patch("src.qwen_farm.resolve_run_reference", return_value=resolved) as resolve,
            patch(
                "src.qwen_farm_dogfood.build_quality_record",
                return_value={"label": "label", "run_id": "farm-run-1"},
            ) as build,
            patch("src.qwen_farm_dogfood.write_quality_record", return_value=Path("record.json")),
            patch("builtins.print"),
        ):
            qwen.handle_farm(args)

        resolve.assert_called_once_with(qwen.ROOT, "farm-run-1")
        self.assertEqual(build.call_args.kwargs["run_dir"], resolved)

    def test_dogfood_timing_record_resolves_run_reference_before_building_record(self) -> None:
        resolved = Path("resolved-run")
        args = argparse.Namespace(
            farm_command="dogfood",
            dogfood_command="timing",
            timing_command="record",
            run_dir="farm-run-1",
            output="out",
            label="label",
        )

        with (
            patch("src.qwen_farm.resolve_run_reference", return_value=resolved) as resolve,
            patch(
                "src.qwen_farm_dogfood_timing.build_timing_record",
                return_value={"label": "label", "run_id": "farm-run-1", "totals": {"duration_ms": 1000}},
            ) as build,
            patch("src.qwen_farm_dogfood_timing.write_timing_record", return_value=Path("record.json")),
            patch("builtins.print"),
        ):
            qwen.handle_farm(args)

        resolve.assert_called_once_with(qwen.ROOT, "farm-run-1")
        self.assertEqual(build.call_args.kwargs["run_dir"], resolved)

    def test_dogfood_timing_compare_writes_json_and_markdown(self) -> None:
        args = argparse.Namespace(
            farm_command="dogfood",
            dogfood_command="timing",
            timing_command="compare",
            baseline_record="baseline.json",
            candidate_record="candidate.json",
            output="out",
        )
        baseline = {"label": "baseline"}
        candidate = {"label": "candidate"}
        comparison = {"baseline": baseline, "candidate": candidate}

        with (
            patch("src.qwen_farm_dogfood_timing.read_json_object", side_effect=[baseline, candidate]) as read_json,
            patch("src.qwen_farm_dogfood_timing.compare_timing_records", return_value=comparison) as compare,
            patch(
                "src.qwen_farm_dogfood_timing.write_timing_comparison",
                return_value=(Path("comparison.json"), Path("comparison.md")),
            ) as write,
            patch("builtins.print"),
        ):
            qwen.handle_farm(args)

        read_json.assert_has_calls([call(Path("baseline.json")), call(Path("candidate.json"))])
        compare.assert_called_once_with(baseline, candidate)
        write.assert_called_once_with(comparison, Path("out"))
