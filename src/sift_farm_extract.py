from __future__ import annotations

import re
from typing import Any


EXTRACT_PRESETS = {"evidence", "entities", "work", "research"}
DEFAULT_EXTRACT_PRESET = "research"
DEFAULT_EXTRACT_CHUNK_CHARS = 6_000
DEFAULT_EXTRACT_MAX_ITEMS_PER_FILE = 40
DEFAULT_EXTRACT_MAX_ITEMS_PER_CHUNK = 10
DEFAULT_EXTRACT_SNIPPET_MAX_CHARS = 240
DEFAULT_EXTRACT_FOCUS_MAX_CHARS = 500

EVIDENCE_TYPES = {"claim", "fact", "example", "quote", "question", "tension"}
ENTITY_TYPES = {"entity", "link"}
WORK_TYPES = {"task", "decision", "risk", "requirement", "blocker", "follow_up"}
EXTRACT_ITEM_TYPES = EVIDENCE_TYPES | ENTITY_TYPES | WORK_TYPES
SNIPPET_EXPECTED_TYPES = {
    "claim",
    "fact",
    "example",
    "quote",
    "question",
    "tension",
    "decision",
    "risk",
    "requirement",
    "blocker",
}
SNIPPET_OPTIONAL_TYPES = {"task", "follow_up", "entity", "link"}


def validate_extract_preset(value: Any) -> str:
    preset = str(value or DEFAULT_EXTRACT_PRESET).strip().lower()
    if preset not in EXTRACT_PRESETS:
        allowed = ", ".join(sorted(EXTRACT_PRESETS))
        raise ValueError(f"extract.preset must be one of: {allowed}.")
    return preset


def validate_extract_focus(value: Any, *, field_path: str = "extract.focus") -> str | None:
    if value is None:
        return None
    focus = str(value).strip()
    if not focus:
        return None
    if len(focus) > DEFAULT_EXTRACT_FOCUS_MAX_CHARS:
        raise ValueError(f"{field_path} must be {DEFAULT_EXTRACT_FOCUS_MAX_CHARS} characters or fewer.")
    return focus


def allowed_types_for_preset(preset: str) -> set[str]:
    preset = validate_extract_preset(preset)
    if preset == "evidence":
        return set(EVIDENCE_TYPES)
    if preset == "entities":
        return set(ENTITY_TYPES)
    if preset == "work":
        return set(WORK_TYPES)
    return set(EVIDENCE_TYPES | ENTITY_TYPES)


def type_label(item_type: str) -> str:
    return item_type.upper().replace("_", "-")


def line_protocol_for_preset(preset: str) -> str:
    labels = [type_label(item_type) for item_type in sorted(allowed_types_for_preset(preset))]
    return "\n".join(f"{label} | <text> | <optional exact source snippet>" for label in labels)


def extract_messages(
    file_path: str,
    content: str,
    *,
    preset: str,
    focus: str | None = None,
    max_items: int = DEFAULT_EXTRACT_MAX_ITEMS_PER_CHUNK,
    snippet_max_chars: int = DEFAULT_EXTRACT_SNIPPET_MAX_CHARS,
) -> list[dict[str, str]]:
    focus_text = f"\nFocus: {focus.strip()}\n" if focus else ""
    allowed = ", ".join(sorted(allowed_types_for_preset(preset)))
    return [
        {
            "role": "system",
            "content": (
                "Extract compact source-grounded items from the provided file. "
                "Scan quickly. Use only facts present in the source. Do not include reasoning traces. "
                "Return compact tagged lines only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Path: {file_path}\nPreset: {preset}\nAllowed item types: {allowed}\n{focus_text}\n"
                f"Return at most {max_items} high-signal items. Zero items is OK when the source has none. "
                f"Use exact source snippets only when useful, {snippet_max_chars} chars or fewer.\n\n"
                "Tagged line shapes:\n"
                f"{line_protocol_for_preset(preset)}\n"
                "ENTITY | <entity_type> | <name> | <optional key=value; key=value attributes> | <optional exact snippet>\n"
                "LINK | <url> | <label/context> | <optional exact snippet>\n\n"
                f"File content:\n{content}"
            ),
        },
    ]


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().strip("\"'"))


def normalize_key(value: str) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_attributes(raw: str) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = normalize_key(key).replace("-", "_")[:40]
        value = normalize_text(value)[:160]
        if key and value:
            attributes[key] = value
        if len(attributes) >= 8:
            break
    return attributes


def source_reference(
    *,
    source_path: str,
    source_text: str,
    snippet: str,
    chunk_id: str | None = None,
    source_offset: int = 0,
    max_chars: int = DEFAULT_EXTRACT_SNIPPET_MAX_CHARS,
) -> dict[str, Any]:
    text = normalize_text(snippet)
    support = "chunk_only"
    char_start = None
    char_end = None
    if text and len(text) <= max_chars:
        local_start = source_text.find(text)
        if local_start >= 0:
            char_start = source_offset + local_start
            char_end = char_start + len(text)
            support = "snippet_verified"
    ref: dict[str, Any] = {
        "file": source_path,
        "chunk_id": chunk_id,
        "snippet": text if support == "snippet_verified" else None,
        "source_support": support,
        "char_start": char_start,
        "char_end": char_end,
    }
    return ref


def parse_tagged_extract(
    raw: str,
    *,
    preset: str,
    source_path: str,
    source_text: str,
    chunk_id: str | None = None,
    source_offset: int = 0,
    snippet_max_chars: int = DEFAULT_EXTRACT_SNIPPET_MAX_CHARS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed = allowed_types_for_preset(preset)
    items: list[dict[str, Any]] = []
    invalid_samples: list[str] = []
    invalid_count = 0
    unsupported_count = 0

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        label = parts[0].lower().replace("-", "_")
        if label not in EXTRACT_ITEM_TYPES:
            invalid_count += 1
            if len(invalid_samples) < 5:
                invalid_samples.append(line[:200])
            continue
        if label not in allowed:
            unsupported_count += 1
            continue

        item: dict[str, Any] | None = None
        if label == "entity":
            if len(parts) < 3:
                item = None
            else:
                entity_type = normalize_key(parts[1]).replace("-", "_") or "other"
                text = normalize_text(parts[2])
                attrs = parse_attributes(parts[3]) if len(parts) >= 4 else {}
                snippet = parts[4] if len(parts) >= 5 else ""
                item = {"type": "entity", "entity_type": entity_type, "text": text, "attributes": attrs}
        elif label == "link":
            if len(parts) < 3:
                item = None
            else:
                url = normalize_text(parts[1])
                text = normalize_text(parts[2]) or url
                snippet = parts[3] if len(parts) >= 4 else ""
                item = {"type": "link", "url": url, "text": text, "attributes": {}}
        else:
            if len(parts) < 2:
                item = None
            else:
                text = normalize_text(parts[1])
                snippet = parts[2] if len(parts) >= 3 else ""
                item = {"type": label, "text": text, "attributes": {}}

        if item is None or not normalize_text(item.get("text")):
            invalid_count += 1
            if len(invalid_samples) < 5:
                invalid_samples.append(line[:200])
            continue

        source = source_reference(
            source_path=source_path,
            source_text=source_text,
            snippet=snippet,
            chunk_id=chunk_id,
            source_offset=source_offset,
            max_chars=snippet_max_chars,
        )
        item["sources"] = [source]
        item["source_support"] = source["source_support"]
        item["dedupe_key"] = dedupe_key(item)
        item["rank_score"] = rank_score(item)
        items.append(item)

    diagnostics = {
        "candidate_count": len(items) + invalid_count + unsupported_count,
        "parsed_count": len(items),
        "invalid_line_count": invalid_count,
        "unsupported_type_count": unsupported_count,
        "invalid_line_samples": invalid_samples,
    }
    return items, diagnostics


def dedupe_key(item: dict[str, Any]) -> str:
    item_type = str(item.get("type") or "")
    if item_type == "link" and item.get("url"):
        return f"link:{normalize_key(str(item.get('url')))}"
    if item_type == "entity":
        return f"entity:{normalize_key(str(item.get('entity_type') or 'other'))}:{normalize_key(str(item.get('text') or ''))}"
    return f"{item_type}:{normalize_key(str(item.get('text') or ''))}"


def rank_score(item: dict[str, Any]) -> float:
    item_type = str(item.get("type") or "")
    score = 0.4
    if item_type in {"claim", "example", "decision", "risk", "requirement", "blocker"}:
        score += 0.2
    if item.get("source_support") == "snippet_verified":
        score += 0.25
    text = str(item.get("text") or "")
    if 20 <= len(text) <= 220:
        score += 0.1
    if item_type in {"quote", "link"}:
        score += 0.05
    return round(min(score, 1.0), 3)


def merge_sources(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any, Any, Any]] = set()
    merged: list[dict[str, Any]] = []
    for source in [*existing, *incoming]:
        key = (
            source.get("file"),
            source.get("chunk_id"),
            source.get("char_start"),
            source.get("snippet"),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(source)
    return merged[:6]


def dedupe_items(items: list[dict[str, Any]], *, max_items: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for item in items:
        key = str(item.get("dedupe_key") or dedupe_key(item))
        if key not in by_key:
            by_key[key] = dict(item)
            by_key[key]["sources"] = list(item.get("sources") or [])
            continue
        duplicate_count += 1
        current = by_key[key]
        current["sources"] = merge_sources(list(current.get("sources") or []), list(item.get("sources") or []))
        if item.get("source_support") == "snippet_verified" and current.get("source_support") != "snippet_verified":
            current.update({field: item.get(field) for field in ["text", "source_support", "rank_score"]})

    ranked = sorted(
        by_key.values(),
        key=lambda item: (-float(item.get("rank_score") or 0), str(item.get("type") or ""), str(item.get("text") or "")),
    )
    selected = ranked[:max_items]
    for index, item in enumerate(selected, start=1):
        item_type = str(item.get("type") or "item")
        item["id"] = f"{item_type}-{index:03d}"
        item.pop("dedupe_key", None)
    diagnostics = {
        "candidate_items": len(items),
        "deduped_items": len(ranked),
        "selected_items": len(selected),
        "duplicate_count": duplicate_count,
        "dropped_by_cap": max(0, len(ranked) - len(selected)),
    }
    return selected, diagnostics


def count_by_type(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {item_type: 0 for item_type in sorted(EXTRACT_ITEM_TYPES)}
    for item in items:
        item_type = str(item.get("type") or "")
        if item_type in counts:
            counts[item_type] += 1
    return {key: value for key, value in counts.items() if value}


def extract_payload(
    *,
    preset: str,
    focus: str | None,
    source_files: list[str],
    items: list[dict[str, Any]],
    limits: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "preset": validate_extract_preset(preset),
        "focus": focus,
        "items": items,
        "counts": {
            "items": len(items),
            "by_type": count_by_type(items),
        },
        "limits": limits,
        "diagnostics": diagnostics,
        "source_files": source_files,
    }


def render_extract_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Extract Results",
        "",
        f"Preset: `{payload.get('preset', '')}`",
        f"Items: `{(payload.get('counts') or {}).get('items', 0)}`",
    ]
    if payload.get("focus"):
        lines.append(f"Focus: {payload.get('focus')}")
    lines.extend(["", "## Items", ""])
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    if not items:
        lines.extend(["No extract items found.", ""])
        return "\n".join(lines)
    for item in items:
        label = str(item.get("type") or "item")
        text = str(item.get("text") or "")
        lines.append(f"- `{label}` {text}")
        if item.get("entity_type"):
            lines.append(f"  - Entity type: `{item.get('entity_type')}`")
        if item.get("url"):
            lines.append(f"  - URL: {item.get('url')}")
        sources = [source for source in item.get("sources", []) if isinstance(source, dict)]
        if sources:
            source = sources[0]
            location = source.get("file") or ""
            if source.get("char_start") is not None and source.get("char_end") is not None:
                location = f"{location}@{source.get('char_start')}-{source.get('char_end')}"
            lines.append(f"  - Source: `{location}`")
            if source.get("snippet"):
                lines.append(f"  - Snippet: \"{source.get('snippet')}\"")
    lines.append("")
    return "\n".join(lines)


def warning_codes_from_diagnostics(diagnostics: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if int(diagnostics.get("invalid_line_count", 0)):
        warnings.append("extract_invalid_tagged_lines")
    if int(diagnostics.get("unsupported_type_count", 0)):
        warnings.append("extract_unsupported_item_types")
    return warnings
