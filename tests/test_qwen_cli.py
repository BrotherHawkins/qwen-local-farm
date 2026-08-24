from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

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
