from __future__ import annotations

import json
import re
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SNIPPET_PACK_SCHEMA_VERSION = 1
DEFAULT_MAX_SNIPPETS = 24
DEFAULT_PER_FILE_SNIPPETS = 4
PACK_SOURCE = "selected"
PACKABLE_JOB_STATUSES = {"complete", "complete_with_warnings"}


def read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_label(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value.strip())
    cleaned = cleaned.strip(".-")
    return cleaned or "snippet-pack"


def to_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_duplicate_key(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    return normalized.strip(string.punctuation + " \t\r\n")


def result_path_for(run_dir: Path, job: dict[str, Any]) -> Path | None:
    result_json = job.get("result_json")
    if not result_json:
        return None
    path = Path(str(result_json))
    if path.is_absolute():
        return path
    return run_dir / path


def skipped_job(job: dict[str, Any], reason: str, detail: str | None = None) -> dict[str, Any]:
    item = {
        "job_id": str(job.get("job_id", "")),
        "input_path": str(job.get("input_path", "")),
        "reason": reason,
    }
    if detail:
        item["detail"] = detail
    return item


def result_snippets(result: dict[str, Any]) -> list[dict[str, Any]]:
    payload = result.get("result", {})
    if not isinstance(payload, dict):
        return []
    snippets = payload.get("snippets", [])
    if not isinstance(snippets, list):
        return []
    return [snippet for snippet in snippets if isinstance(snippet, dict)]


def source_field(snippet: dict[str, Any], canonical: str, fallback: str) -> int | None:
    return to_int(snippet.get(canonical, snippet.get(fallback)))


def normalize_snippet(job: dict[str, Any], snippet: dict[str, Any], index: int) -> dict[str, Any] | None:
    text = str(snippet.get("text", "")).strip()
    if not text:
        return None

    record: dict[str, Any] = {
        "id": f"candidate-{index:04d}",
        "input_path": str(job.get("input_path", "")),
        "job_id": str(job.get("job_id", "")),
        "text": text,
        "reason": str(snippet.get("reason", "")).strip(),
    }

    score = to_int(snippet.get("score"))
    if score is not None:
        record["score"] = score
    score_reasons = snippet.get("score_reasons", [])
    if isinstance(score_reasons, list):
        record["score_reasons"] = [str(item) for item in score_reasons if str(item).strip()]

    for field in ["start_line", "end_line"]:
        value = to_int(snippet.get(field))
        if value is not None:
            record[field] = value

    start_char = source_field(snippet, "start_char", "char_start")
    end_char = source_field(snippet, "end_char", "char_end")
    if start_char is not None:
        record["start_char"] = start_char
    if end_char is not None:
        record["end_char"] = end_char

    source_path = str(snippet.get("source_path", "")).strip()
    if source_path and source_path != record["input_path"]:
        record["source_path"] = source_path

    return record


def snippet_sort_key(snippet: dict[str, Any]) -> tuple[Any, ...]:
    score = to_int(snippet.get("score")) or 0
    start_line = to_int(snippet.get("start_line"))
    start_char = to_int(snippet.get("start_char"))
    return (
        -score,
        str(snippet.get("input_path", "")),
        str(snippet.get("job_id", "")),
        start_line if start_line is not None else 10**9,
        start_char if start_char is not None else 10**12,
        str(snippet.get("text", "")),
    )


def dedupe_snippets(snippets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for snippet in sorted(snippets, key=snippet_sort_key):
        key = normalize_duplicate_key(str(snippet.get("text", "")))
        if not key:
            continue
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        selected.append(snippet)
    return selected, duplicate_count


def apply_caps(snippets: list[dict[str, Any]], *, max_snippets: int, per_file: int) -> list[dict[str, Any]]:
    if max_snippets <= 0 or per_file <= 0:
        return []

    by_file: dict[str, list[dict[str, Any]]] = {}
    for snippet in sorted(snippets, key=snippet_sort_key):
        input_path = str(snippet.get("input_path", ""))
        by_file.setdefault(input_path, [])
        if len(by_file[input_path]) < per_file:
            by_file[input_path].append(snippet)

    selected: list[dict[str, Any]] = []
    file_order = sorted(by_file, key=lambda path: snippet_sort_key(by_file[path][0]))
    index = 0
    while len(selected) < max_snippets:
        added = False
        for input_path in file_order:
            items = by_file[input_path]
            if index >= len(items):
                continue
            selected.append(items[index])
            added = True
            if len(selected) >= max_snippets:
                break
        if not added:
            break
        index += 1

    return selected


def collect_snippets(run_dir: Path, status: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    skipped_jobs: list[dict[str, Any]] = []
    warnings: list[str] = []
    jobs = [job for job in status.get("jobs", []) if isinstance(job, dict)]

    for job in jobs:
        status_value = str(job.get("status", ""))
        if status_value not in PACKABLE_JOB_STATUSES:
            skipped_jobs.append(skipped_job(job, "job_not_complete", status_value))
            continue

        result_path = result_path_for(run_dir, job)
        if result_path is None:
            skipped_jobs.append(skipped_job(job, "missing_result_json"))
            continue
        if not result_path.exists():
            skipped_jobs.append(skipped_job(job, "missing_result_file", str(result_path)))
            continue

        try:
            result = read_json_object(result_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            skipped_jobs.append(skipped_job(job, "malformed_result_json", str(exc)))
            continue

        snippets = result_snippets(result)
        if not snippets:
            skipped_jobs.append(skipped_job(job, "no_selected_snippets"))
            continue

        for snippet in snippets:
            normalized = normalize_snippet(job, snippet, len(candidates) + 1)
            if normalized is None:
                warnings.append(f"empty_snippet:{job.get('job_id', '')}")
                continue
            candidates.append(normalized)

    return candidates, {"skipped_jobs": skipped_jobs, "warnings": warnings}


def renumber_snippets(snippets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, snippet in enumerate(snippets, start=1):
        item = dict(snippet)
        item["id"] = f"snippet-{index:04d}"
        output.append(item)
    return output


def build_snippet_pack(
    *,
    run_dir: Path,
    label: str | None = None,
    max_snippets: int = DEFAULT_MAX_SNIPPETS,
    per_file: int = DEFAULT_PER_FILE_SNIPPETS,
    created_at: str | None = None,
) -> dict[str, Any]:
    if max_snippets < 0:
        raise ValueError("--max-snippets must be a non-negative integer.")
    if per_file < 0:
        raise ValueError("--per-file must be a non-negative integer.")

    status = read_json_object(run_dir / "farm-status.json")
    run_label = label or str(status.get("run_id") or run_dir.name)
    candidates, diagnostics = collect_snippets(run_dir, status)
    deduped, duplicates_dropped = dedupe_snippets(candidates)
    selected = renumber_snippets(apply_caps(deduped, max_snippets=max_snippets, per_file=per_file))
    input_paths = {str(snippet.get("input_path", "")) for snippet in candidates}

    return {
        "schema_version": SNIPPET_PACK_SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "label": run_label,
        "run_id": status.get("run_id"),
        "run_path": str(run_dir),
        "mode": status.get("mode"),
        "model": status.get("model"),
        "limits": {
            "max_snippets": max_snippets,
            "per_file": per_file,
            "source": PACK_SOURCE,
        },
        "counts": {
            "jobs_seen": len([job for job in status.get("jobs", []) if isinstance(job, dict)]),
            "jobs_with_snippets": len(input_paths),
            "candidates": len(candidates),
            "selected": len(selected),
            "duplicates_dropped": duplicates_dropped,
            "jobs_skipped": len(diagnostics["skipped_jobs"]),
        },
        "snippets": selected,
        "diagnostics": diagnostics,
    }


def source_description(snippet: dict[str, Any]) -> str:
    parts = [str(snippet.get("job_id", "")).strip()]
    start_line = snippet.get("start_line")
    end_line = snippet.get("end_line")
    if start_line and end_line:
        if start_line == end_line:
            parts.append(f"line {start_line}")
        else:
            parts.append(f"lines {start_line}-{end_line}")
    elif snippet.get("start_char") is not None and snippet.get("end_char") is not None:
        parts.append(f"chars {snippet.get('start_char')}-{snippet.get('end_char')}")
    return ", ".join(part for part in parts if part)


def render_snippet_pack_markdown(pack: dict[str, Any]) -> str:
    lines = [
        f"# Snippet Pack {pack.get('label')}",
        "",
        f"Run: {pack.get('run_id') or ''}",
        f"Model: {pack.get('model') or ''}",
        f"Selected snippets: {(pack.get('counts') or {}).get('selected', 0)}",
        "",
    ]

    snippets = [snippet for snippet in pack.get("snippets", []) if isinstance(snippet, dict)]
    if not snippets:
        lines.extend(["No snippets selected.", ""])
    else:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for snippet in snippets:
            grouped.setdefault(str(snippet.get("input_path", "")), []).append(snippet)

        for input_path in sorted(grouped):
            lines.extend([f"## {Path(input_path).name}", ""])
            for index, snippet in enumerate(grouped[input_path], start=1):
                text = str(snippet.get("text", "")).replace("\n", " ").strip()
                lines.append(f'{index}. "{text}"')
                source = source_description(snippet)
                if source:
                    lines.append(f"   Source: {source}")
                reason = str(snippet.get("reason", "")).strip()
                if reason:
                    lines.append(f"   Why it matters: {reason}")
                lines.append("")

    diagnostics = pack.get("diagnostics", {})
    skipped_jobs = diagnostics.get("skipped_jobs", []) if isinstance(diagnostics, dict) else []
    warnings = diagnostics.get("warnings", []) if isinstance(diagnostics, dict) else []
    if skipped_jobs or warnings:
        lines.extend(["## Diagnostics", ""])
        for job in skipped_jobs:
            if not isinstance(job, dict):
                continue
            label = job.get("input_path") or job.get("job_id") or "unknown job"
            lines.append(f"- Skipped `{label}`: {job.get('reason', 'unknown')}")
        for warning in warnings:
            lines.append(f"- Warning: {warning}")
        lines.append("")

    return "\n".join(lines)


def write_snippet_pack(pack: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    stem = safe_label(str(pack.get("label") or pack.get("run_id") or "snippet-pack"))
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    write_json(json_path, pack)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_snippet_pack_markdown(pack), encoding="utf-8")
    return json_path, markdown_path
