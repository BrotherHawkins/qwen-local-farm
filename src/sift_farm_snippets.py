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
SNIPPET_DROP_REASONS = ("unverified", "low_signal", "duplicate", "too_long")
SNIPPET_DIVERSITY_LINE_DISTANCE = 20
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
LOW_SIGNAL_SNIPPET_PHRASES = (
    "learn more",
    "read more",
    "see also",
    "see the changelog",
    "you can read more",
)

SIGNAL_GROUPS = {
    "claim": (
        "because",
        "therefore",
        "finding",
        "improves",
        "performs",
        "proves",
        "shows",
        "worse",
    ),
    "definition": (
        "combines",
        "defined",
        "definition",
        "is a",
        "is an",
        "means",
    ),
    "example": (
        "e.g.",
        "example",
        "for example",
        "instance",
        "such as",
    ),
    "limit": (
        "beyond",
        "caveat",
        "fails",
        "failure",
        "limit",
        "misleading",
        "past that",
        "risk",
        "tradeoff",
        "warning",
    ),
    "metric": (
        "%",
        "cost",
        "seconds",
        "tokens",
        "×",
    ),
    "operation": (
        "chunk",
        "ingest",
        "lint",
        "operation",
        "process",
        "query",
        "rank",
        "rerank",
        "step",
        "workflow",
    ),
    "rule": (
        "constraint",
        "must",
        "never",
        "only",
        "requires",
        "rule",
        "should",
    ),
    "thesis": (
        "central",
        "core",
        "fundamental",
        "main",
        "primary",
        "thesis",
    ),
}


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
    if any(phrase in lowered for phrase in LOW_SIGNAL_SNIPPET_PHRASES):
        return True
    if len(normalized) < 40 and not re.search(r"[.!?]$", normalized) and " - " in normalized:
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


def empty_snippet_diagnostics(
    *,
    policy: str = DEFAULT_SNIPPET_POLICY,
    requested_count: int = 0,
    max_chars: int = DEFAULT_SNIPPET_MAX_CHARS,
) -> dict[str, Any]:
    return {
        "policy": policy,
        "requested_count": requested_count,
        "candidate_count": 0,
        "verified_count": 0,
        "selected_count": 0,
        "max_chars": max_chars,
        "dropped": {reason: 0 for reason in SNIPPET_DROP_REASONS},
    }


def score_snippet(snippet: dict[str, Any]) -> dict[str, Any]:
    text = str(snippet.get("text", ""))
    reason = str(snippet.get("reason", ""))
    combined = f"{text}\n{reason}".lower()
    score = 0
    score_reasons: list[str] = []

    text_len = len(text)
    if 80 <= text_len <= 420:
        score += 2
        score_reasons.append("useful_length")
    elif 40 <= text_len < 80:
        score += 1
        score_reasons.append("compact_length")
    elif text_len > 520:
        score -= 1
        score_reasons.append("near_max_length")

    for group, terms in SIGNAL_GROUPS.items():
        if any(term in combined for term in terms):
            score += 2 if group in {"claim", "limit", "rule", "thesis"} else 1
            score_reasons.append(group)

    if re.search(r"\d", text):
        score += 1
        if "metric" not in score_reasons:
            score_reasons.append("metric")
    if text.strip().startswith(("**Rule:**", "Rule:", "NEVER ", "Never ")):
        score += 2
        if "rule" not in score_reasons:
            score_reasons.append("rule")
    if is_low_signal_snippet_text(text):
        score -= 10
        score_reasons.append("low_signal")

    return {"score": score, "score_reasons": score_reasons}


def with_snippet_score(snippet: dict[str, Any]) -> dict[str, Any]:
    scored = dict(snippet)
    scored.update(score_snippet(snippet))
    return scored


def source_line_distance(left: dict[str, Any], right: dict[str, Any]) -> int | None:
    if left.get("source_path") != right.get("source_path"):
        return None
    try:
        return abs(int(left.get("start_line", 0)) - int(right.get("start_line", 0)))
    except (TypeError, ValueError):
        return None


def select_ranked_snippets(
    snippets: list[dict[str, Any]],
    *,
    requested_count: int,
    diversity_line_distance: int = SNIPPET_DIVERSITY_LINE_DISTANCE,
) -> list[dict[str, Any]]:
    if requested_count <= 0:
        return []

    ranked = sorted(
        (with_snippet_score(snippet) for snippet in snippets),
        key=lambda item: (-int(item.get("score", 0)), int(item.get("char_start", 0))),
    )
    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    for snippet in ranked:
        if len(selected) >= requested_count:
            break
        clustered = any(
            (distance is not None and distance <= diversity_line_distance)
            for distance in (source_line_distance(snippet, existing) for existing in selected)
        )
        if clustered:
            deferred.append(snippet)
            continue
        selected.append(snippet)

    if len(selected) < requested_count:
        selected_texts = {str(snippet.get("text", "")) for snippet in selected}
        for snippet in [*deferred, *ranked]:
            if len(selected) >= requested_count:
                break
            text = str(snippet.get("text", ""))
            if text in selected_texts:
                continue
            selected.append(snippet)
            selected_texts.add(text)

    return selected


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


def select_snippet_candidates(
    candidates: list[dict[str, str]],
    *,
    source_text: str,
    source_path: str,
    requested_count: int,
    max_chars: int,
    policy: str = DEFAULT_SNIPPET_POLICY,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    diagnostics = empty_snippet_diagnostics(
        policy=policy,
        requested_count=requested_count,
        max_chars=max_chars,
    )
    diagnostics["candidate_count"] = len(candidates)
    verified: list[dict[str, Any]] = []
    seen: set[str] = set()
    dropped = diagnostics["dropped"]

    for candidate in candidates:
        text = candidate.get("text", "").strip().strip("\"'")
        if not text:
            dropped["unverified"] += 1
            continue
        if len(text) > max_chars:
            dropped["too_long"] += 1
            continue
        if is_low_signal_snippet_text(text):
            dropped["low_signal"] += 1
            continue
        if text in seen:
            dropped["duplicate"] += 1
            continue

        snippet = verify_snippet_candidate(
            candidate,
            source_text=source_text,
            source_path=source_path,
            max_chars=max_chars,
        )
        if snippet is None:
            dropped["unverified"] += 1
            continue
        seen.add(text)
        verified.append(snippet)

    diagnostics["verified_count"] = len(verified)
    selected = select_ranked_snippets(verified, requested_count=requested_count)
    diagnostics["selected_count"] = len(selected)

    warnings: list[str] = []
    if dropped["unverified"]:
        warnings.append("snippet_candidates_unverified")
    if requested_count > 0 and len(selected) < requested_count:
        warnings.append("snippet_count_under_requested")
    return selected, warnings, diagnostics


def verify_snippet_candidates(
    candidates: list[dict[str, str]],
    *,
    source_text: str,
    source_path: str,
    requested_count: int,
    max_chars: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    snippets, warnings, _diagnostics = select_snippet_candidates(
        candidates,
        source_text=source_text,
        source_path=source_path,
        requested_count=requested_count,
        max_chars=max_chars,
    )
    return snippets, warnings


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


def compact_snippet_status(
    request: dict[str, Any],
    verified_count: int = 0,
    *,
    selected_count: int | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if selected_count is None:
        selected_count = verified_count
    compact = {
        "policy": request.get("policy", DEFAULT_SNIPPET_POLICY),
        "requested_count": int(request.get("requested_count", 0)),
        "verified_count": verified_count,
        "selected_count": selected_count,
        "max_chars": int(request.get("max_chars", DEFAULT_SNIPPET_MAX_CHARS)),
    }
    if diagnostics:
        compact["candidate_count"] = int(diagnostics.get("candidate_count", 0))
        compact["dropped"] = diagnostics.get("dropped", {reason: 0 for reason in SNIPPET_DROP_REASONS})
    return compact


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


def reselect_snippets(
    snippets: list[dict[str, Any]],
    *,
    source_text: str,
    source_path: str,
    requested_count: int,
    max_chars: int,
    policy: str = DEFAULT_SNIPPET_POLICY,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    candidates = [
        {"text": str(snippet.get("text", "")), "reason": str(snippet.get("reason", ""))}
        for snippet in snippets
    ]
    return select_snippet_candidates(
        candidates,
        source_text=source_text,
        source_path=source_path,
        requested_count=requested_count,
        max_chars=max_chars,
        policy=policy,
    )
