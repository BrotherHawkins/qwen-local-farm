from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COLLECTION_SCHEMA_VERSION = 1
COLLECTABLE_JOB_STATUSES = {"complete", "complete_with_warnings"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_label(value: str, fallback: str = "farm-collection") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    cleaned = cleaned.strip(".-")
    return cleaned or fallback


def safe_item_stem(*, item_id: str, input_path: str) -> str:
    name = Path(input_path).stem or Path(input_path).name or item_id
    slug = safe_label(name, fallback="item").lower()
    return f"{item_id}-{slug[:80]}"


def result_path_for(run_dir: Path, job: dict[str, Any], key: str) -> Path | None:
    raw = job.get(key)
    if not raw:
        return None
    path = Path(str(raw))
    if path.is_absolute():
        return path
    return run_dir / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def skipped_job(job: dict[str, Any], reason: str, detail: str | None = None) -> dict[str, Any]:
    item = {
        "job_id": str(job.get("job_id", "")),
        "input_path": str(job.get("input_path", "")),
        "reason": reason,
    }
    if detail:
        item["detail"] = detail
    return item


def compact_summary(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("result")
    if not isinstance(payload, dict):
        return {}

    summary: dict[str, Any] = {}
    for key in ["title", "abstract", "confidence"]:
        value = payload.get(key)
        if value is not None and str(value).strip():
            summary[key] = str(value).strip()
    return summary


def normalize_warnings(job: dict[str, Any], result: dict[str, Any] | None = None) -> list[str]:
    warnings: list[str] = []
    for source in [job.get("warnings"), (result or {}).get("warnings")]:
        if isinstance(source, list):
            warnings.extend(str(item) for item in source if str(item).strip())
    return warnings


def copy_artifact(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build_collection(
    *,
    run_dir: Path,
    output_dir: Path,
    label: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    status = read_json_object(run_dir / "farm-status.json")
    run_label = label or str(status.get("run_id") or run_dir.name)
    collection_dir = output_dir / safe_label(run_label)
    items_dir = collection_dir / "items"
    jobs = [job for job in status.get("jobs", []) if isinstance(job, dict)]
    items: list[dict[str, Any]] = []
    skipped_jobs: list[dict[str, Any]] = []
    warnings: list[str] = []
    markdown_count = 0
    json_count = 0

    for job in jobs:
        status_value = str(job.get("status", ""))
        if status_value not in COLLECTABLE_JOB_STATUSES:
            skipped_jobs.append(skipped_job(job, "job_not_collectable", status_value))
            continue

        result_md_path = result_path_for(run_dir, job, "result_md")
        result_json_path = result_path_for(run_dir, job, "result_json")
        available_md = result_md_path is not None and result_md_path.is_file()
        available_json = result_json_path is not None and result_json_path.is_file()
        if not available_md and not available_json:
            skipped_jobs.append(skipped_job(job, "missing_result_artifacts"))
            continue

        result: dict[str, Any] | None = None
        malformed_json: str | None = None
        if available_json and result_json_path is not None:
            try:
                result = read_json_object(result_json_path)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                malformed_json = str(exc)
                warnings.append(f"malformed_result_json:{job.get('job_id', '')}")

        item_id = f"item-{len(items) + 1:04d}"
        stem = safe_item_stem(item_id=item_id, input_path=str(job.get("input_path", "")))
        source_artifacts: dict[str, str] = {}
        collected_artifacts: dict[str, str] = {}

        if available_md and result_md_path is not None:
            destination = items_dir / f"{stem}.md"
            copy_artifact(result_md_path, destination)
            source_artifacts["result_md"] = display_path(run_dir, result_md_path)
            collected_artifacts["result_md"] = display_path(collection_dir, destination)
            markdown_count += 1

        if available_json and result_json_path is not None:
            destination = items_dir / f"{stem}.json"
            copy_artifact(result_json_path, destination)
            source_artifacts["result_json"] = display_path(run_dir, result_json_path)
            collected_artifacts["result_json"] = display_path(collection_dir, destination)
            json_count += 1

        item: dict[str, Any] = {
            "id": item_id,
            "job_id": str(job.get("job_id", "")),
            "input_path": str(job.get("input_path", "")),
            "status": status_value,
            "warnings": normalize_warnings(job, result),
            "source_artifacts": source_artifacts,
            "collected_artifacts": collected_artifacts,
        }
        if result is not None:
            summary = compact_summary(result)
            if summary:
                item["summary"] = summary
        if malformed_json:
            item.setdefault("diagnostics", {})["malformed_result_json"] = malformed_json
        items.append(item)

    manifest = {
        "schema_version": COLLECTION_SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "label": run_label,
        "run_id": status.get("run_id"),
        "run_path": str(run_dir),
        "mode": status.get("mode"),
        "agent": status.get("agent"),
        "model": status.get("model"),
        "counts": {
            "jobs_seen": len(jobs),
            "items_collected": len(items),
            "markdown_files": markdown_count,
            "json_files": json_count,
            "jobs_skipped": len(skipped_jobs),
        },
        "artifacts": {
            "markdown_index": "FARM_COLLECTION.md",
            "manifest": "farm-collection.json",
            "items_dir": "items",
        },
        "items": items,
        "diagnostics": {
            "skipped_jobs": skipped_jobs,
            "warnings": warnings,
        },
    }
    return manifest


def render_collection_markdown(collection: dict[str, Any]) -> str:
    counts = collection.get("counts", {}) if isinstance(collection.get("counts"), dict) else {}
    lines = [
        f"# Farm Collection {collection.get('label')}",
        "",
        f"Run: {collection.get('run_id') or ''}",
        f"Mode: {collection.get('mode') or ''}",
        f"Model: {collection.get('model') or ''}",
        f"Items collected: {counts.get('items_collected', 0)}",
        "",
        "## Items",
        "",
        "| Item | Job | Input | Status | Markdown | JSON |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    items = [item for item in collection.get("items", []) if isinstance(item, dict)]
    if not items:
        lines.append("| _none_ |  |  |  |  |  |")
    for item in items:
        artifacts = item.get("collected_artifacts", {}) if isinstance(item.get("collected_artifacts"), dict) else {}
        lines.append(
            f"| `{item.get('id', '')}` | `{item.get('job_id', '')}` | `{item.get('input_path', '')}` | "
            f"`{item.get('status', '')}` | `{artifacts.get('result_md', '')}` | `{artifacts.get('result_json', '')}` |"
        )

    lines.extend(["", "## Summaries", ""])
    if not items:
        lines.extend(["No items collected.", ""])
    for item in items:
        input_path = str(item.get("input_path", ""))
        summary = item.get("summary", {}) if isinstance(item.get("summary"), dict) else {}
        lines.extend([f"### {item.get('id')} - {Path(input_path).name}", ""])
        title = str(summary.get("title", "")).strip()
        confidence = str(summary.get("confidence", "")).strip()
        abstract = str(summary.get("abstract", "")).strip()
        if title:
            lines.append(f"Title: {title}")
        if confidence:
            lines.append(f"Confidence: {confidence}")
        if title or confidence:
            lines.append("")
        if abstract:
            lines.extend([abstract, ""])
        elif not summary:
            lines.extend(["No compact summary metadata available.", ""])

    diagnostics = collection.get("diagnostics", {}) if isinstance(collection.get("diagnostics"), dict) else {}
    skipped_jobs = diagnostics.get("skipped_jobs", []) if isinstance(diagnostics.get("skipped_jobs"), list) else []
    warnings = diagnostics.get("warnings", []) if isinstance(diagnostics.get("warnings"), list) else []
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


def write_collection(collection: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    collection_dir = output_dir / safe_label(str(collection.get("label") or collection.get("run_id") or "farm-collection"))
    json_path = collection_dir / "farm-collection.json"
    markdown_path = collection_dir / "FARM_COLLECTION.md"
    write_json(json_path, collection)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_collection_markdown(collection), encoding="utf-8")
    return json_path, markdown_path
