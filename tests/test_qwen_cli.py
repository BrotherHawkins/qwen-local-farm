from __future__ import annotations

import argparse
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
            ],
        ):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "run")
        self.assertEqual(args.input_folder, "notes")
        self.assertEqual(args.mode, "prompt")
        self.assertEqual(args.instructions, "Summarize risks")
        self.assertEqual(args.agent, "qwen8")

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

    def test_parse_args_accepts_farm_tokenizer_status(self) -> None:
        with patch.object(sys, "argv", ["qwen.py", "farm", "tokenizer", "status", "--model", "qwen3:4b"]):
            args = qwen.parse_args()

        self.assertEqual(args.command, "farm")
        self.assertEqual(args.farm_command, "tokenizer")
        self.assertEqual(args.tokenizer_command, "status")
        self.assertEqual(args.model, ["qwen3:4b"])

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


class FarmHandlerTests(unittest.TestCase):
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
