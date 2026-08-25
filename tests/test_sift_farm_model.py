from __future__ import annotations

import unittest

from src import sift_farm_model
from src.sift_farm_model import FarmModelResult


class FakeClient:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.calls: list[dict[str, object]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: str | None = None,
        timeout: int = 600,
        think: bool | None = None,
    ) -> str:
        self.calls.append(
            {
                "messages": messages,
                "response_format": response_format,
                "timeout": timeout,
                "think": think,
            }
        )
        return self.raw


class JsonParsingTests(unittest.TestCase):
    def test_parse_json_object_accepts_code_fence(self) -> None:
        data = sift_farm_model.parse_json_object('```json\n{"title":"A"}\n```')

        self.assertEqual(data, {"title": "A"})

    def test_parse_json_object_extracts_object_from_text(self) -> None:
        data = sift_farm_model.parse_json_object('Here: {"title":"A"} done')

        self.assertEqual(data, {"title": "A"})

    def test_normalize_summary_payload_supplies_defaults(self) -> None:
        payload = sift_farm_model.normalize_summary_payload({"title": "T", "bullets": "one", "confidence": "wild"})

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

    def test_parse_labeled_summary_builds_payload(self) -> None:
        raw = "\n".join(
            [
                "TITLE: Example",
                "ABSTRACT: A compact article summary.",
                "KEY POINTS:",
                "- first point",
                "- second point",
                "OPEN QUESTIONS:",
                "- None",
                "CONFIDENCE: high",
            ]
        )

        payload, valid = sift_farm_model.parse_summary_response(raw)

        self.assertTrue(valid)
        self.assertEqual(payload["title"], "Example")
        self.assertEqual(payload["bullets"], ["first point", "second point"])
        self.assertEqual(payload["open_questions"], [])
        self.assertEqual(payload["confidence"], "high")

    def test_parse_labeled_summary_reads_snippet_candidates(self) -> None:
        raw = "\n".join(
            [
                "TITLE: Example",
                "ABSTRACT: A compact article summary.",
                "KEY POINTS:",
                "- first point",
                "OPEN QUESTIONS:",
                "- None",
                "SOURCE SNIPPETS:",
                "- TEXT: Exact source passage.",
                "  REASON: Captures the thesis.",
                "CONFIDENCE: high",
            ]
        )

        payload, valid = sift_farm_model.parse_summary_response(raw)

        self.assertTrue(valid)
        self.assertEqual(payload["snippets"], [{"text": "Exact source passage.", "reason": "Captures the thesis."}])

    def test_apply_agent_guidance_appends_to_system_message(self) -> None:
        messages = [{"role": "system", "content": "Base"}, {"role": "user", "content": "Hi"}]

        updated = sift_farm_model.apply_agent_guidance(messages, "Agent rule")

        self.assertIn("Base", updated[0]["content"])
        self.assertIn("Agent guidance:", updated[0]["content"])
        self.assertIn("Agent rule", updated[0]["content"])
        self.assertEqual(messages[0]["content"], "Base")

    def test_summarize_prompt_is_source_grounded_and_neutral(self) -> None:
        messages = sift_farm_model.summarize_messages("article.txt", "Article body")

        system = messages[0]["content"]
        self.assertIn("Use only facts present in the file content", system)
        self.assertNotIn("worker farm", system.lower())
        self.assertNotIn("qwen", system.lower())

    def test_summarize_prompt_guides_snippet_selection(self) -> None:
        messages = sift_farm_model.summarize_messages(
            "article.txt",
            "Article body",
            snippet_request={"policy": "auto", "requested_count": 2, "max_chars": 600},
        )

        combined = "\n".join(message["content"] for message in messages)
        self.assertIn("SOURCE SNIPPETS", combined)
        self.assertIn("Choose passages that capture the thesis", combined)
        self.assertIn("Avoid titles, URLs, tags, front matter", combined)

    def test_prepare_summary_content_truncates_large_inputs_with_warning(self) -> None:
        content, warnings = sift_farm_model.prepare_summary_content("a" * 25, max_chars=10)

        self.assertTrue(content.startswith("aaaaaaaaaa"))
        self.assertIn("Input truncated", content)
        self.assertEqual(warnings, ["input_truncated"])

    def test_summarize_mode_does_not_inject_agent_guidance(self) -> None:
        client = FakeClient(
            '{"title":"T","abstract":"A","bullets":["B"],"open_questions":[],"confidence":"high"}'
        )

        result = sift_farm_model.process_file_with_model(
            client=client,  # type: ignore[arg-type]
            mode="summarize",
            file_path="article.txt",
            content="Article body",
            instructions=None,
            timeout=1,
            agent_system_prompt="You are a local Qwen assistant.",
        )

        self.assertIsInstance(result, FarmModelResult)
        messages = client.calls[0]["messages"]
        assert isinstance(messages, list)
        combined = "\n".join(message["content"] for message in messages)
        self.assertNotIn("Agent guidance", combined)
        self.assertNotIn("local Qwen assistant", combined)

    def test_summarize_mode_uses_fast_plain_text_call_shape(self) -> None:
        client = FakeClient(
            "\n".join(
                [
                    "TITLE: T",
                    "ABSTRACT: A",
                    "KEY POINTS:",
                    "- B",
                    "OPEN QUESTIONS:",
                    "- None",
                    "CONFIDENCE: high",
                ]
            )
        )

        result = sift_farm_model.process_file_with_model(
            client=client,  # type: ignore[arg-type]
            mode="summarize",
            file_path="article.txt",
            content="Article body",
            instructions=None,
            timeout=1,
        )

        self.assertTrue(result.structured_valid)
        self.assertEqual(client.calls[0]["response_format"], None)
        self.assertEqual(client.calls[0]["think"], False)

    def test_summarize_mode_verifies_requested_snippets(self) -> None:
        client = FakeClient(
            "\n".join(
                [
                    "TITLE: T",
                    "ABSTRACT: A",
                    "KEY POINTS:",
                    "- B",
                    "OPEN QUESTIONS:",
                    "- None",
                    "SOURCE SNIPPETS:",
                    "- TEXT: Exact source passage because it captures a useful claim.",
                    "  REASON: Useful.",
                    "- TEXT: Made up passage.",
                    "  REASON: Bad.",
                    "CONFIDENCE: high",
                ]
            )
        )

        result = sift_farm_model.process_file_with_model(
            client=client,  # type: ignore[arg-type]
            mode="summarize",
            file_path="article.txt",
            content="Intro.\nExact source passage because it captures a useful claim.\nOutro.",
            instructions=None,
            timeout=1,
            snippet_request={"policy": "fixed", "requested_count": 2, "max_chars": 100},
        )

        self.assertEqual(
            [item["text"] for item in result.payload["snippets"]],
            ["Exact source passage because it captures a useful claim."],
        )
        self.assertIsNotNone(result.snippet_selection)
        assert result.snippet_selection is not None
        self.assertEqual(result.snippet_selection["candidate_count"], 2)
        self.assertEqual(result.snippet_selection["verified_count"], 1)
        self.assertEqual(result.snippet_selection["selected_count"], 1)
        self.assertIn("compact_length", result.payload["snippets"][0]["score_reasons"])
        self.assertIn("claim", result.payload["snippets"][0]["score_reasons"])
        self.assertIn("snippet_candidates_unverified", result.warnings)
        self.assertIn("snippet_count_under_requested", result.warnings)
        self.assertIn("## Source Snippets", result.markdown)
