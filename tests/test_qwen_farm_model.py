from __future__ import annotations

import unittest

from src import qwen_farm_model
from src.qwen_farm_model import FarmModelResult


class FakeClient:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.messages: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]], *, response_format: str | None = None, timeout: int = 600) -> str:
        self.messages.append(messages)
        return self.raw


class JsonParsingTests(unittest.TestCase):
    def test_parse_json_object_accepts_code_fence(self) -> None:
        data = qwen_farm_model.parse_json_object('```json\n{"title":"A"}\n```')

        self.assertEqual(data, {"title": "A"})

    def test_parse_json_object_extracts_object_from_text(self) -> None:
        data = qwen_farm_model.parse_json_object('Here: {"title":"A"} done')

        self.assertEqual(data, {"title": "A"})

    def test_normalize_summary_payload_supplies_defaults(self) -> None:
        payload = qwen_farm_model.normalize_summary_payload({"title": "T", "bullets": "one", "confidence": "wild"})

        self.assertEqual(
            payload,
            {
                "title": "T",
                "abstract": "",
                "bullets": ["one"],
                "open_questions": [],
                "confidence": "medium",
            },
        )

    def test_apply_agent_guidance_appends_to_system_message(self) -> None:
        messages = [{"role": "system", "content": "Base"}, {"role": "user", "content": "Hi"}]

        updated = qwen_farm_model.apply_agent_guidance(messages, "Agent rule")

        self.assertIn("Base", updated[0]["content"])
        self.assertIn("Agent guidance:", updated[0]["content"])
        self.assertIn("Agent rule", updated[0]["content"])
        self.assertEqual(messages[0]["content"], "Base")

    def test_summarize_prompt_is_source_grounded_and_neutral(self) -> None:
        messages = qwen_farm_model.summarize_messages("article.txt", "Article body")

        system = messages[0]["content"]
        self.assertIn("Use only facts present in the file content", system)
        self.assertNotIn("worker farm", system.lower())
        self.assertNotIn("qwen", system.lower())

    def test_prepare_summary_content_truncates_large_inputs_with_warning(self) -> None:
        content, warnings = qwen_farm_model.prepare_summary_content("a" * 25, max_chars=10)

        self.assertTrue(content.startswith("aaaaaaaaaa"))
        self.assertIn("Input truncated", content)
        self.assertEqual(warnings, ["input_truncated"])

    def test_summarize_mode_does_not_inject_agent_guidance(self) -> None:
        client = FakeClient(
            '{"title":"T","abstract":"A","bullets":["B"],"open_questions":[],"confidence":"high"}'
        )

        result = qwen_farm_model.process_file_with_model(
            client=client,  # type: ignore[arg-type]
            mode="summarize",
            file_path="article.txt",
            content="Article body",
            instructions=None,
            timeout=1,
            agent_system_prompt="You are a local Qwen assistant.",
        )

        self.assertIsInstance(result, FarmModelResult)
        combined = "\n".join(message["content"] for message in client.messages[0])
        self.assertNotIn("Agent guidance", combined)
        self.assertNotIn("local Qwen assistant", combined)
