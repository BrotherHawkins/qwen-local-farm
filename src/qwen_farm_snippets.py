from __future__ import annotations

import math
import re
from typing import Any


SNIPPET_POLICIES = {"off", "fixed", "auto"}
DEFAULT_SNIPPET_POLICY = "off"
DEFAULT_SNIPPET_MIN_COUNT = 2
DEFAULT_SNIPPET_MAX_COUNT = 8
DEFAULT_SNIPPET_MAX_CHARS = 600
DEFAULT_CHUNK_CANDIDATE_SNIPPETS = 2
LOW_SIGNAL_SNIPPET_PREFIXES = (
    "author:",
    "by:",
    "conversion:",
    "date:",
    "downloaded:",
    "source:",
    "source url:",
    "tags:",
    "title:",
)


def default_snippet_settings() -> dict[str, Any]:
    return {
        "snippet_policy": DEFAULT_SNIPPET_POLICY,
        "snippet_count": None,
        "snippet_min_count": DEFAULT_SNIPPET_MIN_COUNT,
        "snippet_max_count": DEFAULT_SNIPPET_MAX_COUNT,
        "snippet_max_chars": DEFAULT_SNIPPET_MAX_CHARS,
    }


def normalize_snippet_candidate(candidate: Any) -> dict[str, str] | None:
    if isinstance(candidate, dict):
        text = str(candidate.get("text") or "").strip()
        reason = str(candidate.get("reason") or "").strip()
    else:
        text = str(candidate or "").strip()
        reason = ""

    text = text.strip("\"'")
    if not text or text.lower() in {"none", "n/a"}:
        return None
    return {"text": text, "reason": reason}


def parse_snippet_candidates(lines: list[str]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    def finish_current() -> None:
        nonlocal current
        normalized = normalize_snippet_candidate(current)
        if normalized is not None:
            candidates.append(normalized)
        current = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        upper = line.upper()
        if upper.startswith("TEXT:"):
            finish_current()
            current = {"text": line.split(":", 1)[1].strip(), "reason": ""}
            continue
        if upper.startswith("REASON:"):
            if current is None:
                current = {"text": "", "reason": ""}
            current["reason"] = line.split(":", 1)[1].strip()
            continue
        if current is None:
            current = {"text": line, "reason": ""}
        elif not current.get("reason"):
            current["text"] = f"{current.get('text', '')} {line}".strip()

    finish_current()
    return candidates


def line_range_for_span(source_text: str, start: int, end: int) -> tuple[int, int]:
    start_line = source_text.count("\n", 0, start) + 1
    end_line = source_text.count("\n", 0, end) + 1
    return start_line, end_line


def is_low_signal_snippet_text(text: str) -> bool:
    normalized = text.strip()
    lowered = normalized.lower()
    if lowered.startswith(LOW_SIGNAL_SNIPPET_PREFIXES):
        return True
    if re.search(r"https?://", normalized, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"https?://\S+", normalized):
        return True
    if re.match(r"^\d+[.)]\s+.+https?://", normalized, flags=re.IGNORECASE | re.DOTALL):
        return True
    if re.match(r"^[^,\n]{2,80},\s+[\"“]", normalized) and re.search(r"\d{4}$", normalized):
        return True
    return False


def verify_snippet_candidate(
    candidate: dict[str, str],
    *,
    source_text: str,
    source_path: str,
    max_chars: int,
) -> dict[str, Any] | None:
    text = candidate.get("text", "").strip()
    text = text.strip("\"'")
    if not text or len(text) > max_chars or is_low_signal_snippet_text(text):
        return None

    char_start = source_text.find(text)
    if char_start < 0:
        return None

    char_end = char_start + len(text)
    start_line, end_line = line_range_for_span(source_text, char_start, char_end)
    return {
        "text": text,
        "reason": candidate.get("reason", "").strip(),
        "source_path": source_path,
        "start_line": start_line,
        "end_line": end_line,
        "char_start": char_start,
        "char_end": char_end,
    }


def verify_snippet_candidates(
    candidates: list[dict[str, str]],
    *,
    source_text: str,
    source_path: str,
    requested_count: int,
    max_chars: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    verified: list[dict[str, Any]] = []
    seen: set[str] = set()
    dropped = 0

    for candidate in candidates:
        text = candidate.get("text", "").strip().strip("\"'")
        if is_low_signal_snippet_text(text):
            continue
        snippet = verify_snippet_candidate(
            candidate,
            source_text=source_text,
            source_path=source_path,
            max_chars=max_chars,
        )
        if snippet is None:
            dropped += 1
            continue
        if snippet["text"] in seen:
            continue
        seen.add(snippet["text"])
        verified.append(snippet)
        if len(verified) >= requested_count:
            break

    if dropped:
        warnings.append("snippet_candidates_unverified")
    if requested_count > 0 and len(verified) < requested_count:
        warnings.append("snippet_count_under_requested")
    return verified, warnings


def clamp(value: int, minimum: int, maximum: int) -> int:
    return min(max(value, minimum), maximum)


def resolve_snippet_request(
    summarize: dict[str, Any],
    *,
    source_chars: int,
    source_tokens: int | None = None,
    chunk_count: int | None = None,
    candidate_count: int | None = None,
) -> dict[str, Any]:
    policy = str(summarize.get("snippet_policy", DEFAULT_SNIPPET_POLICY)).lower()
    count = summarize.get("snippet_count")
    min_count = int(summarize.get("snippet_min_count", DEFAULT_SNIPPET_MIN_COUNT))
    max_count = int(summarize.get("snippet_max_count", DEFAULT_SNIPPET_MAX_COUNT))
    max_chars = int(summarize.get("snippet_max_chars", DEFAULT_SNIPPET_MAX_CHARS))

    if policy == "off":
        requested = 0
    elif policy == "fixed":
        requested = int(count)
    elif candidate_count is not None:
        requested = candidate_count
    elif source_tokens is not None:
        requested = math.ceil(source_tokens / 3000)
    elif chunk_count is not None and chunk_count > 1:
        requested = chunk_count + 1
    else:
        requested = math.ceil(source_chars / 12000)
    if policy == "auto":
        requested = clamp(requested, min_count, max_count)

    return {
        "policy": policy,
        "requested_count": requested,
        "max_chars": max_chars,
        "min_count": min_count,
        "max_count": max_count,
    }


def compact_snippet_status(request: dict[str, Any], verified_count: int = 0) -> dict[str, Any]:
    return {
        "policy": request.get("policy", DEFAULT_SNIPPET_POLICY),
        "requested_count": int(request.get("requested_count", 0)),
        "verified_count": verified_count,
        "max_chars": int(request.get("max_chars", DEFAULT_SNIPPET_MAX_CHARS)),
    }


def apply_snippet_warning_policy(
    warnings: list[str],
    *,
    snippet_request: dict[str, Any],
    verified_count: int,
) -> list[str]:
    if snippet_request.get("policy") == "auto" and verified_count > 0:
        return [warning for warning in warnings if not warning.startswith("snippet_")]
    return warnings


def reverify_snippets(
    snippets: list[dict[str, Any]],
    *,
    source_text: str,
    source_path: str,
    requested_count: int,
    max_chars: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates = [
        {"text": str(snippet.get("text", "")), "reason": str(snippet.get("reason", ""))}
        for snippet in snippets
    ]
    return verify_snippet_candidates(
        candidates,
        source_text=source_text,
        source_path=source_path,
        requested_count=requested_count,
        max_chars=max_chars,
    )
