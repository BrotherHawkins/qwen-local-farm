from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.qwen_farm_files import utc_timestamp


COUNT_STATUSES = [
    "queued",
    "running",
    "complete",
    "complete_with_warnings",
    "failed",
    "skipped",
]


def count_jobs(jobs: list[dict[str, Any]], skipped: int = 0) -> dict[str, int]:
    counts = {status: 0 for status in COUNT_STATUSES}
    counts["total"] = len(jobs)
    counts["skipped"] = skipped
    for job in jobs:
        status = str(job.get("status", "queued"))
        if status in counts:
            counts[status] += 1
    return counts


def final_run_status(jobs: list[dict[str, Any]]) -> str:
    if not jobs:
        return "complete_with_warnings"

    failed = sum(1 for job in jobs if job.get("status") == "failed")
    warning = any(job.get("status") == "complete_with_warnings" or job.get("warnings") for job in jobs)

    if failed == len(jobs):
        return "failed"
    if failed:
        return "partial"
    if warning:
        return "complete_with_warnings"
    return "complete"


def run_status_path(run_dir: Path) -> Path:
    return run_dir / "farm-status.json"


def run_status_markdown_path(run_dir: Path) -> Path:
    return run_dir / "FARM_STATUS.md"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_run_status(run_dir: Path) -> dict[str, Any]:
    return json.loads(run_status_path(run_dir).read_text(encoding="utf-8"))


def write_status(run_dir: Path, status: dict[str, Any]) -> None:
    status["updated_at"] = utc_timestamp()
    write_json(run_status_path(run_dir), status)
    run_status_markdown_path(run_dir).write_text(render_status_markdown(status), encoding="utf-8")


def render_status_markdown(status: dict[str, Any]) -> str:
    counts = status.get("counts", {})
    lines = [
        f"# Farm Run {status.get('run_id', '')}",
        "",
        f"Status: `{status.get('status', '')}`",
        "",
        f"Mode: `{status.get('mode', '')}`",
        f"Agent: `{status.get('agent', '')}`",
        f"Model: `{status.get('model', '')}`",
        "",
        "## Counts",
        "",
        "| Field | Count |",
        "| --- | ---: |",
    ]
    for key in ["total", *COUNT_STATUSES]:
        lines.append(f"| {key} | {counts.get(key, 0)} |")

    lines.extend(
        [
            "",
            "## Jobs",
            "",
            "| Job | Status | Input | Result | Error |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for job in status.get("jobs", []):
        result = job.get("result_md") or ""
        error = (job.get("error") or "").replace("\n", " ")
        lines.append(
            f"| `{job.get('job_id', '')}` | `{job.get('status', '')}` | "
            f"`{job.get('input_path', '')}` | `{result}` | {error} |"
        )

    skipped = status.get("skipped_files") or []
    if skipped:
        lines.extend(["", "## Skipped Files", ""])
        for path in skipped:
            lines.append(f"- `{path}`")

    lines.append("")
    return "\n".join(lines)


def render_farm_overview(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "No farm runs found."

    lines = [
        "# Farm Overview",
        "",
        "| Run | Status | Mode | Counts | Output | Updated |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for run in runs:
        counts = run.get("counts", {})
        count_text = f"{counts.get('complete', 0)}/{counts.get('total', 0)} complete"
        if counts.get("failed", 0):
            count_text += f", {counts.get('failed')} failed"
        lines.append(
            f"| `{run.get('run_id', '')}` | `{run.get('status', '')}` | `{run.get('mode', '')}` | "
            f"{count_text} | `{run.get('output', {}).get('path', '')}` | `{run.get('updated_at', '')}` |"
        )
    return "\n".join(lines)


def render_run_list(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "No farm runs found."

    lines = ["Run ID\tStatus\tMode\tUpdated"]
    for run in runs:
        lines.append(
            f"{run.get('run_id', '')}\t{run.get('status', '')}\t"
            f"{run.get('mode', '')}\t{run.get('updated_at', '')}"
        )
    return "\n".join(lines)
