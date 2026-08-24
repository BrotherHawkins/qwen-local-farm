from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol


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
    heading_ancestry: list[dict[str, Any]] = field(default_factory=list)
    overlap_text: str = ""
    overlap_before_chars: int = 0
    overlap_before_tokens: int | None = None
    overlap_source: str = "none"


@dataclass(frozen=True)
class HeadingMarker:
    level: int
    text: str
    line: int
    start: int


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


def markdown_heading_markers(content: str) -> list[HeadingMarker]:
    markers: list[HeadingMarker] = []
    in_fence = False
    fence_marker = ""
    position = 0

    for line_number, line in enumerate(content.splitlines(keepends=True), start=1):
        stripped = line.strip()
        fence = re.match(r"^(```+|~~~+)", stripped)
        if fence:
            marker = fence.group(1)[0]
            if in_fence and marker == fence_marker:
                in_fence = False
                fence_marker = ""
            elif not in_fence:
                in_fence = True
                fence_marker = marker
            position += len(line)
            continue

        if not in_fence:
            match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line.rstrip())
            if match:
                text = match.group(2).strip()
                if text:
                    markers.append(
                        HeadingMarker(
                            level=len(match.group(1)),
                            text=text,
                            line=line_number,
                            start=position,
                        )
                    )
        position += len(line)

    return markers


def heading_ancestry_at(markers: list[HeadingMarker], char_index: int) -> list[dict[str, Any]]:
    stack: list[HeadingMarker] = []
    for marker in markers:
        if marker.start > char_index:
            break
        stack = [item for item in stack if item.level < marker.level]
        stack.append(marker)
    return [{"level": item.level, "text": item.text, "line": item.line} for item in stack]


def locate_chunk_spans(content: str, chunks: list[TextChunk]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for chunk in chunks:
        if not chunk.text:
            spans.append((0, 0))
            continue
        start = content.find(chunk.text, cursor)
        if start < 0:
            start = content.find(chunk.text.strip(), cursor)
        if start < 0:
            start = cursor
        end = start + len(chunk.text)
        spans.append((start, end))
        cursor = end
    return spans


def suffix_under_token_budget(text: str, max_tokens: int, token_counter: TokenCounter) -> str:
    if max_tokens <= 0 or not text.strip():
        return ""
    stripped = text.rstrip()
    if token_counter.count_tokens(stripped) <= max_tokens:
        return stripped

    low = 0
    high = len(stripped)
    best = len(stripped)
    while low <= high:
        mid = (low + high) // 2
        candidate = stripped[mid:].lstrip()
        tokens = token_counter.count_tokens(candidate) if candidate else 0
        if tokens <= max_tokens:
            best = mid
            high = mid - 1
        else:
            low = mid + 1

    candidate = stripped[best:].lstrip()
    boundary = candidate.find(" ")
    if boundary > 0:
        trimmed = candidate[boundary + 1 :].lstrip()
        if trimmed and token_counter.count_tokens(trimmed) <= max_tokens:
            candidate = trimmed
    return candidate


def contextualize_chunks(
    content: str,
    chunks: list[TextChunk],
    *,
    preserve_heading_ancestry: bool = True,
    overlap_chars: int = 0,
    overlap_tokens: int = 0,
    token_counter: TokenCounter | None = None,
    max_input_tokens: int | None = None,
    source_path: str = "",
) -> list[TextChunk]:
    markers = markdown_heading_markers(content) if preserve_heading_ancestry else []
    spans = locate_chunk_spans(content, chunks)
    contextualized: list[TextChunk] = []

    for chunk, (start, _end) in zip(chunks, spans):
        heading_ancestry = heading_ancestry_at(markers, start) if preserve_heading_ancestry else []
        overlap_text = ""
        overlap_before_chars = 0
        overlap_before_tokens: int | None = None
        overlap_source = "none"

        if chunk.index > 1 and start > 0:
            before = content[:start].rstrip()
            if token_counter is not None and overlap_tokens > 0:
                base_chunk = TextChunk(
                    chunk_id=chunk.chunk_id,
                    index=chunk.index,
                    total=chunk.total,
                    text=chunk.text,
                    chars=chunk.chars,
                    tokens=chunk.tokens,
                    heading_ancestry=heading_ancestry,
                )
                if max_input_tokens is not None:
                    base_tokens = token_counter.count_tokens(render_chunk_input(source_path, base_chunk))
                    remaining_tokens = max(0, max_input_tokens - base_tokens)
                    allowed_overlap_tokens = min(overlap_tokens, remaining_tokens)
                else:
                    allowed_overlap_tokens = overlap_tokens
                overlap_text = suffix_under_token_budget(before, allowed_overlap_tokens, token_counter)
                overlap_before_tokens = token_counter.count_tokens(overlap_text) if overlap_text else 0
            elif overlap_chars > 0:
                overlap_text = before[-overlap_chars:].lstrip()

            if overlap_text:
                overlap_before_chars = len(overlap_text)
                overlap_source = "previous"

        contextualized.append(
            TextChunk(
                chunk_id=chunk.chunk_id,
                index=chunk.index,
                total=chunk.total,
                text=chunk.text,
                chars=chunk.chars,
                tokens=chunk.tokens,
                heading_ancestry=heading_ancestry,
                overlap_text=overlap_text,
                overlap_before_chars=overlap_before_chars,
                overlap_before_tokens=overlap_before_tokens,
                overlap_source=overlap_source,
            )
        )

    return contextualized


def chunk_text(
    content: str,
    max_chars: int = DEFAULT_CHUNK_TARGET_CHARS,
    *,
    preserve_heading_ancestry: bool = True,
    overlap_chars: int = 0,
) -> list[TextChunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive.")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be non-negative.")

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
    planned = [
        TextChunk(chunk_id=chunk_id_for(index), index=index, total=total, text=text, chars=len(text))
        for index, text in enumerate(chunks, start=1)
    ]
    return contextualize_chunks(
        content,
        planned,
        preserve_heading_ancestry=preserve_heading_ancestry,
        overlap_chars=overlap_chars,
    )


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
    preserve_heading_ancestry: bool = True,
    overlap_tokens: int = 0,
) -> list[TextChunk]:
    if max_input_tokens <= 0:
        raise ValueError("max_input_tokens must be positive.")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens must be non-negative.")

    body_budget = token_body_budget(source_path, max_input_tokens, token_counter)
    while body_budget >= 1:
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
        base_chunks = [
            TextChunk(chunk_id=chunk_id_for(index), index=index, total=total, text=text, chars=len(text))
            for index, text in enumerate(chunks, start=1)
        ]
        contextualized = contextualize_chunks(
            content,
            base_chunks,
            preserve_heading_ancestry=preserve_heading_ancestry,
            overlap_tokens=overlap_tokens,
            token_counter=token_counter,
            max_input_tokens=max_input_tokens,
            source_path=source_path,
        )

        planned: list[TextChunk] = []
        over_budget = False
        for chunk in contextualized:
            rendered_tokens = token_counter.count_tokens(render_chunk_input(source_path, chunk))
            if rendered_tokens > max_input_tokens:
                over_budget = True
                break
            planned.append(
                TextChunk(
                    chunk_id=chunk.chunk_id,
                    index=chunk.index,
                    total=chunk.total,
                    text=chunk.text,
                    chars=chunk.chars,
                    tokens=rendered_tokens,
                    heading_ancestry=chunk.heading_ancestry,
                    overlap_text=chunk.overlap_text,
                    overlap_before_chars=chunk.overlap_before_chars,
                    overlap_before_tokens=chunk.overlap_before_tokens,
                    overlap_source=chunk.overlap_source,
                )
            )
        if not over_budget:
            return planned
        body_budget -= 1

    raise ValueError(
        f"Could not plan token chunks under the configured budget of {max_input_tokens} tokens "
        "after adding heading context and overlap."
    )


def render_chunk_input(source_path: str, chunk: TextChunk) -> str:
    lines = [
        f"Source path: {source_path}",
        f"Chunk: {chunk.index} of {chunk.total}",
        f"Chunk ID: {chunk.chunk_id}",
    ]
    headings = [
        f"- {'#' * int(item.get('level', 1))} {str(item.get('text', '')).strip()}"
        for item in chunk.heading_ancestry
        if str(item.get("text", "")).strip()
    ]
    if headings:
        lines.extend(["", "Heading context:", *headings])
    if chunk.overlap_text:
        lines.extend(
            [
                "",
                "Overlap context from previous source text (for continuity; not primary chunk coverage):",
                chunk.overlap_text,
            ]
        )
    lines.extend(["", "Chunk text:", chunk.text])
    return "\n".join(lines)


def overlap_metadata(chunk: TextChunk) -> dict[str, Any]:
    return {
        "before_chars": chunk.overlap_before_chars,
        "before_tokens": chunk.overlap_before_tokens,
        "source": chunk.overlap_source,
    }


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
