from __future__ import annotations

import unittest

from src import qwen_farm_model


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
