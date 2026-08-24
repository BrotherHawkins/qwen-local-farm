from __future__ import annotations

import unittest

from src import qwen_farm_chunks


class ChunkPlanningTests(unittest.TestCase):
    def test_chunk_text_groups_paragraphs_under_budget(self) -> None:
        content = "\n\n".join(["a" * 30, "b" * 30, "c" * 30])

        chunks = qwen_farm_chunks.chunk_text(content, max_chars=70)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].chunk_id, "chunk-0001")
        self.assertEqual(chunks[0].index, 1)
        self.assertEqual(chunks[0].total, 2)
        self.assertLessEqual(len(chunks[0].text), 70)
        self.assertLessEqual(len(chunks[1].text), 70)

    def test_chunk_text_hard_splits_oversized_paragraph(self) -> None:
        chunks = qwen_farm_chunks.chunk_text("x" * 25, max_chars=10)

        self.assertEqual([chunk.text for chunk in chunks], ["x" * 10, "x" * 10, "x" * 5])

    def test_render_reduce_input_includes_chunk_summaries(self) -> None:
        text = qwen_farm_chunks.render_reduce_input(
            "source.md",
            [
                {
                    "title": "One",
                    "abstract": "First chunk",
                    "bullets": ["A"],
                    "open_questions": ["Q"],
                }
            ],
        )

        self.assertIn("Source path: source.md", text)
        self.assertIn("Chunk summaries: 1", text)
        self.assertIn("Title: One", text)
        self.assertIn("- A", text)
        self.assertIn("- Q", text)
