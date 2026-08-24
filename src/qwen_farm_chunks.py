from __future__ import annotations

import re
from dataclasses import dataclass


DEFAULT_CHUNK_TARGET_CHARS = 7_000
CHUNK_STRATEGY = "paragraph-character"


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    index: int
    total: int
    text: str


def chunk_id_for(index: int) -> str:
    return f"chunk-{index:04d}"


def split_oversized_text(text: str, max_chars: int) -> list[str]:
    parts = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + max_chars])
        start += max_chars
    return parts


def paragraph_units(content: str, max_chars: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs and content.strip():
        paragraphs = [content.strip()]

    units: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue
        units.extend(split_oversized_text(paragraph, max_chars))
    return units


def chunk_text(content: str, max_chars: int = DEFAULT_CHUNK_TARGET_CHARS) -> list[TextChunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive.")

    units = paragraph_units(content, max_chars)
    chunks: list[str] = []
    current = ""

    for unit in units:
        candidate = unit if not current else f"{current}\n\n{unit}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = unit

    if current:
        chunks.append(current)

    if not chunks:
        chunks = [""]

    total = len(chunks)
    return [
        TextChunk(chunk_id=chunk_id_for(index), index=index, total=total, text=text)
        for index, text in enumerate(chunks, start=1)
    ]


def render_chunk_input(source_path: str, chunk: TextChunk) -> str:
    return (
        f"Source path: {source_path}\n"
        f"Chunk: {chunk.index} of {chunk.total}\n"
        f"Chunk ID: {chunk.chunk_id}\n\n"
        f"{chunk.text}"
    )


def render_reduce_input(source_path: str, chunk_payloads: list[dict[str, object]]) -> str:
    lines = [
        f"Source path: {source_path}",
        f"Chunk summaries: {len(chunk_payloads)}",
        "",
        "Synthesize these chunk summaries into one file-level summary.",
        "Use only facts present in the chunk summaries.",
        "",
    ]

    for index, payload in enumerate(chunk_payloads, start=1):
        lines.extend(
            [
                f"## Chunk {index}",
                "",
                f"Title: {payload.get('title', 'Untitled')}",
                f"Abstract: {payload.get('abstract', '')}",
                "",
                "Key points:",
            ]
        )
        bullets = payload.get("bullets") or []
        if isinstance(bullets, list):
            lines.extend(f"- {item}" for item in bullets)
        questions = payload.get("open_questions") or []
        if isinstance(questions, list) and questions:
            lines.extend(["", "Open questions:"])
            lines.extend(f"- {item}" for item in questions)
        lines.append("")

    return "\n".join(lines)
