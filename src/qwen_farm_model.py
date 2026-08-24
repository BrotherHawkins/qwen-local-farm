from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from typing import Any

from src.qwen_farm_snippets import (
    apply_snippet_warning_policy,
    parse_snippet_candidates,
    verify_snippet_candidates,
)

SUMMARY_MAX_INPUT_CHARS = 8_000
SUMMARY_NUM_PREDICT = 384
SUMMARY_NUM_BATCH = 128


@dataclass(frozen=True)
class FarmModelResult:
    payload: dict[str, Any]
    markdown: str
    raw_response: str
    structured_valid: bool
    warnings: list[str]


class OllamaChatClient:
    def __init__(self, base_url: str, model: str, options: dict[str, Any] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.options = options or {}

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: str | None = None,
        timeout: int = 600,
        think: bool | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "5m",
            "options": self.options,
        }
        if response_format:
            payload["format"] = response_format
        if think is not None:
            payload["think"] = think

        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return str(data.get("message", {}).get("content", ""))


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        data = json.loads(text[start : end + 1])

    if not isinstance(data, dict):
        raise ValueError("Model JSON response must be an object.")
    return data


def normalize_summary_payload(data: dict[str, Any]) -> dict[str, Any]:
    bullets = data.get("bullets", [])
    if not isinstance(bullets, list):
        bullets = [str(bullets)]

    open_questions = data.get("open_questions", [])
    if not isinstance(open_questions, list):
        open_questions = [str(open_questions)]

    confidence = str(data.get("confidence", "medium")).lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"

    snippets = data.get("snippets", [])
    if not isinstance(snippets, list):
        snippets = []

    payload = {
        "title": str(data.get("title") or "Untitled"),
        "abstract": str(data.get("abstract") or ""),
        "bullets": [str(item) for item in bullets],
        "open_questions": [str(item) for item in open_questions],
        "confidence": confidence,
    }
    if snippets:
        payload["snippets"] = [
            item for item in snippets if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
    return payload


def strip_bullet_marker(line: str) -> str:
    return re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()


def compact_labeled_items(lines: list[str]) -> list[str]:
    items = [strip_bullet_marker(line) for line in lines if strip_bullet_marker(line)]
    return [item for item in items if item.lower() not in {"none", "n/a", "no open questions"}]


def parse_labeled_summary(raw: str) -> dict[str, Any]:
    text = raw.strip()
    labels = {
        "title": "title",
        "abstract": "abstract",
        "key points": "bullets",
        "key_points": "bullets",
        "bullets": "bullets",
        "open questions": "open_questions",
        "open_questions": "open_questions",
        "source snippets": "snippets",
        "source_snippets": "snippets",
        "snippets": "snippets",
        "confidence": "confidence",
    }
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z_ ]{3,30})\s*:\s*(.*)$", line)
        if match:
            label = match.group(1).strip().lower()
            mapped = labels.get(label)
            if mapped:
                current = mapped
                sections.setdefault(current, [])
                rest = match.group(2).strip()
                if rest:
                    sections[current].append(rest)
                continue
        if current is not None:
            sections.setdefault(current, []).append(line.rstrip())

    if not sections:
        raise ValueError("No labeled summary sections found.")

    bullets = compact_labeled_items(sections.get("bullets", []))
    open_questions = compact_labeled_items(sections.get("open_questions", []))
    confidence = " ".join(part.strip() for part in sections.get("confidence", []) if part.strip()).lower()
    confidence = confidence.split()[0] if confidence else "medium"

    return normalize_summary_payload(
        {
            "title": " ".join(part.strip() for part in sections.get("title", []) if part.strip()),
            "abstract": " ".join(part.strip() for part in sections.get("abstract", []) if part.strip()),
            "bullets": bullets,
            "open_questions": open_questions,
            "confidence": confidence,
            "snippets": parse_snippet_candidates(sections.get("snippets", [])),
        }
    )


def parse_summary_response(raw: str) -> tuple[dict[str, Any], bool]:
    try:
        return normalize_summary_payload(parse_json_object(raw)), True
    except Exception:
        pass

    try:
        return parse_labeled_summary(raw), True
    except Exception:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        bullets = [strip_bullet_marker(line) for line in lines if re.match(r"^\s*(?:[-*]|\d+[.)])\s+", line)]
        payload = normalize_summary_payload(
            {
                "title": "Untitled",
                "abstract": lines[0] if lines else "",
                "bullets": bullets,
                "open_questions": [],
                "confidence": "low",
            }
        )
        return payload, False


def render_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload.get('title', 'Summary')}",
        "",
        str(payload.get("abstract", "")),
        "",
        "## Key Points",
        "",
    ]
    bullets = payload.get("bullets") or []
    if bullets:
        lines.extend(f"- {item}" for item in bullets)
    else:
        lines.append("- No key points returned.")

    questions = payload.get("open_questions") or []
    if questions:
        lines.extend(["", "## Open Questions", ""])
        lines.extend(f"- {item}" for item in questions)

    snippets = payload.get("snippets") or []
    if snippets:
        lines.extend(["", "## Source Snippets", ""])
        for index, snippet in enumerate(snippets, start=1):
            text = str(snippet.get("text", ""))
            reason = str(snippet.get("reason", ""))
            source = str(snippet.get("source_path", ""))
            start_line = snippet.get("start_line")
            end_line = snippet.get("end_line")
            if start_line and end_line:
                source = f"{source}:{start_line}-{end_line}"
            lines.extend([f"{index}. \"{text}\""])
            if reason:
                lines.append(f"   Why it matters: {reason}")
            if source:
                lines.append(f"   Source: `{source}`")

    lines.extend(["", f"Confidence: `{payload.get('confidence', 'medium')}`", ""])
    return "\n".join(lines)


def prepare_summary_content(content: str, max_chars: int = SUMMARY_MAX_INPUT_CHARS) -> tuple[str, list[str]]:
    if len(content) <= max_chars:
        return content, []

    clipped = content[:max_chars].rstrip()
    clipped += f"\n\n[Input truncated by qwen-local-farm: summarized first {max_chars} of {len(content)} characters.]"
    return clipped, ["input_truncated"]


def snippet_instructions(snippet_request: dict[str, Any] | None) -> str:
    if not snippet_request or int(snippet_request.get("requested_count", 0)) <= 0:
        return ""
    count = int(snippet_request.get("requested_count", 0))
    max_chars = int(snippet_request.get("max_chars", 600))
    return (
        "SOURCE SNIPPETS:\n"
        f"- TEXT: <exact source passage, copied verbatim, {max_chars} chars or fewer>\n"
        "  REASON: <why this passage matters for later synthesis>\n\n"
        f"Return up to {count} source snippets. If no useful exact source snippet exists, return no snippets. "
        "Choose passages that capture the thesis, important claims, vivid examples, definitions, or caveats. "
        "Avoid titles, URLs, tags, front matter, navigation text, citation lists, and boilerplate unless that text "
        "is itself essential evidence. Do not paraphrase snippets.\n"
    )


def summarize_messages(
    file_path: str,
    content: str,
    instructions: str | None = None,
    snippet_request: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    extra = f"\nCaller instructions: {instructions.strip()}\n" if instructions else ""
    snippet_shape = snippet_instructions(snippet_request)
    return [
        {
            "role": "system",
            "content": (
                "Summarize the provided input file. Use only facts present in the file content. "
                "Do not include reasoning traces. Return compact labeled text only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Summarize this file.\nPath: {file_path}\n{extra}\n"
                "Use exactly this output shape:\n"
                "TITLE: <short title>\n"
                "ABSTRACT: <2-3 sentence summary>\n"
                "KEY POINTS:\n"
                "- <point>\n"
                "- <point>\n"
                "OPEN QUESTIONS:\n"
                "- <question, or None>\n"
                f"{snippet_shape}"
                "CONFIDENCE: low|medium|high\n\n"
                f"File content:\n{content}"
            ),
        },
    ]


def prompt_messages(file_path: str, content: str, instructions: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "You are a local offline worker. Apply the caller instructions to the provided file.",
        },
        {
            "role": "user",
            "content": f"Path: {file_path}\nInstructions: {instructions}\n\nFile content:\n{content}",
        },
    ]


def apply_agent_guidance(messages: list[dict[str, str]], agent_system_prompt: str | None) -> list[dict[str, str]]:
    guidance = (agent_system_prompt or "").strip()
    if not guidance:
        return messages

    updated = [dict(message) for message in messages]
    for message in updated:
        if message.get("role") == "system":
            message["content"] = f"{message.get('content', '')}\n\nAgent guidance:\n{guidance}"
            return updated

    updated.insert(0, {"role": "system", "content": guidance})
    return updated


def process_file_with_model(
    *,
    client: OllamaChatClient,
    mode: str,
    file_path: str,
    content: str,
    instructions: str | None,
    timeout: int,
    agent_system_prompt: str | None = None,
    summary_max_input_chars: int = SUMMARY_MAX_INPUT_CHARS,
    snippet_request: dict[str, Any] | None = None,
) -> FarmModelResult:
    if mode == "summarize":
        summary_content, warnings = prepare_summary_content(content, max_chars=summary_max_input_chars)
        raw = client.chat(
            summarize_messages(file_path, summary_content, instructions, snippet_request),
            timeout=timeout,
            think=False,
        )
        payload, structured_valid = parse_summary_response(raw)
        parse_warnings = [] if structured_valid else ["summary_text_parse_fallback"]
        if snippet_request and int(snippet_request.get("requested_count", 0)) > 0:
            candidates = payload.get("snippets") or []
            if not isinstance(candidates, list):
                candidates = []
            snippets, snippet_warnings = verify_snippet_candidates(
                candidates,
                source_text=summary_content,
                source_path=file_path,
                requested_count=int(snippet_request.get("requested_count", 0)),
                max_chars=int(snippet_request.get("max_chars", 600)),
            )
            payload["snippets"] = snippets
            snippet_warnings = apply_snippet_warning_policy(
                snippet_warnings,
                snippet_request=snippet_request,
                verified_count=len(snippets),
            )
            parse_warnings.extend(snippet_warnings)
        return FarmModelResult(
            payload=payload,
            markdown=render_summary_markdown(payload),
            raw_response=raw,
            structured_valid=structured_valid,
            warnings=[*warnings, *parse_warnings],
        )

    if mode == "prompt":
        if not instructions:
            raise ValueError("prompt mode requires instructions.")
        raw = client.chat(
            apply_agent_guidance(prompt_messages(file_path, content, instructions), agent_system_prompt),
            timeout=timeout,
        )
        return FarmModelResult(
            payload={"response": raw},
            markdown=raw,
            raw_response=raw,
            structured_valid=True,
            warnings=[],
        )

    raise ValueError(f"Unsupported farm mode: {mode}")
