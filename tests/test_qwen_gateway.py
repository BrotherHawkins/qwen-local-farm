from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import qwen_gateway


class JsonFileTests(unittest.TestCase):
    def test_read_json_file_returns_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "agent.json"
            path.write_text(json.dumps({"id": "helper"}), encoding="utf-8")

            self.assertEqual(qwen_gateway.read_json_file(path), {"id": "helper"})

    def test_read_json_file_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "agent.json"
            path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

            with self.assertRaises(ValueError):
                qwen_gateway.read_json_file(path)


class AgentLoadingTests(unittest.TestCase):
    def test_load_agents_applies_defaults_and_file_stem_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agents_dir = Path(temp_dir)
            (agents_dir / "worker.json").write_text(json.dumps({"name": "Worker"}), encoding="utf-8")

            with patch.object(qwen_gateway, "AGENTS_DIR", agents_dir), patch.object(
                qwen_gateway, "DEFAULT_MODEL", "qwen-test:1b"
            ):
                agents = qwen_gateway.load_agents()

        self.assertEqual(sorted(agents), ["worker"])
        self.assertEqual(agents["worker"]["id"], "worker")
        self.assertEqual(agents["worker"]["name"], "Worker")
        self.assertEqual(agents["worker"]["model"], "qwen-test:1b")
        self.assertEqual(agents["worker"]["system_prompt"], "")
        self.assertEqual(agents["worker"]["options"], {})

    def test_public_agent_hides_system_prompt(self) -> None:
        agent = {
            "id": "coder",
            "name": "Coder",
            "model": "qwen-test:1b",
            "system_prompt": "private rails",
            "options": {"temperature": 0.2},
        }

        self.assertEqual(
            qwen_gateway.public_agent(agent),
            {
                "id": "coder",
                "name": "Coder",
                "model": "qwen-test:1b",
                "model_metadata": {
                    "model": "qwen-test:1b",
                    "backend": "ollama",
                    "family": "qwen",
                    "support": "experimental",
                    "tokenizer": {
                        "strategy": "none",
                        "id": None,
                        "exact": False,
                    },
                    "context": {
                        "tokens": None,
                        "source": None,
                    },
                },
                "options": {"temperature": 0.2},
            },
        )


class MessageNormalizationTests(unittest.TestCase):
    def test_messages_for_agent_inserts_system_prompt_for_single_message(self) -> None:
        agent = {"system_prompt": "Be concise."}

        messages = qwen_gateway.messages_for_agent(agent, {"message": "Hello"})

        self.assertEqual(
            messages,
            [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Hello"},
            ],
        )

    def test_messages_for_agent_keeps_existing_system_message(self) -> None:
        agent = {"system_prompt": "Default system prompt."}
        body = {
            "messages": [
                {"role": "system", "content": "Caller system prompt."},
                {"role": "user", "content": "Hello"},
            ]
        }

        messages = qwen_gateway.messages_for_agent(agent, body)

        self.assertEqual(messages, body["messages"])

    def test_messages_for_agent_requires_message_or_messages(self) -> None:
        with self.assertRaises(ValueError):
            qwen_gateway.messages_for_agent({}, {})

    def test_messages_for_agent_rejects_non_list_messages(self) -> None:
        with self.assertRaises(ValueError):
            qwen_gateway.messages_for_agent({}, {"messages": "hello"})
