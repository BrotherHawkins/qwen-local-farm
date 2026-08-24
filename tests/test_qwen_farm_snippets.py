from __future__ import annotations

import unittest

from src.qwen_farm_snippets import (
    apply_snippet_warning_policy,
    parse_snippet_candidates,
    resolve_snippet_request,
    score_snippet,
    select_snippet_candidates,
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

    def test_select_snippet_candidates_ranks_high_signal_before_source_order(self) -> None:
        source = "\n".join(
            [
                "This short intro is fine but not especially useful.",
                "A common mistake is querying the wiki too early because the model has high-confidence gaps.",
            ]
        )

        snippets, warnings, diagnostics = select_snippet_candidates(
            [
                {"text": source.splitlines()[0], "reason": "Background."},
                {"text": source.splitlines()[1], "reason": "Captures a caveat and risk."},
            ],
            source_text=source,
            source_path="article.txt",
            requested_count=1,
            max_chars=200,
            policy="fixed",
        )

        self.assertEqual([item["text"] for item in snippets], [source.splitlines()[1]])
        self.assertIn("limit", snippets[0]["score_reasons"])
        self.assertEqual(warnings, [])
        self.assertEqual(diagnostics["candidate_count"], 2)
        self.assertEqual(diagnostics["verified_count"], 2)
        self.assertEqual(diagnostics["selected_count"], 1)

    def test_select_snippet_candidates_reports_drop_reasons(self) -> None:
        source = "\n".join(
            [
                "tags: [guide]",
                "QMD - Query Markup Documents",
                "Exact duplicate claim because this is useful.",
                "Exact duplicate claim because this is useful.",
            ]
        )

        snippets, warnings, diagnostics = select_snippet_candidates(
            [
                {"text": "tags: [guide]", "reason": "Metadata."},
                {"text": "QMD - Query Markup Documents", "reason": "Title."},
                {"text": "x" * 50, "reason": "Invented."},
                {"text": "y" * 150, "reason": "Too long."},
                {"text": "Exact duplicate claim because this is useful.", "reason": "Claim."},
                {"text": "Exact duplicate claim because this is useful.", "reason": "Duplicate."},
            ],
            source_text=source,
            source_path="article.txt",
            requested_count=1,
            max_chars=100,
            policy="fixed",
        )

        self.assertEqual(len(snippets), 1)
        self.assertEqual(diagnostics["dropped"]["low_signal"], 2)
        self.assertEqual(diagnostics["dropped"]["unverified"], 1)
        self.assertEqual(diagnostics["dropped"]["too_long"], 1)
        self.assertEqual(diagnostics["dropped"]["duplicate"], 1)
        self.assertIn("snippet_candidates_unverified", warnings)

    def test_select_snippet_candidates_prefers_source_diversity(self) -> None:
        source = "\n".join(
            [
                "Rule: this first nearby claim must be preserved because it is useful.",
                "Rule: this second nearby claim must be preserved because it is useful.",
                *["filler"] * 24,
                "Beyond that point, the system fails unless search tools help with navigation.",
            ]
        )

        snippets, _warnings, _diagnostics = select_snippet_candidates(
            [
                {"text": source.splitlines()[0], "reason": "Rule."},
                {"text": source.splitlines()[1], "reason": "Rule."},
                {"text": source.splitlines()[-1], "reason": "Limit."},
            ],
            source_text=source,
            source_path="article.txt",
            requested_count=2,
            max_chars=200,
            policy="fixed",
        )

        self.assertEqual(snippets[0]["text"], source.splitlines()[0])
        self.assertEqual(snippets[1]["text"], source.splitlines()[-1])

    def test_score_snippet_records_stable_score_reasons(self) -> None:
        scored = score_snippet(
            {
                "text": "A wiki with 90% coverage can be actively misleading because it has high-confidence gaps.",
                "reason": "Captures a caveat.",
            }
        )

        self.assertGreater(scored["score"], 0)
        self.assertIn("limit", scored["score_reasons"])
        self.assertIn("metric", scored["score_reasons"])

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
