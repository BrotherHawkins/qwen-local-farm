from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.sift_farm_files import utc_timestamp
from src.sift_farm_timing import duration_between, duration_label


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


def progress_summary(job: dict[str, Any]) -> str:
    progress = job.get("progress") if isinstance(job.get("progress"), dict) else {}
    if not progress:
        return ""
    phase = str(progress.get("phase") or "")
    chunks = progress.get("chunks") if isinstance(progress.get("chunks"), dict) else {}
    reduce = progress.get("reduce") if isinstance(progress.get("reduce"), dict) else {}
    current_call = progress.get("current_call") if isinstance(progress.get("current_call"), dict) else {}
    parts = [phase] if phase else []
    total = chunks.get("total")
    if isinstance(total, int) and total > 0:
        complete = chunks.get("complete", 0)
        running = chunks.get("current")
        chunk_text = f"{complete}/{total} chunks complete"
        if running:
            chunk_text += f", {running} running"
        parts.append(chunk_text)
    if phase == "reduce":
        generation = reduce.get("generation")
        batch_index = reduce.get("batch_index")
        batch_total = reduce.get("batch_total")
        if generation is not None:
            reduce_text = f"reduce generation {generation}"
            if batch_index is not None and batch_total is not None:
                reduce_text += f" batch {batch_index}/{batch_total}"
            parts.append(reduce_text)
    if current_call:
        call_text = str(current_call.get("chunk_id") or current_call.get("kind") or "")
        if call_text:
            started_at = current_call.get("started_at")
            duration = duration_between(str(started_at), utc_timestamp()) if started_at and current_call.get("status") == "running" else current_call.get("duration_ms")
            label = duration_label(duration)
            parts.append(f"{call_text}{f' {label}' if label else ''}")
    return "; ".join(parts)


def table_text(value: Any) -> str:
    return str(value or "").replace("\n", " ").replace("|", "\\|")


def failure_summary(failure: Any) -> str:
    if not isinstance(failure, dict):
        return ""
    retryable = "yes" if failure.get("retryable") else "no"
    retry_after_fix = "yes" if failure.get("retry_after_fix") else "no"
    text = (
        f"{failure.get('code', '')} ({failure.get('category', '')}; "
        f"retryable: {retryable}; retry after fix: {retry_after_fix})"
    )
    action = failure.get("recommended_action")
    if action:
        text = f"{text} Next: {action}"
    return table_text(text)


def render_status_markdown(status: dict[str, Any]) -> str:
    counts = status.get("counts", {})
    runtime = status.get("runtime") or {}
    resource_mode = runtime.get("resource_mode") if isinstance(runtime.get("resource_mode"), dict) else {}
    summarize = runtime.get("summarize") or {}
    concurrency = runtime.get("concurrency") or {}
    failure_policy = runtime.get("failure_policy") or {}
    discovery_runtime = runtime.get("discovery") if isinstance(runtime.get("discovery"), dict) else {}
    model_metadata = runtime.get("model_metadata") if isinstance(runtime.get("model_metadata"), dict) else {}
    tokenizer = model_metadata.get("tokenizer") if isinstance(model_metadata.get("tokenizer"), dict) else {}
    context = model_metadata.get("context") if isinstance(model_metadata.get("context"), dict) else {}
    lines = [
        f"# Farm Run {status.get('run_id', '')}",
        "",
        f"Status: `{status.get('status', '')}`",
        "",
        f"Mode: `{status.get('mode', '')}`",
        f"Agent: `{status.get('agent', '')}`",
        f"Model: `{status.get('model', '')}`",
        "",
        "## Timing",
        "",
        f"Started: `{(status.get('timing') or {}).get('started_at') or ''}`",
        f"Completed: `{(status.get('timing') or {}).get('completed_at') or ''}`",
        f"Duration: `{duration_label((status.get('timing') or {}).get('duration_ms'))}`",
        "",
        "## Runtime",
        "",
        f"Profile: `{runtime.get('profile', '')}`",
        f"Resource mode requested: `{resource_mode.get('requested') or ''}`",
        f"Resource mode effective: `{resource_mode.get('effective') or ''}`",
        f"Resource mode source: `{resource_mode.get('source') or ''}`",
        f"Model: `{runtime.get('model', status.get('model', ''))}`",
        f"Model family: `{model_metadata.get('family') or ''}`",
        f"Model backend: `{model_metadata.get('backend') or ''}`",
        f"Model support: `{model_metadata.get('support') or ''}`",
        f"Tokenizer strategy: `{tokenizer.get('strategy') or ''}`",
        f"Tokenizer exact: `{tokenizer.get('exact') if tokenizer.get('exact') is not None else ''}`",
        f"Context tokens: `{context.get('tokens') if context.get('tokens') is not None else ''}`",
        f"Chunk strategy: `{summarize.get('chunk_strategy', '')}`",
        f"Chunk chars: `{summarize.get('chunk_chars', '')}`",
        f"Reduce chars: `{summarize.get('reduce_chars', '')}`",
        f"Chunk tokens: `{summarize.get('chunk_tokens') or ''}`",
        f"Reduce tokens: `{summarize.get('reduce_tokens') or ''}`",
        f"Preserve heading ancestry: `{summarize.get('preserve_heading_ancestry', '')}`",
        f"Chunk overlap chars: `{summarize.get('chunk_overlap_chars', '')}`",
        f"Chunk overlap tokens: `{summarize.get('chunk_overlap_tokens', '')}`",
        f"Snippet policy: `{summarize.get('snippet_policy', 'off')}`",
        f"Snippet count: `{summarize.get('snippet_count') if summarize.get('snippet_count') is not None else ''}`",
        f"Snippet max chars: `{summarize.get('snippet_max_chars', '')}`",
        f"Parallel jobs: `{concurrency.get('jobs', '')}`",
        f"Parallel chunks: `{concurrency.get('chunks', '')}`",
        f"Max attempts: `{failure_policy.get('max_attempts', '')}`",
        f"Per-file timeout seconds: `{failure_policy.get('per_file_timeout_seconds', '')}`",
        f"Chunk max attempts: `{failure_policy.get('chunk_max_attempts', '')}`",
        f"Reduce max attempts: `{failure_policy.get('reduce_max_attempts', '')}`",
        f"Discovery include: `{', '.join(discovery_runtime.get('include') or [])}`",
        f"Discovery exclude: `{', '.join(discovery_runtime.get('exclude') or [])}`",
        "",
        "## Counts",
        "",
        "| Field | Count |",
        "| --- | ---: |",
    ]
    for key in ["total", *COUNT_STATUSES]:
        lines.append(f"| {key} | {counts.get(key, 0)} |")

    retry = status.get("retry") if isinstance(status.get("retry"), dict) else {}
    if retry:
        lines.extend(
            [
                "",
                "## Retry",
                "",
                f"Source run: `{retry.get('source_run_id', '')}`",
                f"Retried files: `{retry.get('retried_count', 0)}` of `{retry.get('source_failed_count', 0)}` failed source jobs",
            ]
        )
        retry_jobs = retry.get("jobs") if isinstance(retry.get("jobs"), list) else []
        if retry_jobs:
            lines.extend(["", "| Source Job | Retry Job | Input | Source Error |", "| --- | --- | --- | --- |"])
            for item in retry_jobs:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"| `{item.get('source_job_id', '')}` | `{item.get('retry_job_id', '')}` | "
                    f"`{item.get('input_path', '')}` | {item.get('source_error') or ''} |"
                )

    lines.extend(
        [
            "",
            "## Jobs",
            "",
            "| Job | Status | Input | Chunking | Snippets | Queue Wait | Duration | Result | Failure | Error |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )

    for job in status.get("jobs", []):
        result = job.get("result_md") or ""
        error = table_text(job.get("error"))
        failure = failure_summary(job.get("failure"))
        timing = job.get("timing") or {}
        chunking = job.get("chunking") or {}
        snippets = job.get("snippets") or {}
        if snippets:
            requested = snippets.get("requested_count", 0)
            verified = snippets.get("verified_count", 0)
            selected = snippets.get("selected_count", verified)
            if selected != verified:
                snippet_text = f"{selected}/{verified}/{requested}"
            else:
                snippet_text = f"{verified}/{requested}"
        else:
            snippet_text = "0/0"
        if chunking.get("enabled"):
            chunking_text = (
                f"{chunking.get('chunk_count', 0)} chunks/"
                f"{chunking.get('strategy', '')}/{chunking.get('coverage', '')}"
            )
        else:
            chunking_text = str(chunking.get("strategy") or "single-pass")
        lines.append(
            f"| `{job.get('job_id', '')}` | `{job.get('status', '')}` | "
            f"`{job.get('input_path', '')}` | `{chunking_text}` | "
            f"`{snippet_text}` | "
            f"`{duration_label(timing.get('queue_wait_ms'))}` | `{duration_label(timing.get('duration_ms'))}` | "
            f"`{result}` | {failure} | {error} |"
        )

    active_jobs = [job for job in status.get("jobs", []) if job.get("status") == "running" and job.get("progress")]
    if active_jobs:
        lines.extend(
            [
                "",
                "## Active Jobs",
                "",
                "| Job | Phase | Progress |",
                "| --- | --- | --- |",
            ]
        )
        for job in active_jobs:
            progress = job.get("progress") if isinstance(job.get("progress"), dict) else {}
            lines.append(
                f"| `{job.get('job_id', '')}` | `{progress.get('phase', '')}` | "
                f"{progress_summary(job)} |"
            )

    skipped = status.get("skipped_files") or []
    if skipped:
        lines.extend(["", "## Skipped Files", ""])
        skipped_details = status.get("discovery", {}).get("skipped", []) if isinstance(status.get("discovery"), dict) else []
        detail_by_path = {
            item.get("path"): item
            for item in skipped_details
            if isinstance(item, dict) and item.get("path")
        }
        for path in skipped:
            detail = detail_by_path.get(path) or {}
            reason = detail.get("reason")
            pattern = detail.get("pattern")
            suffix = ""
            if reason:
                suffix = f" - {reason}"
                if pattern:
                    suffix += f" `{pattern}`"
            lines.append(f"- `{path}`{suffix}")

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


def farm_overview_json(runs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scope": "overview",
        "counts": {
            "runs": len(runs),
        },
        "runs": runs,
    }


def run_status_json(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scope": "run",
        "run_id": status.get("run_id"),
        "run": status,
    }


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
