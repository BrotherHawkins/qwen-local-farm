from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DOGFOOD_HISTORY_SCHEMA_VERSION = 1
QUALITY_FIELDS = (
    "summary_accuracy",
    "summary_usefulness",
    "snippet_usefulness",
    "diagnostic_clarity",
    "overall",
)
DROP_REASONS = ("unverified", "low_signal", "duplicate", "too_long")


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


def current_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def safe_label(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value.strip())
    cleaned = cleaned.strip(".-")
    return cleaned or "dogfood-run"


def normalize_quality(data: Any) -> dict[str, int]:
    if not isinstance(data, dict):
        return {}
    quality: dict[str, int] = {}
    for field in QUALITY_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if isinstance(value, bool):
            continue
        try:
            score = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= score <= 5:
            quality[field] = score
    return quality


def normalize_notes(data: Any) -> list[str]:
    if isinstance(data, str):
        text = data.strip()
        return [text] if text else []
    if not isinstance(data, list):
        return []
    notes: list[str] = []
    for item in data:
        text = str(item).strip()
        if text:
            notes.append(text)
    return notes


def load_quality_notes(notes_path: Path | None) -> dict[str, Any]:
    if notes_path is None:
        return {"quality": {}, "notes": [], "jobs": {}}
    data = read_json_object(notes_path)
    jobs = data.get("jobs", {})
    if not isinstance(jobs, dict):
        jobs = {}
    return {
        "quality": normalize_quality(data.get("quality", {})),
        "notes": normalize_notes(data.get("notes", [])),
        "jobs": jobs,
    }


def job_notes_for(notes: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    jobs = notes.get("jobs", {})
    if not isinstance(jobs, dict):
        return {"quality": {}, "notes": []}
    candidates = [
        str(job.get("input_path", "")),
        str(job.get("job_id", "")),
        Path(str(job.get("input_path", ""))).name,
    ]
    for key in candidates:
        if key and isinstance(jobs.get(key), dict):
            item = jobs[key]
            return {
                "quality": normalize_quality(item.get("quality", {})),
                "notes": normalize_notes(item.get("notes", [])),
            }
    return {"quality": {}, "notes": []}


def count_job_warnings(job: dict[str, Any]) -> int:
    warnings = job.get("warnings", [])
    return len(warnings) if isinstance(warnings, list) else 0


def compact_dropped(snippets: dict[str, Any]) -> dict[str, int]:
    dropped = snippets.get("dropped", {})
    if not isinstance(dropped, dict):
        dropped = {}
    return {reason: int(dropped.get(reason, 0) or 0) for reason in DROP_REASONS}


def compact_snippets(snippets: Any) -> dict[str, Any]:
    if not isinstance(snippets, dict):
        snippets = {}
    return {
        "requested_count": int(snippets.get("requested_count", 0) or 0),
        "verified_count": int(snippets.get("verified_count", 0) or 0),
        "selected_count": int(snippets.get("selected_count", snippets.get("verified_count", 0)) or 0),
        "candidate_count": int(snippets.get("candidate_count", 0) or 0),
        "dropped": compact_dropped(snippets),
    }


def job_chunk_count(job: dict[str, Any]) -> int:
    chunking = job.get("chunking", {})
    if not isinstance(chunking, dict):
        return 0
    if chunking.get("enabled"):
        return int(chunking.get("chunk_count", 0) or 0)
    return 1


def build_job_record(job: dict[str, Any], notes: dict[str, Any]) -> dict[str, Any]:
    timing = job.get("timing", {})
    if not isinstance(timing, dict):
        timing = {}
    warnings = job.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
    job_notes = job_notes_for(notes, job)
    return {
        "job_id": str(job.get("job_id", "")),
        "input_path": str(job.get("input_path", "")),
        "status": str(job.get("status", "")),
        "duration_ms": timing.get("duration_ms"),
        "chunk_count": job_chunk_count(job),
        "warnings": [str(item) for item in warnings],
        "warning_count": len(warnings),
        "snippets": compact_snippets(job.get("snippets", {})),
        "quality": job_notes["quality"],
        "notes": job_notes["notes"],
    }


def sum_drop_counts(jobs: list[dict[str, Any]]) -> dict[str, int]:
    totals = {reason: 0 for reason in DROP_REASONS}
    for job in jobs:
        dropped = ((job.get("snippets") or {}).get("dropped") or {})
        if not isinstance(dropped, dict):
            continue
        for reason in DROP_REASONS:
            totals[reason] += int(dropped.get(reason, 0) or 0)
    return totals


def sum_snippet_count(jobs: list[dict[str, Any]], key: str) -> int:
    total = 0
    for job in jobs:
        snippets = job.get("snippets") or {}
        if isinstance(snippets, dict):
            total += int(snippets.get(key, 0) or 0)
    return total


def compact_runtime(status: dict[str, Any]) -> dict[str, Any]:
    runtime = status.get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    summarize = runtime.get("summarize", {})
    if not isinstance(summarize, dict):
        summarize = {}
    return {
        "profile": runtime.get("profile"),
        "resource_mode": runtime.get("resource_mode"),
        "model": runtime.get("model", status.get("model")),
        "summarize": {
            "chunk_strategy": summarize.get("chunk_strategy"),
            "chunk_chars": summarize.get("chunk_chars"),
            "reduce_chars": summarize.get("reduce_chars"),
            "chunk_tokens": summarize.get("chunk_tokens"),
            "reduce_tokens": summarize.get("reduce_tokens"),
            "preserve_heading_ancestry": summarize.get("preserve_heading_ancestry"),
            "chunk_overlap_chars": summarize.get("chunk_overlap_chars"),
            "chunk_overlap_tokens": summarize.get("chunk_overlap_tokens"),
            "snippet_policy": summarize.get("snippet_policy"),
            "snippet_count": summarize.get("snippet_count"),
            "snippet_max_chars": summarize.get("snippet_max_chars"),
        },
    }


def build_quality_record(
    *,
    root: Path,
    run_dir: Path,
    label: str | None = None,
    notes_path: Path | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    status = read_json_object(run_dir / "farm-status.json")
    notes = load_quality_notes(notes_path)
    jobs = [build_job_record(job, notes) for job in status.get("jobs", []) if isinstance(job, dict)]
    timing = status.get("timing", {})
    if not isinstance(timing, dict):
        timing = {}
    run_label = label or str(status.get("run_id") or run_dir.name)
    return {
        "schema_version": DOGFOOD_HISTORY_SCHEMA_VERSION,
        "recorded_at": recorded_at or utc_now(),
        "label": run_label,
        "commit": current_commit(root),
        "run_id": status.get("run_id"),
        "run_path": str(run_dir),
        "mode": status.get("mode"),
        "model": status.get("model"),
        "status": status.get("status"),
        "duration_ms": timing.get("duration_ms"),
        "runtime": compact_runtime(status),
        "totals": {
            "jobs": len(jobs),
            "chunks": sum(int(job.get("chunk_count", 0) or 0) for job in jobs),
            "warnings": sum(int(job.get("warning_count", 0) or 0) for job in jobs),
            "requested_snippets": sum_snippet_count(jobs, "requested_count"),
            "verified_snippets": sum_snippet_count(jobs, "verified_count"),
            "selected_snippets": sum_snippet_count(jobs, "selected_count"),
            "dropped": sum_drop_counts(jobs),
        },
        "quality": notes["quality"],
        "notes": notes["notes"],
        "jobs": jobs,
    }


def write_quality_record(record: dict[str, Any], output_dir: Path) -> Path:
    filename = f"{safe_label(str(record.get('label') or record.get('run_id') or 'dogfood-run'))}.json"
    path = output_dir / filename
    write_json(path, record)
    return path


def delta(candidate: int | float | None, baseline: int | float | None) -> int | float | None:
    if candidate is None or baseline is None:
        return None
    return candidate - baseline


def compare_quality(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_quality = baseline.get("quality", {})
    candidate_quality = candidate.get("quality", {})
    if not isinstance(baseline_quality, dict):
        baseline_quality = {}
    if not isinstance(candidate_quality, dict):
        candidate_quality = {}
    return {
        field: {
            "baseline": baseline_quality.get(field),
            "candidate": candidate_quality.get(field),
            "delta": delta(candidate_quality.get(field), baseline_quality.get(field)),
        }
        for field in QUALITY_FIELDS
        if field in baseline_quality or field in candidate_quality
    }


def job_key(job: dict[str, Any]) -> str:
    return str(job.get("input_path") or job.get("job_id") or "")


def compare_jobs(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    baseline_jobs = {job_key(job): job for job in baseline.get("jobs", []) if isinstance(job, dict)}
    candidate_jobs = {job_key(job): job for job in candidate.get("jobs", []) if isinstance(job, dict)}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(baseline_jobs) | set(candidate_jobs)):
        old = baseline_jobs.get(key, {})
        new = candidate_jobs.get(key, {})
        old_snippets = old.get("snippets", {}) if isinstance(old.get("snippets", {}), dict) else {}
        new_snippets = new.get("snippets", {}) if isinstance(new.get("snippets", {}), dict) else {}
        rows.append(
            {
                "input_path": key,
                "baseline_status": old.get("status"),
                "candidate_status": new.get("status"),
                "duration_ms": {
                    "baseline": old.get("duration_ms"),
                    "candidate": new.get("duration_ms"),
                    "delta": delta(new.get("duration_ms"), old.get("duration_ms")),
                },
                "warnings": {
                    "baseline": old.get("warning_count", 0),
                    "candidate": new.get("warning_count", 0),
                    "delta": delta(new.get("warning_count", 0), old.get("warning_count", 0)),
                },
                "snippets": {
                    "baseline_selected": old_snippets.get("selected_count", old_snippets.get("verified_count", 0)),
                    "candidate_selected": new_snippets.get("selected_count", new_snippets.get("verified_count", 0)),
                    "baseline_verified": old_snippets.get("verified_count", 0),
                    "candidate_verified": new_snippets.get("verified_count", 0),
                    "baseline_requested": old_snippets.get("requested_count", 0),
                    "candidate_requested": new_snippets.get("requested_count", 0),
                },
            }
        )
    return rows


def compare_records(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_totals = baseline.get("totals", {})
    candidate_totals = candidate.get("totals", {})
    if not isinstance(baseline_totals, dict):
        baseline_totals = {}
    if not isinstance(candidate_totals, dict):
        candidate_totals = {}
    return {
        "schema_version": DOGFOOD_HISTORY_SCHEMA_VERSION,
        "compared_at": utc_now(),
        "baseline": {
            "label": baseline.get("label"),
            "run_id": baseline.get("run_id"),
            "status": baseline.get("status"),
        },
        "candidate": {
            "label": candidate.get("label"),
            "run_id": candidate.get("run_id"),
            "status": candidate.get("status"),
        },
        "duration_ms": {
            "baseline": baseline.get("duration_ms"),
            "candidate": candidate.get("duration_ms"),
            "delta": delta(candidate.get("duration_ms"), baseline.get("duration_ms")),
        },
        "totals": {
            key: {
                "baseline": baseline_totals.get(key),
                "candidate": candidate_totals.get(key),
                "delta": delta(candidate_totals.get(key), baseline_totals.get(key)),
            }
            for key in [
                "jobs",
                "chunks",
                "warnings",
                "requested_snippets",
                "verified_snippets",
                "selected_snippets",
            ]
        },
        "dropped": {
            reason: {
                "baseline": ((baseline_totals.get("dropped") or {}).get(reason, 0)),
                "candidate": ((candidate_totals.get("dropped") or {}).get(reason, 0)),
                "delta": delta(
                    ((candidate_totals.get("dropped") or {}).get(reason, 0)),
                    ((baseline_totals.get("dropped") or {}).get(reason, 0)),
                ),
            }
            for reason in DROP_REASONS
        },
        "quality": compare_quality(baseline, candidate),
        "jobs": compare_jobs(baseline, candidate),
        "notes": {
            "baseline": baseline.get("notes", []),
            "candidate": candidate.get("notes", []),
        },
    }


def format_delta(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and value > 0:
        return f"+{value}"
    return str(value)


def render_comparison_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        f"# Dogfood Comparison {comparison['baseline'].get('label')} -> {comparison['candidate'].get('label')}",
        "",
        "## Runs",
        "",
        "| Field | Baseline | Candidate | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    duration = comparison.get("duration_ms", {})
    lines.append(
        f"| Duration ms | {duration.get('baseline', '')} | {duration.get('candidate', '')} | {format_delta(duration.get('delta'))} |"
    )
    for key, item in comparison.get("totals", {}).items():
        label = key.replace("_", " ").title()
        lines.append(
            f"| {label} | {item.get('baseline', '')} | {item.get('candidate', '')} | {format_delta(item.get('delta'))} |"
        )

    lines.extend(["", "## Quality", "", "| Field | Baseline | Candidate | Delta |", "| --- | ---: | ---: | ---: |"])
    quality = comparison.get("quality", {})
    if quality:
        for key, item in quality.items():
            lines.append(
                f"| {key.replace('_', ' ').title()} | {item.get('baseline', '')} | {item.get('candidate', '')} | {format_delta(item.get('delta'))} |"
            )
    else:
        lines.append("| No quality scores supplied |  |  |  |")

    lines.extend(["", "## Jobs", "", "| Input | Duration Delta | Warnings Delta | Snippets |", "| --- | ---: | ---: | --- |"])
    for job in comparison.get("jobs", []):
        snippets = job.get("snippets", {})
        snippet_text = (
            f"{snippets.get('baseline_selected', 0)}/{snippets.get('baseline_verified', 0)}/{snippets.get('baseline_requested', 0)}"
            " -> "
            f"{snippets.get('candidate_selected', 0)}/{snippets.get('candidate_verified', 0)}/{snippets.get('candidate_requested', 0)}"
        )
        lines.append(
            f"| `{job.get('input_path', '')}` | {format_delta((job.get('duration_ms') or {}).get('delta'))} | "
            f"{format_delta((job.get('warnings') or {}).get('delta'))} | `{snippet_text}` |"
        )

    notes = comparison.get("notes", {})
    candidate_notes = notes.get("candidate", []) if isinstance(notes, dict) else []
    if candidate_notes:
        lines.extend(["", "## Candidate Notes", ""])
        lines.extend(f"- {note}" for note in candidate_notes)
    lines.append("")
    return "\n".join(lines)


def write_comparison(comparison: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    baseline = safe_label(str(comparison["baseline"].get("label") or comparison["baseline"].get("run_id") or "baseline"))
    candidate = safe_label(
        str(comparison["candidate"].get("label") or comparison["candidate"].get("run_id") or "candidate")
    )
    stem = f"{baseline}--{candidate}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    write_json(json_path, comparison)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_comparison_markdown(comparison), encoding="utf-8")
    return json_path, md_path
