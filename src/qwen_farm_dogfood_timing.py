from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.qwen_farm_dogfood import safe_label
from src.qwen_farm_timing import duration_label


DOGFOOD_TIMING_SCHEMA_VERSION = 1
CALL_KIND_FIELDS = ("count", "duration_ms")
TOTAL_FIELDS = ("duration_ms", "jobs", "chunks", "calls", "queue_wait_ms", "call_duration_ms")
JOB_DELTA_FIELDS = ("duration_ms", "queue_wait_ms", "chunk_count", "call_count", "call_duration_ms", "warning_count")
COMPARABILITY_FIELDS = (
    ("model", "model"),
    ("profile", "profile"),
    ("runtime.resource_mode.effective", "resource_mode.effective"),
    ("commit", "commit"),
    ("runtime.concurrency.jobs", "concurrency.jobs"),
    ("runtime.concurrency.chunks", "concurrency.chunks"),
    ("runtime.summarize.chunk_strategy", "summarize.chunk_strategy"),
    ("runtime.summarize.chunk_chars", "summarize.chunk_chars"),
    ("runtime.summarize.reduce_chars", "summarize.reduce_chars"),
    ("runtime.summarize.chunk_tokens", "summarize.chunk_tokens"),
    ("runtime.summarize.reduce_tokens", "summarize.reduce_tokens"),
    ("runtime.summarize.preserve_heading_ancestry", "summarize.preserve_heading_ancestry"),
    ("runtime.summarize.chunk_overlap_chars", "summarize.chunk_overlap_chars"),
    ("runtime.summarize.chunk_overlap_tokens", "summarize.chunk_overlap_tokens"),
    ("runtime.summarize.snippet_policy", "summarize.snippet_policy"),
)


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


def to_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def int_or_zero(value: Any) -> int:
    return to_int(value) or 0


def delta(candidate: int | float | None, baseline: int | float | None) -> int | float | None:
    if candidate is None or baseline is None:
        return None
    return candidate - baseline


def format_delta(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and value > 0:
        return f"+{value}"
    return str(value)


def get_path(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def compact_runtime(status: dict[str, Any]) -> dict[str, Any]:
    runtime = status.get("runtime", {})
    if not isinstance(runtime, dict):
        runtime = {}
    concurrency = runtime.get("concurrency", {})
    if not isinstance(concurrency, dict):
        concurrency = {}
    summarize = runtime.get("summarize", {})
    if not isinstance(summarize, dict):
        summarize = {}
    return {
        "profile": runtime.get("profile"),
        "resource_mode": runtime.get("resource_mode"),
        "model": runtime.get("model", status.get("model")),
        "concurrency": {
            "jobs": concurrency.get("jobs"),
            "chunks": concurrency.get("chunks"),
        },
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


def job_chunk_count(job: dict[str, Any]) -> int:
    chunking = job.get("chunking", {})
    if not isinstance(chunking, dict):
        return 1
    if chunking.get("enabled"):
        return int_or_zero(chunking.get("chunk_count"))
    return 1


def calls_for_job(job: dict[str, Any]) -> list[dict[str, Any]]:
    timing = job.get("timing", {})
    if not isinstance(timing, dict):
        return []
    calls = timing.get("calls", [])
    if not isinstance(calls, list):
        return []
    return [call for call in calls if isinstance(call, dict)]


def aggregate_call_kinds(calls: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    aggregate: dict[str, dict[str, int]] = {}
    for call in calls:
        kind = str(call.get("kind") or "unknown")
        row = aggregate.setdefault(kind, {"count": 0, "duration_ms": 0})
        row["count"] += 1
        row["duration_ms"] += int_or_zero(call.get("duration_ms"))
    return dict(sorted(aggregate.items()))


def compact_aggregate(data: Any) -> dict[str, dict[str, int]]:
    if not isinstance(data, dict):
        return {}
    output: dict[str, dict[str, int]] = {}
    for kind, values in data.items():
        if not isinstance(values, dict):
            continue
        output[str(kind)] = {
            "count": int_or_zero(values.get("count")),
            "duration_ms": int_or_zero(values.get("duration_ms")),
        }
    return dict(sorted(output.items()))


def call_duration(calls: list[dict[str, Any]]) -> int:
    return sum(int_or_zero(call.get("duration_ms")) for call in calls)


def warning_count(job: dict[str, Any]) -> int:
    warnings = job.get("warnings", [])
    return len(warnings) if isinstance(warnings, list) else 0


def build_job_row(job: dict[str, Any]) -> dict[str, Any]:
    timing = job.get("timing", {})
    if not isinstance(timing, dict):
        timing = {}
    calls = calls_for_job(job)
    return {
        "job_id": str(job.get("job_id", "")),
        "input_path": str(job.get("input_path", "")),
        "status": str(job.get("status", "")),
        "duration_ms": timing.get("duration_ms"),
        "queue_wait_ms": timing.get("queue_wait_ms"),
        "chunk_count": job_chunk_count(job),
        "call_count": len(calls),
        "call_duration_ms": call_duration(calls),
        "by_call_kind": aggregate_call_kinds(calls),
        "warning_count": warning_count(job),
    }


def compact_slowest_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job.get("job_id"),
        "input_path": job.get("input_path"),
        "status": job.get("status"),
        "duration_ms": job.get("duration_ms"),
        "queue_wait_ms": job.get("queue_wait_ms"),
    }


def compact_slowest_call(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": call.get("job_id"),
        "input_path": call.get("input_path"),
        "kind": call.get("kind"),
        "target": call.get("chunk_id") or call.get("file_path") or call.get("input_path"),
        "status": call.get("status"),
        "duration_ms": call.get("duration_ms"),
    }


def slowest_jobs_from_rows(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    return [
        compact_slowest_job(row)
        for row in sorted(rows, key=lambda item: int_or_zero(item.get("duration_ms")), reverse=True)[:limit]
    ]


def calls_from_status(status: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    jobs = status.get("jobs", [])
    if not isinstance(jobs, list):
        return []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        for call in calls_for_job(job):
            output.append(
                {
                    "job_id": job.get("job_id"),
                    "input_path": job.get("input_path"),
                    **call,
                }
            )
    return output


def slowest_calls_from_rows(calls: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    return [
        compact_slowest_call(call)
        for call in sorted(calls, key=lambda item: int_or_zero(item.get("duration_ms")), reverse=True)[:limit]
    ]


def timing_summary_for(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "timing-summary.json"
    if not path.exists():
        return {}
    try:
        return read_json_object(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def build_totals(status: dict[str, Any], jobs: list[dict[str, Any]], calls: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    timing = status.get("timing", {})
    if not isinstance(timing, dict):
        timing = {}
    summary_timing = summary.get("timing", {})
    if not isinstance(summary_timing, dict):
        summary_timing = {}
    aggregate = aggregate_call_kinds(calls) or compact_aggregate(summary.get("aggregate_by_call_kind"))
    call_count = sum(int_or_zero(job.get("call_count")) for job in jobs)
    total_call_duration = sum(int_or_zero(job.get("call_duration_ms")) for job in jobs)
    return {
        "duration_ms": timing.get("duration_ms") if timing.get("duration_ms") is not None else summary_timing.get("duration_ms"),
        "jobs": len(jobs),
        "chunks": sum(int_or_zero(job.get("chunk_count")) for job in jobs),
        "calls": call_count or sum(int_or_zero(values.get("count")) for values in aggregate.values()),
        "queue_wait_ms": sum(int_or_zero(job.get("queue_wait_ms")) for job in jobs),
        "call_duration_ms": total_call_duration or sum(int_or_zero(values.get("duration_ms")) for values in aggregate.values()),
        "by_call_kind": aggregate,
    }


def build_timing_record(
    *,
    root: Path,
    run_dir: Path,
    label: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    status = read_json_object(run_dir / "farm-status.json")
    summary = timing_summary_for(run_dir)
    raw_jobs = status.get("jobs", [])
    job_rows = [build_job_row(job) for job in raw_jobs if isinstance(job, dict)] if isinstance(raw_jobs, list) else []
    calls = calls_from_status(status)
    run_label = label or str(status.get("run_id") or run_dir.name)
    runtime = compact_runtime(status)
    return {
        "schema_version": DOGFOOD_TIMING_SCHEMA_VERSION,
        "recorded_at": recorded_at or utc_now(),
        "label": run_label,
        "commit": current_commit(root),
        "run_id": status.get("run_id"),
        "run_path": str(run_dir),
        "status": status.get("status"),
        "mode": status.get("mode"),
        "agent": status.get("agent"),
        "model": status.get("model"),
        "profile": runtime.get("profile"),
        "resource_mode": (runtime.get("resource_mode") or {}).get("effective") if isinstance(runtime.get("resource_mode"), dict) else None,
        "runtime": runtime,
        "totals": build_totals(status, job_rows, calls, summary),
        "slowest_jobs": [
            compact_slowest_job(job)
            for job in summary.get("slowest_jobs", [])
            if isinstance(job, dict)
        ]
        or slowest_jobs_from_rows(job_rows),
        "slowest_calls": [
            compact_slowest_call(call)
            for call in summary.get("slowest_calls", [])
            if isinstance(call, dict)
        ]
        or slowest_calls_from_rows(calls),
        "jobs": job_rows,
    }


def write_timing_record(record: dict[str, Any], output_dir: Path) -> Path:
    filename = f"{safe_label(str(record.get('label') or record.get('run_id') or 'dogfood-timing'))}.json"
    path = output_dir / filename
    write_json(path, record)
    return path


def run_identity(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": record.get("label"),
        "run_id": record.get("run_id"),
        "status": record.get("status"),
        "model": record.get("model"),
        "profile": record.get("profile"),
        "resource_mode": record.get("resource_mode"),
        "commit": record.get("commit"),
    }


def value_delta(baseline: dict[str, Any], candidate: dict[str, Any], field: str) -> dict[str, Any]:
    old = baseline.get(field)
    new = candidate.get(field)
    return {
        "baseline": old,
        "candidate": new,
        "delta": delta(new, old),
    }


def compare_total_fields(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_totals = baseline.get("totals", {})
    candidate_totals = candidate.get("totals", {})
    if not isinstance(baseline_totals, dict):
        baseline_totals = {}
    if not isinstance(candidate_totals, dict):
        candidate_totals = {}
    return {field: value_delta(baseline_totals, candidate_totals, field) for field in TOTAL_FIELDS}


def compare_call_kind_totals(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_kinds = (baseline.get("totals") or {}).get("by_call_kind", {})
    candidate_kinds = (candidate.get("totals") or {}).get("by_call_kind", {})
    if not isinstance(baseline_kinds, dict):
        baseline_kinds = {}
    if not isinstance(candidate_kinds, dict):
        candidate_kinds = {}

    output: dict[str, Any] = {}
    for kind in sorted(set(baseline_kinds) | set(candidate_kinds)):
        old = baseline_kinds.get(kind, {}) if isinstance(baseline_kinds.get(kind), dict) else {}
        new = candidate_kinds.get(kind, {}) if isinstance(candidate_kinds.get(kind), dict) else {}
        output[str(kind)] = {field: value_delta(old, new, field) for field in CALL_KIND_FIELDS}
    return output


def job_key(job: dict[str, Any]) -> str:
    return str(job.get("input_path") or job.get("job_id") or "")


def compare_job_rows(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    baseline_jobs = {job_key(job): job for job in baseline.get("jobs", []) if isinstance(job, dict)}
    candidate_jobs = {job_key(job): job for job in candidate.get("jobs", []) if isinstance(job, dict)}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(baseline_jobs) | set(candidate_jobs)):
        old = baseline_jobs.get(key, {})
        new = candidate_jobs.get(key, {})
        rows.append(
            {
                "input_path": key,
                "baseline_status": old.get("status"),
                "candidate_status": new.get("status"),
                **{field: value_delta(old, new, field) for field in JOB_DELTA_FIELDS},
                "by_call_kind": compare_job_call_kinds(old, new),
            }
        )
    return rows


def compare_job_call_kinds(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    old_kinds = baseline.get("by_call_kind", {}) if isinstance(baseline.get("by_call_kind"), dict) else {}
    new_kinds = candidate.get("by_call_kind", {}) if isinstance(candidate.get("by_call_kind"), dict) else {}
    output: dict[str, Any] = {}
    for kind in sorted(set(old_kinds) | set(new_kinds)):
        old = old_kinds.get(kind, {}) if isinstance(old_kinds.get(kind), dict) else {}
        new = new_kinds.get(kind, {}) if isinstance(new_kinds.get(kind), dict) else {}
        output[str(kind)] = {field: value_delta(old, new, field) for field in CALL_KIND_FIELDS}
    return output


def comparability_notes(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for path, label in COMPARABILITY_FIELDS:
        old = get_path(baseline, path)
        new = get_path(candidate, path)
        if old != new:
            notes.append(f"{label} differs: baseline={old!r}, candidate={new!r}")
    return notes


def build_comparability(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    notes = comparability_notes(baseline, candidate)
    return {
        "comparable": not notes,
        "notes": notes,
    }


def compare_timing_records(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    compared_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": DOGFOOD_TIMING_SCHEMA_VERSION,
        "compared_at": compared_at or utc_now(),
        "baseline": run_identity(baseline),
        "candidate": run_identity(candidate),
        "comparability": build_comparability(baseline, candidate),
        "totals": compare_total_fields(baseline, candidate),
        "by_call_kind": compare_call_kind_totals(baseline, candidate),
        "jobs": compare_job_rows(baseline, candidate),
        "candidate_slowest_jobs": candidate.get("slowest_jobs", []),
        "candidate_slowest_calls": candidate.get("slowest_calls", []),
    }


def render_timing_comparison_markdown(comparison: dict[str, Any]) -> str:
    baseline = comparison.get("baseline", {}) if isinstance(comparison.get("baseline"), dict) else {}
    candidate = comparison.get("candidate", {}) if isinstance(comparison.get("candidate"), dict) else {}
    lines = [
        f"# Dogfood Timing Comparison {baseline.get('label')} -> {candidate.get('label')}",
        "",
        "## Runs",
        "",
        f"Baseline: `{baseline.get('run_id') or ''}`",
        f"Candidate: `{candidate.get('run_id') or ''}`",
        "",
    ]

    comparability = comparison.get("comparability", {}) if isinstance(comparison.get("comparability"), dict) else {}
    notes = comparability.get("notes", []) if isinstance(comparability.get("notes"), list) else []
    lines.extend(["## Comparability", ""])
    if notes:
        lines.append("These runs have setting differences:")
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("No comparable-setting differences detected.")

    lines.extend(["", "## Totals", "", "| Field | Baseline | Candidate | Delta |", "| --- | ---: | ---: | ---: |"])
    totals = comparison.get("totals", {}) if isinstance(comparison.get("totals"), dict) else {}
    for field in TOTAL_FIELDS:
        item = totals.get(field, {}) if isinstance(totals.get(field), dict) else {}
        label = field.replace("_", " ").title()
        lines.append(f"| {label} | {item.get('baseline', '')} | {item.get('candidate', '')} | {format_delta(item.get('delta'))} |")

    lines.extend(["", "## Call Kinds", "", "| Kind | Count Delta | Duration Delta |", "| --- | ---: | ---: |"])
    call_kinds = comparison.get("by_call_kind", {}) if isinstance(comparison.get("by_call_kind"), dict) else {}
    if call_kinds:
        for kind, values in call_kinds.items():
            if not isinstance(values, dict):
                continue
            count = values.get("count", {}) if isinstance(values.get("count"), dict) else {}
            duration = values.get("duration_ms", {}) if isinstance(values.get("duration_ms"), dict) else {}
            lines.append(f"| `{kind}` | {format_delta(count.get('delta'))} | {format_delta(duration.get('delta'))} |")
    else:
        lines.append("|  |  |  |")

    lines.extend(["", "## Candidate Slowest Jobs", "", "| Job | Input | Duration | Queue Wait |", "| --- | --- | ---: | ---: |"])
    for job in comparison.get("candidate_slowest_jobs", []) or []:
        if not isinstance(job, dict):
            continue
        lines.append(
            f"| `{job.get('job_id', '')}` | `{job.get('input_path', '')}` | "
            f"`{duration_label(job.get('duration_ms'))}` | `{duration_label(job.get('queue_wait_ms'))}` |"
        )

    lines.extend(["", "## Candidate Slowest Calls", "", "| Job | Kind | Target | Duration |", "| --- | --- | --- | ---: |"])
    for call in comparison.get("candidate_slowest_calls", []) or []:
        if not isinstance(call, dict):
            continue
        lines.append(
            f"| `{call.get('job_id', '')}` | `{call.get('kind', '')}` | `{call.get('target', '')}` | "
            f"`{duration_label(call.get('duration_ms'))}` |"
        )

    lines.extend(["", "## Jobs", "", "| Input | Duration Delta | Queue Delta | Calls Delta | Call Duration Delta |", "| --- | ---: | ---: | ---: | ---: |"])
    for job in comparison.get("jobs", []) or []:
        if not isinstance(job, dict):
            continue
        duration = job.get("duration_ms", {}) if isinstance(job.get("duration_ms"), dict) else {}
        queue = job.get("queue_wait_ms", {}) if isinstance(job.get("queue_wait_ms"), dict) else {}
        call_count = job.get("call_count", {}) if isinstance(job.get("call_count"), dict) else {}
        call_duration_ms = job.get("call_duration_ms", {}) if isinstance(job.get("call_duration_ms"), dict) else {}
        lines.append(
            f"| `{job.get('input_path', '')}` | {format_delta(duration.get('delta'))} | "
            f"{format_delta(queue.get('delta'))} | {format_delta(call_count.get('delta'))} | "
            f"{format_delta(call_duration_ms.get('delta'))} |"
        )

    lines.append("")
    return "\n".join(lines)


def write_timing_comparison(comparison: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    baseline = safe_label(str((comparison.get("baseline") or {}).get("label") or "baseline"))
    candidate = safe_label(str((comparison.get("candidate") or {}).get("label") or "candidate"))
    stem = f"{baseline}--{candidate}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    write_json(json_path, comparison)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_timing_comparison_markdown(comparison), encoding="utf-8")
    return json_path, markdown_path
