from __future__ import annotations

import unittest

from src import qwen_farm_chunks


class FakeTokenCounter:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


class ChunkPlanningTests(unittest.TestCase):
    def test_heading_ancestry_ignores_fenced_code_headings(self) -> None:
        content = "\n".join(
            [
                "# Title",
                "",
                "```",
                "# Not A Heading",
                "```",
                "",
                "## Real Section",
                "Body",
            ]
        )

        markers = qwen_farm_chunks.markdown_heading_markers(content)

        self.assertEqual([(marker.level, marker.text, marker.line) for marker in markers], [(1, "Title", 1), (2, "Real Section", 7)])

    def test_chunk_text_preserves_heading_ancestry(self) -> None:
        content = "\n\n".join(
            [
                "# Title",
                "Intro.",
                "## Section A",
                "A " * 20,
                "### Detail",
                "B " * 20,
            ]
        )

        chunks = qwen_farm_chunks.chunk_text(content, max_chars=45)

        self.assertGreater(len(chunks), 1)
        detail_chunk = next(chunk for chunk in chunks if "B " in chunk.text)
        self.assertEqual(
            [(item["level"], item["text"]) for item in detail_chunk.heading_ancestry],
            [(1, "Title"), (2, "Section A"), (3, "Detail")],
        )
        rendered = qwen_farm_chunks.render_chunk_input("article.md", detail_chunk)
        self.assertIn("Heading context:", rendered)
        self.assertIn("- # Title", rendered)
        self.assertIn("- ### Detail", rendered)
        self.assertIn("Chunk text:", rendered)

    def test_chunk_text_adds_character_overlap_metadata(self) -> None:
        content = "\n\n".join(["alpha " * 10, "beta " * 10, "gamma " * 10])

        chunks = qwen_farm_chunks.chunk_text(content, max_chars=70, overlap_chars=12)

        self.assertEqual(chunks[0].overlap_source, "none")
        self.assertEqual(chunks[1].overlap_source, "previous")
        self.assertLessEqual(chunks[1].overlap_before_chars, 12)
        self.assertIn(chunks[1].overlap_text, qwen_farm_chunks.render_chunk_input("source.txt", chunks[1]))

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

    def test_chunk_text_by_tokens_groups_under_rendered_budget(self) -> None:
        counter = FakeTokenCounter()
        content = "\n\n".join(["alpha " * 5, "beta " * 5, "gamma " * 5])

        chunks = qwen_farm_chunks.chunk_text_by_tokens(
            content,
            max_input_tokens=18,
            token_counter=counter,
            source_path="source.txt",
        )

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            rendered = qwen_farm_chunks.render_chunk_input("source.txt", chunk)
            self.assertLessEqual(counter.count_tokens(rendered), 18)
            self.assertEqual(chunk.tokens, counter.count_tokens(rendered))
            self.assertEqual(chunk.chars, len(chunk.text))

    def test_chunk_text_by_tokens_adds_overlap_within_rendered_budget(self) -> None:
        counter = FakeTokenCounter()
        content = "\n\n".join(["alpha " * 8, "beta " * 8, "gamma " * 8])

        chunks = qwen_farm_chunks.chunk_text_by_tokens(
            content,
            max_input_tokens=32,
            token_counter=counter,
            source_path="source.txt",
            overlap_tokens=4,
        )

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[1].overlap_source, "previous")
        self.assertLessEqual(chunks[1].overlap_before_tokens or 0, 4)
        for chunk in chunks:
            rendered = qwen_farm_chunks.render_chunk_input("source.txt", chunk)
            self.assertLessEqual(counter.count_tokens(rendered), 32)

    def test_chunk_text_by_tokens_splits_oversized_paragraph(self) -> None:
        counter = FakeTokenCounter()

        chunks = qwen_farm_chunks.chunk_text_by_tokens(
            " ".join(f"word{index}" for index in range(30)),
            max_input_tokens=20,
            token_counter=counter,
            source_path="source.txt",
        )

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(
                counter.count_tokens(qwen_farm_chunks.render_chunk_input("source.txt", chunk)),
                20,
            )

    def test_token_chunking_can_use_fewer_chunks_than_character_chunking(self) -> None:
        counter = FakeTokenCounter()
        content = "\n\n".join(["longword" * 80 for _ in range(6)])

        char_chunks = qwen_farm_chunks.chunk_text(content, max_chars=100)
        token_chunks = qwen_farm_chunks.chunk_text_by_tokens(
            content,
            max_input_tokens=20,
            token_counter=counter,
            source_path="source.txt",
        )

        self.assertLess(len(token_chunks), len(char_chunks))
