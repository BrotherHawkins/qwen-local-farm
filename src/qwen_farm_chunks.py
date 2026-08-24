from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


DEFAULT_CHUNK_TARGET_CHARS = 7_000
CHUNK_STRATEGY = "paragraph-character"
TOKEN_CHUNK_STRATEGY = "paragraph-token"


class TokenCounter(Protocol):
    def count_tokens(self, text: str) -> int:
        ...


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    index: int
    total: int
    text: str
    chars: int = 0
    tokens: int | None = None


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
        TextChunk(chunk_id=chunk_id_for(index), index=index, total=total, text=text, chars=len(text))
        for index, text in enumerate(chunks, start=1)
    ]


def choose_token_safe_cut(text: str, max_tokens: int, token_counter: TokenCounter) -> int:
    low = 1
    high = len(text)
    best = 1
    while low <= high:
        mid = (low + high) // 2
        candidate = text[:mid]
        if token_counter.count_tokens(candidate) <= max_tokens:
            best = mid
            low = mid + 1
        else:
            high = mid - 1

    minimum_boundary = max(1, best // 2)
    for pattern in ["\n\n", "\n", ". ", " "]:
        boundary = text.rfind(pattern, 0, best)
        if boundary >= minimum_boundary:
            cut = boundary + len(pattern)
            if token_counter.count_tokens(text[:cut]) <= max_tokens:
                return cut
    return best


def split_oversized_text_by_tokens(text: str, max_tokens: int, token_counter: TokenCounter) -> list[str]:
    parts: list[str] = []
    remaining = text.strip()
    while remaining:
        if token_counter.count_tokens(remaining) <= max_tokens:
            parts.append(remaining)
            break
        cut = choose_token_safe_cut(remaining, max_tokens, token_counter)
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].strip()
    return [part for part in parts if part]


def paragraph_token_units(content: str, max_tokens: int, token_counter: TokenCounter) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs and content.strip():
        paragraphs = [content.strip()]

    units: list[str] = []
    for paragraph in paragraphs:
        if token_counter.count_tokens(paragraph) <= max_tokens:
            units.append(paragraph)
            continue
        units.extend(split_oversized_text_by_tokens(paragraph, max_tokens, token_counter))
    return units


def token_body_budget(source_path: str, max_input_tokens: int, token_counter: TokenCounter) -> int:
    sample = TextChunk(chunk_id="chunk-9999", index=9999, total=9999, text="")
    overhead = token_counter.count_tokens(render_chunk_input(source_path, sample))
    return max(1, max_input_tokens - overhead)


def chunk_text_by_tokens(
    content: str,
    *,
    max_input_tokens: int,
    token_counter: TokenCounter,
    source_path: str,
) -> list[TextChunk]:
    if max_input_tokens <= 0:
        raise ValueError("max_input_tokens must be positive.")

    body_budget = token_body_budget(source_path, max_input_tokens, token_counter)
    units = paragraph_token_units(content, body_budget, token_counter)
    chunks: list[str] = []
    current = ""

    for unit in units:
        candidate = unit if not current else f"{current}\n\n{unit}"
        if token_counter.count_tokens(candidate) <= body_budget:
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
    planned = []
    for index, text in enumerate(chunks, start=1):
        chunk = TextChunk(
            chunk_id=chunk_id_for(index),
            index=index,
            total=total,
            text=text,
            chars=len(text),
        )
        rendered_tokens = token_counter.count_tokens(render_chunk_input(source_path, chunk))
        if rendered_tokens > max_input_tokens:
            raise ValueError(
                f"Planned chunk {chunk.chunk_id} has {rendered_tokens} tokens, "
                f"over the configured budget of {max_input_tokens}."
            )
        planned.append(
            TextChunk(
                chunk_id=chunk.chunk_id,
                index=chunk.index,
                total=chunk.total,
                text=chunk.text,
                chars=chunk.chars,
                tokens=rendered_tokens,
            )
        )
    return planned


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
