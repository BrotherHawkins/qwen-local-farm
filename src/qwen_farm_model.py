from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

    def chat(self, messages: list[dict[str, str]], *, response_format: str | None = None, timeout: int = 600) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": self.options,
        }
        if response_format:
            payload["format"] = response_format

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

    return {
        "title": str(data.get("title") or "Untitled"),
        "abstract": str(data.get("abstract") or ""),
        "bullets": [str(item) for item in bullets],
        "open_questions": [str(item) for item in open_questions],
        "confidence": confidence,
    }


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

    lines.extend(["", f"Confidence: `{payload.get('confidence', 'medium')}`", ""])
    return "\n".join(lines)


def summarize_messages(file_path: str, content: str, instructions: str | None = None) -> list[dict[str, str]]:
    extra = f"\nCaller instructions: {instructions.strip()}\n" if instructions else ""
    return [
        {
            "role": "system",
            "content": (
                "You summarize files for a local worker farm. "
                "Return only valid JSON with keys: title, abstract, bullets, open_questions, confidence. "
                "confidence must be low, medium, or high."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Summarize this file.\nPath: {file_path}\n{extra}\n"
                "Return compact, useful JSON only.\n\n"
                f"File content:\n{content}"
            ),
        },
    ]


def repair_messages(raw_response: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Repair model output into valid JSON only. Do not add prose.",
        },
        {
            "role": "user",
            "content": (
                "Return one valid JSON object with keys: title, abstract, bullets, open_questions, confidence.\n\n"
                f"Broken output:\n{raw_response}"
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
) -> FarmModelResult:
    if mode == "summarize":
        raw = client.chat(
            apply_agent_guidance(summarize_messages(file_path, content, instructions), agent_system_prompt),
            response_format="json",
            timeout=timeout,
        )
        try:
            payload = normalize_summary_payload(parse_json_object(raw))
            return FarmModelResult(
                payload=payload,
                markdown=render_summary_markdown(payload),
                raw_response=raw,
                structured_valid=True,
                warnings=[],
            )
        except Exception:
            repair_raw = client.chat(repair_messages(raw), response_format="json", timeout=timeout)
            try:
                payload = normalize_summary_payload(parse_json_object(repair_raw))
                return FarmModelResult(
                    payload=payload,
                    markdown=render_summary_markdown(payload),
                    raw_response=f"{raw}\n\n--- repair response ---\n\n{repair_raw}",
                    structured_valid=True,
                    warnings=["summary_json_repaired"],
                )
            except Exception:
                payload = {
                    "title": Path(file_path).name,
                    "abstract": "",
                    "bullets": [],
                    "open_questions": ["Model did not return valid summary JSON."],
                    "confidence": "low",
                }
                return FarmModelResult(
                    payload=payload,
                    markdown=raw,
                    raw_response=f"{raw}\n\n--- failed repair response ---\n\n{repair_raw}",
                    structured_valid=False,
                    warnings=["summary_json_invalid"],
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
