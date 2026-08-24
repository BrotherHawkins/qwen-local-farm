from __future__ import annotations

import unittest

from src.qwen_farm_snippets import (
    apply_snippet_warning_policy,
    parse_snippet_candidates,
    resolve_snippet_request,
    verify_snippet_candidates,
)


class SnippetHelperTests(unittest.TestCase):
    def test_parse_snippet_candidates_from_labeled_lines(self) -> None:
        candidates = parse_snippet_candidates(
            [
                "- TEXT: Exact source passage.",
                "  REASON: Captures the thesis.",
                "- TEXT: Another passage.",
                "  REASON: Shows a limitation.",
            ]
        )

        self.assertEqual(
            candidates,
            [
                {"text": "Exact source passage.", "reason": "Captures the thesis."},
                {"text": "Another passage.", "reason": "Shows a limitation."},
            ],
        )

    def test_verify_snippet_candidates_requires_exact_source_text(self) -> None:
        source = "First line.\nExact source passage.\nFinal line."

        snippets, warnings = verify_snippet_candidates(
            [
                {"text": "Exact source passage.", "reason": "good"},
                {"text": "Invented passage.", "reason": "bad"},
            ],
            source_text=source,
            source_path="article.txt",
            requested_count=2,
            max_chars=100,
        )

        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["text"], "Exact source passage.")
        self.assertEqual(snippets[0]["source_path"], "article.txt")
        self.assertEqual(snippets[0]["start_line"], 2)
        self.assertEqual(snippets[0]["end_line"], 2)
        self.assertIn("snippet_candidates_unverified", warnings)
        self.assertIn("snippet_count_under_requested", warnings)

    def test_verify_snippet_candidates_discards_low_signal_scaffolding(self) -> None:
        source = "\n".join(
            [
                "tags: [guide, obsidian, claude-code, karpathy, pkm, llm-wiki]",
                'Forrest Chang, "andrej-karpathy-skills -- Surgical coding guardrails for LLM agents," GitHub, April 2026',
                "The tedious part of maintaining a knowledge base is not the reading or the thinking.",
            ]
        )

        snippets, warnings = verify_snippet_candidates(
            [
                {"text": "tags: [guide, obsidian, claude-code, karpathy, pkm, llm-wiki]", "reason": "Metadata."},
                {
                    "text": "Repovive, Official Obsidian Skills for Claude Code: https://example.com/skills",
                    "reason": "Citation.",
                },
                {
                    "text": 'Forrest Chang, "andrej-karpathy-skills -- Surgical coding guardrails for LLM agents," GitHub, April 2026',
                    "reason": "Citation.",
                },
                {
                    "text": "The tedious part of maintaining a knowledge base is not the reading or the thinking.",
                    "reason": "Thesis.",
                },
            ],
            source_text=source,
            source_path="article.txt",
            requested_count=1,
            max_chars=200,
        )

        self.assertEqual([item["text"] for item in snippets], [source.splitlines()[2]])
        self.assertEqual(warnings, [])

    def test_auto_warning_policy_allows_partial_success(self) -> None:
        warnings = apply_snippet_warning_policy(
            ["snippet_candidates_unverified", "snippet_count_under_requested"],
            snippet_request={"policy": "auto", "requested_count": 5},
            verified_count=3,
        )

        self.assertEqual(warnings, [])

    def test_fixed_warning_policy_keeps_under_count_warning(self) -> None:
        warnings = apply_snippet_warning_policy(
            ["snippet_count_under_requested"],
            snippet_request={"policy": "fixed", "requested_count": 5},
            verified_count=3,
        )

        self.assertEqual(warnings, ["snippet_count_under_requested"])

    def test_auto_snippet_count_prefers_tokens(self) -> None:
        request = resolve_snippet_request(
            {
                "snippet_policy": "auto",
                "snippet_count": None,
                "snippet_min_count": 2,
                "snippet_max_count": 8,
                "snippet_max_chars": 600,
            },
            source_chars=50000,
            source_tokens=9001,
            chunk_count=10,
        )

        self.assertEqual(request["requested_count"], 4)

    def test_auto_snippet_count_uses_character_fallback(self) -> None:
        request = resolve_snippet_request(
            {
                "snippet_policy": "auto",
                "snippet_count": None,
                "snippet_min_count": 2,
                "snippet_max_count": 8,
                "snippet_max_chars": 600,
            },
            source_chars=25000,
            source_tokens=None,
            chunk_count=1,
        )

        self.assertEqual(request["requested_count"], 3)


if __name__ == "__main__":
    unittest.main()
