from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def timestamp_now() -> str:
    return format_timestamp(utc_now())


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def elapsed_ms(start: datetime, end: datetime) -> int:
    return max(0, round((end - start).total_seconds() * 1000))


def duration_between(start_timestamp: str | None, end_timestamp: str | None) -> int | None:
    start = parse_timestamp(start_timestamp)
    end = parse_timestamp(end_timestamp)
    if start is None or end is None:
        return None
    return elapsed_ms(start, end)


def finish_timing(start: datetime, *, end: datetime | None = None) -> dict[str, Any]:
    completed = end or utc_now()
    return {
        "started_at": format_timestamp(start),
        "completed_at": format_timestamp(completed),
        "duration_ms": elapsed_ms(start, completed),
    }


def duration_label(value: Any) -> str:
    if not isinstance(value, int):
        return ""
    if value < 1000:
        return f"{value}ms"
    seconds = value / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remainder = seconds - (minutes * 60)
    return f"{minutes}m {remainder:.1f}s"


def build_timing_summary(status: dict[str, Any]) -> dict[str, Any]:
    runtime = status.get("runtime") or {}
    jobs = status.get("jobs") or []
    job_rows: list[dict[str, Any]] = []
    call_rows: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "duration_ms": 0})

    for job in jobs:
        timing = job.get("timing") or {}
        job_row = {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "input_path": job.get("input_path"),
            "queue_wait_ms": timing.get("queue_wait_ms"),
            "duration_ms": timing.get("duration_ms"),
            "started_at": timing.get("started_at"),
            "completed_at": timing.get("completed_at"),
        }
        job_rows.append(job_row)

        for call in timing.get("calls") or []:
            call_row = {
                "job_id": job.get("job_id"),
                "input_path": job.get("input_path"),
                **call,
            }
            call_rows.append(call_row)
            kind = str(call.get("kind", "unknown"))
            duration = call.get("duration_ms")
            aggregate[kind]["count"] += 1
            if isinstance(duration, int):
                aggregate[kind]["duration_ms"] += duration

    slowest_jobs = sorted(
        job_rows,
        key=lambda item: item.get("duration_ms") if isinstance(item.get("duration_ms"), int) else -1,
        reverse=True,
    )[:5]
    slowest_calls = sorted(
        call_rows,
        key=lambda item: item.get("duration_ms") if isinstance(item.get("duration_ms"), int) else -1,
        reverse=True,
    )[:10]

    return {
        "schema_version": status.get("schema_version"),
        "run_id": status.get("run_id"),
        "status": status.get("status"),
        "mode": status.get("mode"),
        "agent": status.get("agent"),
        "model": status.get("model"),
        "profile": runtime.get("profile"),
        "resource_mode": runtime.get("resource_mode"),
        "timing": status.get("timing") or {},
        "counts": status.get("counts") or {},
        "jobs": job_rows,
        "calls": call_rows,
        "aggregate_by_call_kind": dict(sorted(aggregate.items())),
        "slowest_jobs": slowest_jobs,
        "slowest_calls": slowest_calls,
    }


def render_timing_summary_markdown(summary: dict[str, Any]) -> str:
    timing = summary.get("timing") or {}
    counts = summary.get("counts") or {}
    aggregate = summary.get("aggregate_by_call_kind") or {}
    lines = [
        f"# Timing Summary {summary.get('run_id', '')}",
        "",
        f"Status: `{summary.get('status', '')}`",
        f"Mode: `{summary.get('mode', '')}`",
        f"Agent: `{summary.get('agent', '')}`",
        f"Model: `{summary.get('model', '')}`",
        f"Profile: `{summary.get('profile', '')}`",
        f"Resource mode: `{((summary.get('resource_mode') or {}) if isinstance(summary.get('resource_mode'), dict) else {}).get('effective') or ''}`",
        f"Duration: `{duration_label(timing.get('duration_ms'))}`",
        "",
        "## Counts",
        "",
        "| Field | Count |",
        "| --- | ---: |",
    ]
    for key in ["total", "queued", "running", "complete", "complete_with_warnings", "failed", "skipped"]:
        lines.append(f"| {key} | {counts.get(key, 0)} |")

    lines.extend(["", "## Aggregate By Call Kind", "", "| Kind | Calls | Duration |", "| --- | ---: | ---: |"])
    if aggregate:
        for kind, values in aggregate.items():
            lines.append(f"| `{kind}` | {values.get('count', 0)} | `{duration_label(values.get('duration_ms'))}` |")
    else:
        lines.append("|  | 0 | `` |")

    lines.extend(["", "## Slowest Jobs", "", "| Job | Status | Input | Queue Wait | Duration |", "| --- | --- | --- | ---: | ---: |"])
    for job in summary.get("slowest_jobs") or []:
        lines.append(
            f"| `{job.get('job_id', '')}` | `{job.get('status', '')}` | `{job.get('input_path', '')}` | "
            f"`{duration_label(job.get('queue_wait_ms'))}` | `{duration_label(job.get('duration_ms'))}` |"
        )

    lines.extend(["", "## Slowest Calls", "", "| Job | Kind | Target | Status | Duration |", "| --- | --- | --- | --- | ---: |"])
    for call in summary.get("slowest_calls") or []:
        target = call.get("chunk_id") or call.get("file_path") or call.get("input_path") or ""
        lines.append(
            f"| `{call.get('job_id', '')}` | `{call.get('kind', '')}` | `{target}` | "
            f"`{call.get('status', '')}` | `{duration_label(call.get('duration_ms'))}` |"
        )

    lines.append("")
    return "\n".join(lines)


def write_timing_summary(run_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
    summary = build_timing_summary(status)
    (run_dir / "timing-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "TIMING_SUMMARY.md").write_text(render_timing_summary_markdown(summary), encoding="utf-8")
    return summary
