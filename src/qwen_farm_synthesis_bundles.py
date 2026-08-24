from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.qwen_farm_snippet_packs import (
    DEFAULT_MAX_SNIPPETS,
    DEFAULT_PER_FILE_SNIPPETS,
    PACK_SOURCE,
    PACKABLE_JOB_STATUSES,
    apply_caps,
    dedupe_snippets,
    normalize_snippet,
    read_json_object,
    renumber_snippets,
    result_path_for,
    result_snippets,
    safe_label,
    skipped_job,
    source_description,
    utc_now,
    write_json,
)


SYNTHESIS_BUNDLE_SCHEMA_VERSION = 1


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def normalize_summary(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    abstract = str(payload.get("abstract") or "").strip()
    bullets = normalize_string_list(payload.get("bullets", []))
    open_questions = normalize_string_list(payload.get("open_questions", []))
    has_summary_text = bool(abstract or bullets or open_questions)
    if not has_summary_text:
        return None

    confidence = str(payload.get("confidence") or "medium").strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"

    return {
        "title": str(payload.get("title") or "Untitled").strip() or "Untitled",
        "abstract": abstract,
        "bullets": bullets,
        "open_questions": open_questions,
        "confidence": confidence,
    }


def build_item(job: dict[str, Any], result: dict[str, Any], index: int) -> dict[str, Any] | None:
    payload = result.get("result", {})
    summary = normalize_summary(payload)
    if summary is None:
        return None
    warnings = job.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
    return {
        "id": f"item-{index:04d}",
        "input_path": str(job.get("input_path", "")),
        "job_id": str(job.get("job_id", "")),
        "status": str(job.get("status", "")),
        "warnings": [str(item) for item in warnings],
        "summary": summary,
        "snippets": [],
    }


def collect_items_and_snippets(run_dir: Path, status: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
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

        item = build_item(job, result, len(items) + 1)
        if item is None:
            skipped_jobs.append(skipped_job(job, "empty_summary"))
            continue
        items.append(item)

        for snippet in result_snippets(result):
            normalized = normalize_snippet(job, snippet, len(candidates) + 1)
            if normalized is None:
                warnings.append(f"empty_snippet:{job.get('job_id', '')}")
                continue
            candidates.append(normalized)

    return items, candidates, {"skipped_jobs": skipped_jobs, "warnings": warnings}


def attach_snippets(items: list[dict[str, Any]], snippets: list[dict[str, Any]]) -> None:
    by_job = {
        (str(item.get("job_id", "")), str(item.get("input_path", ""))): item
        for item in items
    }
    for snippet in snippets:
        key = (str(snippet.get("job_id", "")), str(snippet.get("input_path", "")))
        item = by_job.get(key)
        if item is None:
            continue
        item.setdefault("snippets", []).append(snippet)


def build_synthesis_bundle(
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
    items, candidates, diagnostics = collect_items_and_snippets(run_dir, status)
    deduped, duplicates_dropped = dedupe_snippets(candidates)
    selected = renumber_snippets(apply_caps(deduped, max_snippets=max_snippets, per_file=per_file))
    attach_snippets(items, selected)

    return {
        "schema_version": SYNTHESIS_BUNDLE_SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "label": run_label,
        "run_id": status.get("run_id"),
        "run_path": str(run_dir),
        "mode": status.get("mode"),
        "model": status.get("model"),
        "limits": {
            "max_snippets": max_snippets,
            "per_file": per_file,
            "snippet_source": PACK_SOURCE,
        },
        "counts": {
            "jobs_seen": len([job for job in status.get("jobs", []) if isinstance(job, dict)]),
            "items": len(items),
            "items_with_snippets": len([item for item in items if item.get("snippets")]),
            "snippet_candidates": len(candidates),
            "snippets_selected": len(selected),
            "duplicates_dropped": duplicates_dropped,
            "jobs_skipped": len(diagnostics["skipped_jobs"]),
        },
        "items": items,
        "diagnostics": diagnostics,
    }


def render_list_section(lines: list[str], heading: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend(["", f"{heading}:"])
    lines.extend(f"- {item}" for item in items)


def render_synthesis_bundle_markdown(bundle: dict[str, Any]) -> str:
    counts = bundle.get("counts", {}) if isinstance(bundle.get("counts"), dict) else {}
    lines = [
        f"# Synthesis Bundle {bundle.get('label')}",
        "",
        f"Run: {bundle.get('run_id') or ''}",
        f"Model: {bundle.get('model') or ''}",
        f"Items: {counts.get('items', 0)}",
        f"Selected snippets: {counts.get('snippets_selected', 0)}",
        "",
    ]

    items = [item for item in bundle.get("items", []) if isinstance(item, dict)]
    if not items:
        lines.extend(["No summary items included.", ""])
    for item in items:
        input_path = str(item.get("input_path", ""))
        summary = item.get("summary", {}) if isinstance(item.get("summary"), dict) else {}
        lines.extend([f"## {Path(input_path).name}", ""])
        abstract = str(summary.get("abstract", "")).strip()
        if abstract:
            lines.extend([f"Summary: {abstract}"])
        render_list_section(lines, "Key points", normalize_string_list(summary.get("bullets", [])))
        render_list_section(lines, "Open questions", normalize_string_list(summary.get("open_questions", [])))

        snippets = [snippet for snippet in item.get("snippets", []) if isinstance(snippet, dict)]
        if snippets:
            lines.extend(["", "Evidence:"])
            for index, snippet in enumerate(snippets, start=1):
                text = str(snippet.get("text", "")).replace("\n", " ").strip()
                lines.append(f'{index}. "{text}"')
                source = source_description(snippet)
                if source:
                    lines.append(f"   Source: {source}")
                reason = str(snippet.get("reason", "")).strip()
                if reason:
                    lines.append(f"   Why it matters: {reason}")
        else:
            lines.extend(["", "Evidence: none selected."])

        confidence = str(summary.get("confidence", "")).strip()
        if confidence:
            lines.extend(["", f"Confidence: `{confidence}`"])
        lines.append("")

    diagnostics = bundle.get("diagnostics", {})
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


def write_synthesis_bundle(bundle: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    stem = safe_label(str(bundle.get("label") or bundle.get("run_id") or "synthesis-bundle"))
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    write_json(json_path, bundle)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_synthesis_bundle_markdown(bundle), encoding="utf-8")
    return json_path, markdown_path
