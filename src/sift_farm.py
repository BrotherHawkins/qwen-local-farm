from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from copy import deepcopy
import json
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from src.sift_farm_chunks import (
    CHUNK_STRATEGY,
    TOKEN_CHUNK_STRATEGY,
    TextChunk,
    chunk_text,
    chunk_text_by_tokens,
    locate_chunk_spans,
    overlap_metadata,
    render_chunk_input,
    render_reduce_input,
)
from src.sift_farm_extract import (
    DEFAULT_EXTRACT_PRESET,
    DEFAULT_EXTRACT_SNIPPET_MAX_CHARS,
    dedupe_items,
    extract_payload,
    render_extract_markdown,
)
from src.sift_farm_files import (
    DiscoveredFile,
    DiscoveryResult,
    FARM_SCHEMA_VERSION,
    create_run_dir,
    discover_text_files,
    farm_home,
    job_id_for,
    relative_to,
    utc_timestamp,
)
from src.sift_farm_model import (
    SUMMARY_MAX_INPUT_CHARS,
    SUMMARY_NUM_BATCH,
    SUMMARY_NUM_PREDICT,
    EXTRACT_NUM_BATCH,
    EXTRACT_NUM_PREDICT,
    FarmModelResult,
    OllamaChatClient,
    process_file_with_model,
    render_summary_markdown,
)
from src.sift_farm_model_metadata import apply_model_metadata
from src.sift_farm_profiles import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_PER_FILE_TIMEOUT_SECONDS,
    RuntimeOverrides,
    compact_runtime_config,
    default_failure_policy,
    default_discovery,
    finalize_runtime_config_for_agent,
    model_is_explicit,
    resolve_runtime_config,
    set_effective_model,
    validate_resolved_config,
)
from src.sift_farm_status import (
    count_jobs,
    final_run_status,
    load_run_status,
    farm_overview_json,
    render_farm_overview,
    render_run_list,
    render_status_markdown,
    run_status_json,
    run_status_path,
    write_json,
    write_status,
)
from src.sift_farm_snippets import (
    DEFAULT_CHUNK_CANDIDATE_SNIPPETS,
    apply_snippet_warning_policy,
    compact_snippet_status,
    empty_snippet_diagnostics,
    resolve_snippet_request,
    reselect_snippets,
)
from src.sift_farm_timing import duration_between, finish_timing, format_timestamp, timestamp_now, utc_now, write_timing_summary
from src.sift_farm_tokenizer import ExactTokenCounter, load_exact_token_counter


SUPPORTED_MODES = {"summarize", "prompt", "extract"}

ModelProcessor = Callable[..., FarmModelResult]
TokenCounterLoader = Callable[..., ExactTokenCounter]
ProgressCallback = Callable[[dict[str, Any]], None]


def run_index_path(root: Path) -> Path:
    return farm_home(root) / "runs.json"


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def read_run_index(root: Path) -> list[dict[str, str]]:
    path = run_index_path(root)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and "run_id" in item and "path" in item]


def write_run_index(root: Path, entries: list[dict[str, str]]) -> None:
    path = run_index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remember_run(root: Path, run_id: str, run_dir: Path) -> None:
    entries = [entry for entry in read_run_index(root) if entry.get("run_id") != run_id]
    entries.insert(0, {"run_id": run_id, "path": str(run_dir)})
    write_run_index(root, entries)


def load_agent(root: Path, agent_id: str, default_model: str) -> dict[str, Any]:
    path = root / "agents" / f"{agent_id}.json"
    if path.exists():
        agent = read_json(path)
    else:
        if agent_id != "default":
            raise ValueError(f"Unknown agent: {agent_id}")
        agent = {}

    agent["id"] = str(agent.get("id") or agent_id)
    agent.setdefault("name", agent["id"])
    agent.setdefault("model", default_model)
    agent.setdefault("system_prompt", "")
    agent.setdefault("options", {})
    return apply_model_metadata(agent)


def make_initial_status(
    *,
    run_id: str,
    run_dir: Path,
    mode: str,
    agent: dict[str, Any],
    instructions: str | None,
    extract_preset: str | None = None,
    extract_focus: str | None = None,
    input_folder: Path,
    jobs: list[dict[str, Any]],
    skipped_files: list[str],
    discovery_metadata: dict[str, Any],
    runtime_config: dict[str, Any],
    retry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    created_at = utc_timestamp()
    timing_created_at = timestamp_now()
    status = {
        "schema_version": FARM_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "running",
        "mode": mode,
        "agent": agent["id"],
        "model": agent["model"],
        "runtime": compact_runtime_config(runtime_config),
        "request": {
            "mode": mode,
            "instructions": instructions,
            "agent": agent["id"],
        },
        "input": {
            "path": str(input_folder),
            "kind": "folder",
        },
        "output": {
            "path": str(run_dir),
        },
        "counts": {},
        "jobs": jobs,
        "skipped_files": skipped_files,
        "discovery": discovery_metadata,
        "created_at": created_at,
        "updated_at": created_at,
        "timing": {
            "created_at": timing_created_at,
            "started_at": timing_created_at,
            "completed_at": None,
            "duration_ms": None,
        },
    }
    if retry is not None:
        status["retry"] = retry
    if mode == "extract":
        status["request"]["extract_preset"] = extract_preset or DEFAULT_EXTRACT_PRESET
        status["request"]["extract_focus"] = extract_focus
    status["counts"] = count_jobs(jobs, skipped=len(skipped_files))
    return status


def result_envelope(
    *,
    job: dict[str, Any],
    mode: str,
    result: FarmModelResult,
    run_dir: Path,
    markdown_path: Path,
    raw_path: Path,
    agent: dict[str, Any],
    chunking: dict[str, Any] | None = None,
    snippets: dict[str, Any] | None = None,
    timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = "complete_with_warnings" if result.warnings or not result.structured_valid else "complete"
    envelope = {
        "schema_version": FARM_SCHEMA_VERSION,
        "job_id": job["job_id"],
        "mode": mode,
        "status": status,
        "structured_valid": result.structured_valid,
        "input": {
            "path": job["input_path"],
        },
        "result": result.payload,
        "artifacts": {
            "markdown": relative_to(markdown_path, run_dir),
            "raw_response": relative_to(raw_path, run_dir),
        },
        "model": {
            "agent": agent["id"],
            "model": agent["model"],
            "metadata": agent.get("model_metadata", {}),
        },
        "warnings": result.warnings,
    }
    if chunking is not None:
        envelope["chunking"] = chunking
    if snippets is not None:
        envelope["snippets"] = snippets
    if timing is not None:
        envelope["timing"] = timing
    return envelope


def result_status(result: FarmModelResult) -> str:
    return "complete_with_warnings" if result.warnings or not result.structured_valid else "complete"


FAILURE_CATALOG: dict[str, dict[str, Any]] = {
    "model_timeout": {
        "category": "transient",
        "retryable": True,
        "retry_after_fix": False,
        "recommended_action": "Retry the failed job, or increase the configured timeout if this repeats.",
    },
    "model_unavailable": {
        "category": "configuration",
        "retryable": False,
        "retry_after_fix": True,
        "recommended_action": "Start Ollama, install the selected model, or choose an available agent/model.",
    },
    "context_overflow": {
        "category": "resource",
        "retryable": False,
        "retry_after_fix": True,
        "recommended_action": "Enable chunking, reduce the configured chunk size, or choose a larger-context model.",
    },
    "input_missing": {
        "category": "input",
        "retryable": False,
        "retry_after_fix": True,
        "recommended_action": "Restore the missing input file or rerun discovery against an existing input folder.",
    },
    "input_unreadable": {
        "category": "input",
        "retryable": False,
        "retry_after_fix": True,
        "recommended_action": "Fix file permissions or convert the input to readable UTF-8 text.",
    },
    "input_empty": {
        "category": "input",
        "retryable": False,
        "retry_after_fix": True,
        "recommended_action": "Provide source text before retrying this job.",
    },
    "model_output_invalid": {
        "category": "model_output",
        "retryable": True,
        "retry_after_fix": False,
        "recommended_action": "Retry the job; if this repeats, simplify the prompt or use a stronger model.",
    },
    "internal_error": {
        "category": "internal",
        "retryable": True,
        "retry_after_fix": False,
        "recommended_action": "Retry once; if this repeats, inspect the error and file a bug with the run artifacts.",
    },
}


def failure_object(code: str, message: str) -> dict[str, Any]:
    template = FAILURE_CATALOG.get(code) or FAILURE_CATALOG["internal_error"]
    return {
        "code": code if code in FAILURE_CATALOG else "internal_error",
        "category": str(template["category"]),
        "retryable": bool(template["retryable"]),
        "retry_after_fix": bool(template["retry_after_fix"]),
        "message": message,
        "recommended_action": str(template["recommended_action"]),
    }


def classify_failure(exc: BaseException) -> dict[str, Any]:
    message = str(exc) or type(exc).__name__
    text = message.lower()
    exc_name = type(exc).__name__.lower()

    if isinstance(exc, FileNotFoundError) or "no such file" in text or ("input file" in text and "not found" in text):
        return failure_object("input_missing", message)
    if isinstance(exc, PermissionError) or "permission denied" in text:
        return failure_object("input_unreadable", message)
    if "no usable text" in text or "empty input" in text:
        return failure_object("input_empty", message)
    if isinstance(exc, TimeoutError) or "timeout" in exc_name or "timed out" in text or "timeout" in text:
        return failure_object("model_timeout", message)
    if (
        "connection refused" in text
        or "failed to establish" in text
        or ("ollama" in text and "unavailable" in text)
        or ("model" in text and ("not found" in text or "not available" in text or "unavailable" in text))
    ):
        return failure_object("model_unavailable", message)
    if (
        "context" in text
        or "num_ctx" in text
        or "token budget" in text
        or "too large" in text
        or ("exceeds" in text and ("token" in text or "context" in text))
    ):
        return failure_object("context_overflow", message)
    if "json" in text or "parse" in text or "schema" in text or "structured" in text:
        return failure_object("model_output_invalid", message)
    return failure_object("internal_error", message)


def render_failure_markdown(job: dict[str, Any], failure: dict[str, Any]) -> str:
    retryable = "yes" if failure.get("retryable") else "no"
    retry_after_fix = "yes" if failure.get("retry_after_fix") else "no"
    lines = [
        "# Failure",
        "",
        f"Job: `{job.get('job_id', '')}`",
        f"Input: `{job.get('input_path', '')}`",
        f"Failure: `{failure.get('code', '')}` ({failure.get('category', '')}, retryable: {retryable}, retry after fix: {retry_after_fix})",
        f"Next: {failure.get('recommended_action', '')}",
        "",
        "## Error",
        "",
        "```text",
        str(failure.get("message") or ""),
        "```",
        "",
    ]
    return "\n".join(lines)


def write_failure_result_files(
    *,
    job: dict[str, Any],
    mode: str,
    run_dir: Path,
    job_dir: Path,
    agent: dict[str, Any],
    failure: dict[str, Any],
    chunking: dict[str, Any],
    snippets: dict[str, Any],
    timing: dict[str, Any],
) -> dict[str, Any]:
    markdown_path = job_dir / "result.md"
    raw_path = job_dir / "raw-response.txt"
    json_path = job_dir / "result.json"
    markdown = render_failure_markdown(job, failure)
    markdown_path.write_text(markdown, encoding="utf-8")
    raw_path.write_text(str(failure.get("message") or ""), encoding="utf-8")
    envelope = {
        "schema_version": FARM_SCHEMA_VERSION,
        "job_id": job["job_id"],
        "mode": mode,
        "status": "failed",
        "structured_valid": False,
        "input": {
            "path": job["input_path"],
        },
        "result": {},
        "artifacts": {
            "markdown": relative_to(markdown_path, run_dir),
            "raw_response": relative_to(raw_path, run_dir),
        },
        "model": {
            "agent": agent["id"],
            "model": agent["model"],
        },
        "warnings": [],
        "error": failure.get("message"),
        "failure": failure,
        "chunking": chunking,
        "snippets": snippets,
        "timing": timing,
    }
    write_json(json_path, envelope)
    return envelope


def single_pass_chunking(
    *,
    chunk_strategy: str | None = None,
    chars: int | None = None,
    tokens: int | None = None,
    chunk_tokens: int | None = None,
    tokenizer: str | None = None,
) -> dict[str, Any]:
    chunking: dict[str, Any] = {
        "enabled": False,
        "strategy": "single-pass",
        "chunk_count": 1,
        "coverage": "full",
    }
    if chunk_strategy == "token":
        chunking.update(
            {
                "strategy": "single-pass-token",
                "chars": chars,
                "tokens": tokens,
                "chunk_tokens": chunk_tokens,
                "tokenizer": tokenizer,
                "counts_are_estimated": False,
            }
        )
    return chunking


def chunk_body_budget(source_path: str, max_input_chars: int) -> int:
    sample = TextChunk(chunk_id="chunk-9999", index=9999, total=9999, text="")
    overhead = len(render_chunk_input(source_path, sample))
    return max(1, max_input_chars - overhead)


def compact_chunking(chunking: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "enabled": bool(chunking.get("enabled")),
        "strategy": str(chunking.get("strategy", "")),
        "chunk_count": int(chunking.get("chunk_count", 0)),
        "coverage": str(chunking.get("coverage", "")),
    }
    if chunking.get("tokenizer"):
        compact["tokenizer"] = chunking.get("tokenizer")
    if chunking.get("counts_are_estimated") is not None:
        compact["counts_are_estimated"] = bool(chunking.get("counts_are_estimated"))
    return compact


def chunk_progress_counts(
    *,
    total: int,
    complete: int = 0,
    running: int = 0,
    failed: int = 0,
    current: str | None = None,
) -> dict[str, Any]:
    queued = max(0, total - complete - running - failed)
    return {
        "total": total,
        "queued": queued,
        "running": running,
        "complete": complete,
        "failed": failed,
        "current": current,
    }


def reduce_progress_counts(
    *,
    generation: int | None = None,
    batch_index: int | None = None,
    batch_total: int | None = None,
    complete: int = 0,
) -> dict[str, Any]:
    return {
        "generation": generation,
        "batch_index": batch_index,
        "batch_total": batch_total,
        "complete": complete,
    }


def progress_snapshot(
    *,
    phase: str,
    message: str,
    chunks: dict[str, Any] | None = None,
    reduce: dict[str, Any] | None = None,
    current_call: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "message": message,
        "updated_at": timestamp_now(),
        "chunks": chunks or chunk_progress_counts(total=0),
        "reduce": reduce or reduce_progress_counts(),
        "current_call": current_call,
    }


def terminal_progress(job: dict[str, Any]) -> dict[str, Any]:
    status = str(job.get("status", ""))
    phase = "complete" if status in {"complete", "complete_with_warnings"} else status
    previous = job.get("progress") if isinstance(job.get("progress"), dict) else {}
    chunks = previous.get("chunks") if isinstance(previous.get("chunks"), dict) else chunk_progress_counts(total=0)
    reduce = previous.get("reduce") if isinstance(previous.get("reduce"), dict) else reduce_progress_counts()
    return progress_snapshot(
        phase=phase,
        message=f"Job {phase}.",
        chunks=chunks,
        reduce=reduce,
        current_call=None,
    )


def chunk_result_envelope(
    *,
    job: dict[str, Any],
    mode: str = "summarize",
    chunk_id: str,
    chunk_index: int,
    chunk_total: int,
    chunk_input_path: Path,
    result: FarmModelResult,
    run_dir: Path,
    markdown_path: Path,
    raw_path: Path,
    agent: dict[str, Any],
    snippets: dict[str, Any] | None = None,
    timing: dict[str, Any] | None = None,
    heading_ancestry: list[dict[str, Any]] | None = None,
    overlap: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = {
        "schema_version": FARM_SCHEMA_VERSION,
        "job_id": job["job_id"],
        "chunk_id": chunk_id,
        "mode": mode,
        "status": result_status(result),
        "structured_valid": result.structured_valid,
        "input": {
            "source_path": job["input_path"],
            "chunk_path": relative_to(chunk_input_path, run_dir),
            "chunk_index": chunk_index,
            "chunk_total": chunk_total,
            "heading_ancestry": heading_ancestry or [],
            "overlap": overlap or {"before_chars": 0, "before_tokens": None, "source": "none"},
        },
        "result": result.payload,
        "artifacts": {
            "markdown": relative_to(markdown_path, run_dir),
            "raw_response": relative_to(raw_path, run_dir),
        },
        "model": {
            "agent": agent["id"],
            "model": agent["model"],
        },
        "warnings": result.warnings,
    }
    if timing is not None:
        envelope["timing"] = timing
    if snippets is not None:
        envelope["snippets"] = snippets
    return envelope


def write_result_files(
    *,
    result: FarmModelResult,
    job_dir: Path,
    job: dict[str, Any],
    mode: str,
    run_dir: Path,
    agent: dict[str, Any],
    chunking: dict[str, Any],
    snippets: dict[str, Any],
    timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_path = job_dir / "raw-response.txt"
    markdown_path = job_dir / "result.md"
    json_path = job_dir / "result.json"
    raw_path.write_text(result.raw_response, encoding="utf-8")
    markdown_path.write_text(result.markdown, encoding="utf-8")
    envelope = result_envelope(
        job=job,
        mode=mode,
        result=result,
        run_dir=run_dir,
        markdown_path=markdown_path,
        raw_path=raw_path,
        agent=agent,
        chunking=chunking,
        snippets=snippets,
        timing=timing,
    )
    write_json(json_path, envelope)
    return envelope


def default_model_processor(
    *,
    mode: str,
    file_path: str,
    content: str,
    instructions: str | None,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
    summary_max_input_chars: int = SUMMARY_MAX_INPUT_CHARS,
    snippet_request: dict[str, Any] | None = None,
    extract_preset: str = DEFAULT_EXTRACT_PRESET,
    extract_focus: str | None = None,
    extract_max_items: int | None = None,
    extract_snippet_max_chars: int = DEFAULT_EXTRACT_SNIPPET_MAX_CHARS,
    extract_source_text: str | None = None,
    extract_source_offset: int = 0,
    extract_chunk_id: str | None = None,
) -> FarmModelResult:
    options = dict(agent.get("options", {}))
    if mode == "summarize":
        requested_snippets = int((snippet_request or {}).get("requested_count", 0))
        options.setdefault("num_predict", SUMMARY_NUM_PREDICT + min(512, requested_snippets * 128))
        options.setdefault("num_batch", SUMMARY_NUM_BATCH)
    if mode == "extract":
        options.setdefault("num_predict", EXTRACT_NUM_PREDICT)
        options.setdefault("num_batch", EXTRACT_NUM_BATCH)
    client = OllamaChatClient(ollama_base_url, str(agent["model"]), options)
    return process_file_with_model(
        client=client,
        mode=mode,
        file_path=file_path,
        content=content,
        instructions=instructions,
        timeout=timeout,
        agent_system_prompt=str(agent.get("system_prompt", "")),
        summary_max_input_chars=summary_max_input_chars,
        snippet_request=snippet_request,
        extract_preset=extract_preset,
        extract_focus=extract_focus,
        extract_max_items=extract_max_items or 10,
        extract_snippet_max_chars=extract_snippet_max_chars,
        extract_source_text=extract_source_text,
        extract_source_offset=extract_source_offset,
        extract_chunk_id=extract_chunk_id,
    )


def timed_model_call(
    *,
    call_timings: list[dict[str, Any]],
    kind: str,
    mode: str,
    file_path: str,
    content: str,
    instructions: str | None,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
    summary_max_input_chars: int,
    model_processor: ModelProcessor,
    snippet_request: dict[str, Any] | None = None,
    extract_preset: str = DEFAULT_EXTRACT_PRESET,
    extract_focus: str | None = None,
    extract_max_items: int | None = None,
    extract_snippet_max_chars: int = DEFAULT_EXTRACT_SNIPPET_MAX_CHARS,
    extract_source_text: str | None = None,
    extract_source_offset: int = 0,
    chunk_id: str | None = None,
    reduce_generation: int | None = None,
    reduce_batch_index: int | None = None,
    attempt: int = 1,
    max_attempts: int = 1,
    progress_callback: ProgressCallback | None = None,
    progress_context: dict[str, Any] | None = None,
) -> FarmModelResult:
    started = utc_now()
    record: dict[str, Any] = {
        "kind": kind,
        "file_path": file_path,
        "started_at": format_timestamp(started),
        "completed_at": None,
        "duration_ms": None,
        "status": "running",
    }
    if chunk_id is not None:
        record["chunk_id"] = chunk_id
    if reduce_generation is not None:
        record["reduce_generation"] = reduce_generation
    if reduce_batch_index is not None:
        record["reduce_batch_index"] = reduce_batch_index
    record["attempt"] = attempt
    record["max_attempts"] = max_attempts
    if progress_callback is not None:
        progress_callback(
            {
                "event": "call_started",
                "calls": [*call_timings, dict(record)],
                "current_call": dict(record),
                **(progress_context or {}),
            }
        )

    try:
        result = model_processor(
            mode=mode,
            file_path=file_path,
            content=content,
            instructions=instructions,
            agent=agent,
            ollama_base_url=ollama_base_url,
            timeout=timeout,
            summary_max_input_chars=summary_max_input_chars,
            snippet_request=snippet_request,
            extract_preset=extract_preset,
            extract_focus=extract_focus,
            extract_max_items=extract_max_items,
            extract_snippet_max_chars=extract_snippet_max_chars,
            extract_source_text=extract_source_text,
            extract_source_offset=extract_source_offset,
            extract_chunk_id=chunk_id,
        )
    except Exception as exc:
        record.update(finish_timing(started))
        record["status"] = "failed"
        record["error"] = str(exc)
        call_timings.append(record)
        if progress_callback is not None:
            progress_callback(
                {
                    "event": "call_finished",
                    "calls": [dict(call) for call in call_timings],
                    "current_call": dict(record),
                    **(progress_context or {}),
                }
            )
        raise

    record.update(finish_timing(started))
    record["status"] = result_status(result)
    if result.warnings:
        record["warnings"] = result.warnings
    call_timings.append(record)
    if progress_callback is not None:
        progress_callback(
            {
                "event": "call_finished",
                "calls": [dict(call) for call in call_timings],
                "current_call": dict(record),
                **(progress_context or {}),
            }
        )
    return result


def retry_model_call(
    *,
    max_attempts: int,
    **kwargs: Any,
) -> FarmModelResult:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return timed_model_call(
                **kwargs,
                attempt=attempt,
                max_attempts=max_attempts,
            )
        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts:
                raise
    raise RuntimeError("Retry loop ended without a result.") from last_error


def unique_warnings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def reduce_instructions_for(instructions: str | None) -> str:
    reduce_instructions = (
        "Synthesize the chunk summaries into one file-level summary. "
        "Capture the source thesis, key claims, useful examples, and open questions."
    )
    if instructions:
        reduce_instructions = f"{reduce_instructions} Caller instructions: {instructions}"
    return reduce_instructions


def reduce_payload_batches(
    source_path: str,
    payloads: list[dict[str, Any]],
    max_chars: int,
) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for payload in payloads:
        candidate = [*current, payload]
        if current and len(render_reduce_input(source_path, candidate)) > max_chars:
            batches.append(current)
            current = [payload]
        else:
            current = candidate

    if current:
        batches.append(current)
    return batches


def reduce_payload_batches_by_tokens(
    source_path: str,
    payloads: list[dict[str, Any]],
    max_tokens: int,
    token_counter: ExactTokenCounter,
) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for payload in payloads:
        candidate = [*current, payload]
        if token_counter.count_tokens(render_reduce_input(source_path, candidate)) <= max_tokens:
            current = candidate
            continue
        if current:
            batches.append(current)
            current = [payload]
        else:
            raise ValueError(
                f"Reduce input for `{source_path}` exceeds reduce token budget of {max_tokens} tokens."
            )

    if current:
        if token_counter.count_tokens(render_reduce_input(source_path, current)) > max_tokens:
            raise ValueError(
                f"Reduce input for `{source_path}` exceeds reduce token budget of {max_tokens} tokens."
            )
        batches.append(current)
    return batches


def reduce_summary_payloads(
    *,
    source_path: str,
    payloads: list[dict[str, Any]],
    instructions: str | None,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
    reduce_chars: int,
    reduce_tokens: int | None,
    chunk_strategy: str,
    token_counter: ExactTokenCounter | None,
    model_processor: ModelProcessor,
    call_timings: list[dict[str, Any]],
    reduce_max_attempts: int,
    progress_callback: ProgressCallback | None = None,
    chunk_total: int = 0,
) -> tuple[FarmModelResult, list[str]]:
    warnings: list[str] = []
    pending = payloads
    generation = 1

    while True:
        reduce_input = render_reduce_input(source_path, pending)
        if chunk_strategy == "token":
            if token_counter is None or reduce_tokens is None:
                raise ValueError("Token-aware reduce requires an exact token counter and reduce token budget.")
            reduce_fits = token_counter.count_tokens(reduce_input) <= reduce_tokens
        else:
            reduce_fits = len(reduce_input) <= reduce_chars

        if reduce_fits or len(pending) <= 1:
            if chunk_strategy == "token" and not reduce_fits:
                raise ValueError(
                    f"Reduce input for `{source_path}` exceeds reduce token budget of {reduce_tokens} tokens."
                )
            result = retry_model_call(
                call_timings=call_timings,
                kind="reduce",
                mode="summarize",
                file_path=source_path,
                content=reduce_input,
                instructions=reduce_instructions_for(instructions),
                agent=agent,
                ollama_base_url=ollama_base_url,
                timeout=timeout,
                summary_max_input_chars=len(reduce_input) if chunk_strategy == "token" else reduce_chars,
                model_processor=model_processor,
                reduce_generation=generation,
                max_attempts=reduce_max_attempts,
                progress_callback=progress_callback,
                progress_context={
                    "progress": progress_snapshot(
                        phase="reduce",
                        message="Reducing chunk summaries.",
                        chunks=chunk_progress_counts(total=chunk_total, complete=chunk_total),
                        reduce=reduce_progress_counts(
                            generation=generation,
                            batch_index=1,
                            batch_total=1,
                            complete=0,
                        ),
                    )
                },
            )
            if progress_callback is not None:
                progress_callback(
                    {
                        "progress": progress_snapshot(
                            phase="reduce",
                            message="Completed reduce.",
                            chunks=chunk_progress_counts(total=chunk_total, complete=chunk_total),
                            reduce=reduce_progress_counts(
                                generation=generation,
                                batch_index=1,
                                batch_total=1,
                                complete=1,
                            ),
                        ),
                        "calls": [dict(call) for call in call_timings],
                    }
                )
            warnings.extend(result.warnings)
            return result, warnings

        next_pending: list[dict[str, Any]] = []
        if chunk_strategy == "token":
            if token_counter is None or reduce_tokens is None:
                raise ValueError("Token-aware reduce requires an exact token counter and reduce token budget.")
            batches = reduce_payload_batches_by_tokens(source_path, pending, reduce_tokens, token_counter)
        else:
            batches = reduce_payload_batches(source_path, pending, max_chars=reduce_chars)

        for batch_index, batch in enumerate(batches, start=1):
            batch_input = render_reduce_input(source_path, batch)
            result = retry_model_call(
                call_timings=call_timings,
                kind="reduce",
                mode="summarize",
                file_path=f"{source_path}#reduce-{generation:02d}-{batch_index:04d}",
                content=batch_input,
                instructions=reduce_instructions_for(instructions),
                agent=agent,
                ollama_base_url=ollama_base_url,
                timeout=timeout,
                summary_max_input_chars=len(batch_input) if chunk_strategy == "token" else reduce_chars,
                model_processor=model_processor,
                reduce_generation=generation,
                reduce_batch_index=batch_index,
                max_attempts=reduce_max_attempts,
                progress_callback=progress_callback,
                progress_context={
                    "progress": progress_snapshot(
                        phase="reduce",
                        message=f"Reducing batch {batch_index} of {len(batches)}.",
                        chunks=chunk_progress_counts(total=chunk_total, complete=chunk_total),
                        reduce=reduce_progress_counts(
                            generation=generation,
                            batch_index=batch_index,
                            batch_total=len(batches),
                            complete=batch_index - 1,
                        ),
                    )
                },
            )
            if progress_callback is not None:
                progress_callback(
                    {
                        "progress": progress_snapshot(
                            phase="reduce",
                            message=f"Completed reduce batch {batch_index} of {len(batches)}.",
                            chunks=chunk_progress_counts(total=chunk_total, complete=chunk_total),
                            reduce=reduce_progress_counts(
                                generation=generation,
                                batch_index=batch_index,
                                batch_total=len(batches),
                                complete=batch_index,
                            ),
                        ),
                        "calls": [dict(call) for call in call_timings],
                    }
                )
            warnings.extend(result.warnings)
            next_pending.append(result.payload)

        pending = next_pending
        generation += 1


def run_single_pass_job(
    *,
    mode: str,
    file_path: str,
    content: str,
    instructions: str | None,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
    chunk_chars: int,
    chunk_strategy: str,
    chunk_tokens: int | None,
    token_counter: ExactTokenCounter | None,
    model_processor: ModelProcessor,
    call_timings: list[dict[str, Any]],
    snippet_request: dict[str, Any],
    extract_config: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[FarmModelResult, dict[str, Any], dict[str, Any]]:
    extract_config = extract_config or {}
    result = timed_model_call(
        call_timings=call_timings,
        kind="single",
        mode=mode,
        file_path=file_path,
        content=content,
        instructions=instructions,
        agent=agent,
        ollama_base_url=ollama_base_url,
        timeout=timeout,
        summary_max_input_chars=len(content) if chunk_strategy == "token" else chunk_chars,
        model_processor=model_processor,
        snippet_request=snippet_request,
        extract_preset=str(extract_config.get("preset", DEFAULT_EXTRACT_PRESET)),
        extract_focus=extract_config.get("focus"),
        extract_max_items=int(extract_config.get("max_items_per_file", 10)),
        extract_snippet_max_chars=int(extract_config.get("snippet_max_chars", DEFAULT_EXTRACT_SNIPPET_MAX_CHARS)),
        extract_source_text=content,
        extract_source_offset=0,
        progress_callback=progress_callback,
        progress_context={
            "progress": progress_snapshot(
                phase="single",
                message="Running single-pass model call.",
                chunks=chunk_progress_counts(total=1, running=1, current="single"),
            )
        },
    )
    tokens = token_counter.count_tokens(content) if chunk_strategy == "token" and token_counter is not None else None
    fallback_snippet_count = len(result.payload.get("snippets") or [])
    snippet_selection = result.snippet_selection or {
        **empty_snippet_diagnostics(
            policy=str(snippet_request.get("policy", "off")),
            requested_count=int(snippet_request.get("requested_count", 0)),
            max_chars=int(snippet_request.get("max_chars", 600)),
        ),
        "verified_count": fallback_snippet_count,
        "selected_count": fallback_snippet_count,
    }
    return (
        result,
        single_pass_chunking(
            chunk_strategy=chunk_strategy,
            chars=len(content),
            tokens=tokens,
            chunk_tokens=chunk_tokens,
            tokenizer=token_counter.tokenizer_id if token_counter is not None else None,
        ),
        compact_snippet_status(
            snippet_request,
            int(snippet_selection.get("verified_count", len(result.payload.get("snippets") or []))),
            selected_count=int(snippet_selection.get("selected_count", len(result.payload.get("snippets") or []))),
            diagnostics=snippet_selection,
        ),
    )


def run_chunked_summary_job(
    *,
    job: dict[str, Any],
    job_dir: Path,
    run_dir: Path,
    content: str,
    instructions: str | None,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
    chunk_chars: int,
    reduce_chars: int,
    chunk_strategy: str,
    chunk_tokens: int | None,
    reduce_tokens: int | None,
    token_counter: ExactTokenCounter | None,
    model_processor: ModelProcessor,
    call_timings: list[dict[str, Any]],
    runtime_summarize: dict[str, Any],
    failure_policy: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
) -> tuple[FarmModelResult, dict[str, Any], dict[str, Any]]:
    chunk_max_attempts = int(failure_policy.get("chunk_max_attempts", DEFAULT_MAX_ATTEMPTS))
    reduce_max_attempts = int(failure_policy.get("reduce_max_attempts", DEFAULT_MAX_ATTEMPTS))
    preserve_heading_ancestry = bool(runtime_summarize.get("preserve_heading_ancestry", True))
    chunk_overlap_chars = int(runtime_summarize.get("chunk_overlap_chars", 0))
    chunk_overlap_tokens = int(runtime_summarize.get("chunk_overlap_tokens", 0))
    if progress_callback is not None:
        progress_callback(
            {
                "progress": progress_snapshot(
                    phase="planning_chunks",
                    message="Planning chunks.",
                )
            }
        )
    if chunk_strategy == "token":
        if token_counter is None or chunk_tokens is None:
            raise ValueError("Token-aware chunking requires an exact token counter and chunk token budget.")
        chunks = chunk_text_by_tokens(
            content,
            max_input_tokens=chunk_tokens,
            token_counter=token_counter,
            source_path=job["input_path"],
            preserve_heading_ancestry=preserve_heading_ancestry,
            overlap_tokens=chunk_overlap_tokens,
        )
        strategy_name = TOKEN_CHUNK_STRATEGY
    else:
        chunks = chunk_text(
            content,
            max_chars=chunk_body_budget(job["input_path"], chunk_chars),
            preserve_heading_ancestry=preserve_heading_ancestry,
            overlap_chars=chunk_overlap_chars,
        )
        strategy_name = CHUNK_STRATEGY
    chunks_dir = job_dir / "chunks"
    chunk_results_dir = job_dir / "chunk-results"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_results_dir.mkdir(parents=True, exist_ok=True)
    planned_chunking = compact_chunking(
        {
            "enabled": True,
            "strategy": strategy_name,
            "chunk_count": len(chunks),
            "coverage": "full",
            "tokenizer": token_counter.tokenizer_id if token_counter is not None else None,
            "counts_are_estimated": False if token_counter is not None else None,
        }
    )
    if progress_callback is not None:
        progress_callback(
            {
                "chunking": planned_chunking,
                "progress": progress_snapshot(
                    phase="chunk_map",
                    message=f"Planned {len(chunks)} chunks.",
                    chunks=chunk_progress_counts(total=len(chunks), complete=0, running=0),
                ),
            }
        )

    chunk_records: list[dict[str, Any]] = []
    chunk_payloads: list[dict[str, Any]] = []
    chunk_snippets: list[dict[str, Any]] = []
    warnings: list[str] = []
    source_tokens = token_counter.count_tokens(content) if token_counter is not None else None
    final_snippet_request = resolve_snippet_request(
        runtime_summarize,
        source_chars=len(content),
        source_tokens=source_tokens,
        chunk_count=len(chunks),
    )
    if int(final_snippet_request.get("requested_count", 0)) > 0:
        chunk_snippet_request = resolve_snippet_request(
            runtime_summarize,
            source_chars=len(content),
            source_tokens=source_tokens,
            chunk_count=len(chunks),
            candidate_count=DEFAULT_CHUNK_CANDIDATE_SNIPPETS,
        )
    else:
        chunk_snippet_request = {"policy": "off", "requested_count": 0, "max_chars": runtime_summarize["snippet_max_chars"]}

    for chunk in chunks:
        chunk_input_path = chunks_dir / f"{chunk.chunk_id}.txt"
        chunk_input_path.write_text(render_chunk_input(job["input_path"], chunk), encoding="utf-8")
        chunk_input = chunk_input_path.read_text(encoding="utf-8")
        chunk_call_context = {
            "progress": progress_snapshot(
                phase="chunk_map",
                message=f"Summarizing chunk {chunk.index} of {chunk.total}.",
                chunks=chunk_progress_counts(
                    total=len(chunks),
                    complete=len(chunk_records),
                    running=1,
                    current=chunk.chunk_id,
                ),
            )
        }

        chunk_result = retry_model_call(
            call_timings=call_timings,
            kind="chunk_map",
            mode="summarize",
            file_path=f"{job['input_path']}#{chunk.chunk_id}",
            content=chunk_input,
            instructions=instructions,
            agent=agent,
            ollama_base_url=ollama_base_url,
            timeout=timeout,
            summary_max_input_chars=len(chunk_input),
            model_processor=model_processor,
            snippet_request=chunk_snippet_request,
            chunk_id=chunk.chunk_id,
            max_attempts=chunk_max_attempts,
            progress_callback=progress_callback,
            progress_context=chunk_call_context,
        )
        warnings.extend(warning for warning in chunk_result.warnings if not warning.startswith("snippet_"))
        chunk_verified_snippets = chunk_result.payload.get("snippets") or []
        if isinstance(chunk_verified_snippets, list):
            chunk_snippets.extend(item for item in chunk_verified_snippets if isinstance(item, dict))
        chunk_selection = chunk_result.snippet_selection or {
            **empty_snippet_diagnostics(
                policy=str(chunk_snippet_request.get("policy", "off")),
                requested_count=int(chunk_snippet_request.get("requested_count", 0)),
                max_chars=int(chunk_snippet_request.get("max_chars", 600)),
            ),
            "verified_count": len(chunk_verified_snippets),
            "selected_count": len(chunk_verified_snippets),
        }

        chunk_dir = chunk_results_dir / chunk.chunk_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        raw_path = chunk_dir / "raw-response.txt"
        markdown_path = chunk_dir / "result.md"
        json_path = chunk_dir / "result.json"
        raw_path.write_text(chunk_result.raw_response, encoding="utf-8")
        markdown_path.write_text(chunk_result.markdown, encoding="utf-8")
        envelope = chunk_result_envelope(
            job=job,
            chunk_id=chunk.chunk_id,
            chunk_index=chunk.index,
            chunk_total=chunk.total,
            chunk_input_path=chunk_input_path,
            result=chunk_result,
            run_dir=run_dir,
            markdown_path=markdown_path,
            raw_path=raw_path,
            agent=agent,
            snippets=compact_snippet_status(
                chunk_snippet_request,
                int(chunk_selection.get("verified_count", len(chunk_verified_snippets))),
                selected_count=int(chunk_selection.get("selected_count", len(chunk_verified_snippets))),
                diagnostics=chunk_selection,
            ),
            timing=call_timings[-1],
            heading_ancestry=chunk.heading_ancestry,
            overlap=overlap_metadata(chunk),
        )
        write_json(json_path, envelope)
        chunk_payloads.append(chunk_result.payload)
        chunk_records.append(
            {
                "chunk_id": chunk.chunk_id,
                "chars": chunk.chars or len(chunk.text),
                "tokens": chunk.tokens,
                "heading_ancestry": chunk.heading_ancestry,
                "overlap": overlap_metadata(chunk),
                "input": relative_to(chunk_input_path, run_dir),
                "result_json": relative_to(json_path, run_dir),
                "result_md": relative_to(markdown_path, run_dir),
                "status": envelope["status"],
                "warnings": chunk_result.warnings,
            }
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "chunking": planned_chunking,
                    "progress": progress_snapshot(
                        phase="chunk_map",
                        message=f"Completed chunk {chunk.index} of {chunk.total}.",
                        chunks=chunk_progress_counts(
                            total=len(chunks),
                            complete=len(chunk_records),
                            running=0,
                        ),
                    ),
                    "calls": [dict(call) for call in call_timings],
                }
            )

    reduce_result, reduce_warnings = reduce_summary_payloads(
        source_path=job["input_path"],
        payloads=chunk_payloads,
        instructions=instructions,
        agent=agent,
        ollama_base_url=ollama_base_url,
        timeout=timeout,
        reduce_chars=reduce_chars,
        reduce_tokens=reduce_tokens,
        chunk_strategy=chunk_strategy,
        token_counter=token_counter,
        model_processor=model_processor,
        call_timings=call_timings,
        reduce_max_attempts=reduce_max_attempts,
        progress_callback=progress_callback,
        chunk_total=len(chunks),
    )
    warnings.extend(reduce_warnings)
    final_snippets: list[dict[str, Any]] = []
    if int(final_snippet_request.get("requested_count", 0)) > 0:
        final_snippets, snippet_warnings, final_snippet_selection = reselect_snippets(
            chunk_snippets,
            source_text=content,
            source_path=job["input_path"],
            requested_count=int(final_snippet_request.get("requested_count", 0)),
            max_chars=int(final_snippet_request.get("max_chars", 600)),
            policy=str(final_snippet_request.get("policy", "off")),
        )
        snippet_warnings = apply_snippet_warning_policy(
            snippet_warnings,
            snippet_request=final_snippet_request,
            verified_count=int(final_snippet_selection.get("selected_count", len(final_snippets))),
        )
        warnings.extend(snippet_warnings)
        reduce_result.payload["snippets"] = final_snippets
        reduce_result = FarmModelResult(
            payload=reduce_result.payload,
            markdown=render_summary_markdown(reduce_result.payload),
            raw_response=reduce_result.raw_response,
            structured_valid=reduce_result.structured_valid,
            warnings=reduce_result.warnings,
            snippet_selection=final_snippet_selection,
        )
    else:
        final_snippet_selection = empty_snippet_diagnostics(
            policy=str(final_snippet_request.get("policy", "off")),
            requested_count=int(final_snippet_request.get("requested_count", 0)),
            max_chars=int(final_snippet_request.get("max_chars", 600)),
        )
    final_result = FarmModelResult(
        payload=reduce_result.payload,
        markdown=reduce_result.markdown,
        raw_response=reduce_result.raw_response,
        structured_valid=reduce_result.structured_valid,
        warnings=unique_warnings(warnings),
        snippet_selection=final_snippet_selection,
    )
    chunking = {
        "enabled": True,
        "strategy": strategy_name,
        "chunk_count": len(chunks),
        "coverage": "full",
        "chunk_chars": chunk_chars if chunk_strategy == "character" else None,
        "reduce_chars": reduce_chars if chunk_strategy == "character" else None,
        "chunk_tokens": chunk_tokens if chunk_strategy == "token" else None,
        "reduce_tokens": reduce_tokens if chunk_strategy == "token" else None,
        "preserve_heading_ancestry": preserve_heading_ancestry,
        "chunk_overlap_chars": chunk_overlap_chars,
        "chunk_overlap_tokens": chunk_overlap_tokens,
        "tokenizer": token_counter.tokenizer_id if token_counter is not None else None,
        "counts_are_estimated": False if token_counter is not None else None,
        "chunks": chunk_records,
    }
    return (
        final_result,
        chunking,
        compact_snippet_status(
            final_snippet_request,
            int(final_snippet_selection.get("verified_count", len(final_snippets))),
            selected_count=int(final_snippet_selection.get("selected_count", len(final_snippets))),
            diagnostics=final_snippet_selection,
        ),
    )


def run_chunked_extract_job(
    *,
    job: dict[str, Any],
    job_dir: Path,
    run_dir: Path,
    content: str,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
    chunk_strategy: str,
    token_counter: ExactTokenCounter | None,
    model_processor: ModelProcessor,
    call_timings: list[dict[str, Any]],
    runtime_extract: dict[str, Any],
    failure_policy: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
) -> tuple[FarmModelResult, dict[str, Any], dict[str, Any]]:
    chunk_max_attempts = int(failure_policy.get("chunk_max_attempts", DEFAULT_MAX_ATTEMPTS))
    preserve_heading_ancestry = bool(runtime_extract.get("preserve_heading_ancestry", True))
    chunk_overlap_chars = int(runtime_extract.get("chunk_overlap_chars", 0))
    chunk_overlap_tokens = int(runtime_extract.get("chunk_overlap_tokens", 0))
    chunk_chars = int(runtime_extract["chunk_chars"])
    chunk_tokens = runtime_extract.get("chunk_tokens")
    if progress_callback is not None:
        progress_callback({"progress": progress_snapshot(phase="planning_chunks", message="Planning extract chunks.")})

    if chunk_strategy == "token":
        if token_counter is None or chunk_tokens is None:
            raise ValueError("Token-aware extract chunking requires an exact token counter and chunk token budget.")
        chunks = chunk_text_by_tokens(
            content,
            max_input_tokens=int(chunk_tokens),
            token_counter=token_counter,
            source_path=job["input_path"],
            preserve_heading_ancestry=preserve_heading_ancestry,
            overlap_tokens=chunk_overlap_tokens,
        )
        strategy_name = TOKEN_CHUNK_STRATEGY
    else:
        chunks = chunk_text(
            content,
            max_chars=chunk_body_budget(job["input_path"], chunk_chars),
            preserve_heading_ancestry=preserve_heading_ancestry,
            overlap_chars=chunk_overlap_chars,
        )
        strategy_name = CHUNK_STRATEGY
    spans = locate_chunk_spans(content, chunks)

    chunks_dir = job_dir / "chunks"
    chunk_results_dir = job_dir / "chunk-results"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_results_dir.mkdir(parents=True, exist_ok=True)
    planned_chunking = compact_chunking(
        {
            "enabled": True,
            "strategy": strategy_name,
            "chunk_count": len(chunks),
            "coverage": "full",
            "tokenizer": token_counter.tokenizer_id if token_counter is not None else None,
            "counts_are_estimated": False if token_counter is not None else None,
        }
    )
    if progress_callback is not None:
        progress_callback(
            {
                "chunking": planned_chunking,
                "progress": progress_snapshot(
                    phase="chunk_map",
                    message=f"Planned {len(chunks)} extract chunks.",
                    chunks=chunk_progress_counts(total=len(chunks), complete=0, running=0),
                ),
            }
        )

    chunk_records: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    diagnostics = {
        "candidate_count": 0,
        "parsed_count": 0,
        "invalid_line_count": 0,
        "unsupported_type_count": 0,
        "invalid_line_samples": [],
    }

    for chunk, (source_start, _source_end) in zip(chunks, spans):
        chunk_input_path = chunks_dir / f"{chunk.chunk_id}.txt"
        chunk_input_path.write_text(render_chunk_input(job["input_path"], chunk), encoding="utf-8")
        chunk_call_context = {
            "progress": progress_snapshot(
                phase="chunk_map",
                message=f"Extracting chunk {chunk.index} of {chunk.total}.",
                chunks=chunk_progress_counts(
                    total=len(chunks),
                    complete=len(chunk_records),
                    running=1,
                    current=chunk.chunk_id,
                ),
            )
        }
        chunk_result = retry_model_call(
            call_timings=call_timings,
            kind="chunk_map",
            mode="extract",
            file_path=f"{job['input_path']}#{chunk.chunk_id}",
            content=chunk.text,
            instructions=None,
            agent=agent,
            ollama_base_url=ollama_base_url,
            timeout=timeout,
            summary_max_input_chars=len(chunk.text),
            model_processor=model_processor,
            chunk_id=chunk.chunk_id,
            max_attempts=chunk_max_attempts,
            progress_callback=progress_callback,
            progress_context=chunk_call_context,
            extract_preset=str(runtime_extract.get("preset", DEFAULT_EXTRACT_PRESET)),
            extract_focus=runtime_extract.get("focus"),
            extract_max_items=int(runtime_extract.get("max_items_per_chunk", 10)),
            extract_snippet_max_chars=int(runtime_extract.get("snippet_max_chars", DEFAULT_EXTRACT_SNIPPET_MAX_CHARS)),
            extract_source_text=chunk.text,
            extract_source_offset=source_start,
        )
        warnings.extend(chunk_result.warnings)
        payload = chunk_result.payload if isinstance(chunk_result.payload, dict) else {}
        candidates.extend(item for item in payload.get("items", []) if isinstance(item, dict))
        chunk_diag = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
        for field in ["candidate_count", "parsed_count", "invalid_line_count", "unsupported_type_count"]:
            diagnostics[field] += int(chunk_diag.get(field, 0))
        diagnostics["invalid_line_samples"].extend(
            str(item) for item in chunk_diag.get("invalid_line_samples", [])[:5]
        )
        diagnostics["invalid_line_samples"] = diagnostics["invalid_line_samples"][:5]

        chunk_dir = chunk_results_dir / chunk.chunk_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        raw_path = chunk_dir / "raw-response.txt"
        markdown_path = chunk_dir / "result.md"
        json_path = chunk_dir / "result.json"
        raw_path.write_text(chunk_result.raw_response, encoding="utf-8")
        markdown_path.write_text(chunk_result.markdown, encoding="utf-8")
        envelope = chunk_result_envelope(
            job=job,
            mode="extract",
            chunk_id=chunk.chunk_id,
            chunk_index=chunk.index,
            chunk_total=chunk.total,
            chunk_input_path=chunk_input_path,
            result=chunk_result,
            run_dir=run_dir,
            markdown_path=markdown_path,
            raw_path=raw_path,
            agent=agent,
            timing=call_timings[-1],
            heading_ancestry=chunk.heading_ancestry,
            overlap=overlap_metadata(chunk),
        )
        write_json(json_path, envelope)
        chunk_records.append(
            {
                "chunk_id": chunk.chunk_id,
                "chars": chunk.chars or len(chunk.text),
                "tokens": chunk.tokens,
                "heading_ancestry": chunk.heading_ancestry,
                "overlap": overlap_metadata(chunk),
                "input": relative_to(chunk_input_path, run_dir),
                "result_json": relative_to(json_path, run_dir),
                "result_md": relative_to(markdown_path, run_dir),
                "status": envelope["status"],
                "warnings": chunk_result.warnings,
            }
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "chunking": planned_chunking,
                    "progress": progress_snapshot(
                        phase="chunk_map",
                        message=f"Completed extract chunk {chunk.index} of {chunk.total}.",
                        chunks=chunk_progress_counts(total=len(chunks), complete=len(chunk_records), running=0),
                    ),
                    "calls": [dict(call) for call in call_timings],
                }
            )

    items, dedupe = dedupe_items(candidates, max_items=int(runtime_extract.get("max_items_per_file", 40)))
    diagnostics["dedupe"] = dedupe
    payload = extract_payload(
        preset=str(runtime_extract.get("preset", DEFAULT_EXTRACT_PRESET)),
        focus=runtime_extract.get("focus"),
        source_files=[job["input_path"]],
        items=items,
        limits={
            "max_items_per_file": int(runtime_extract.get("max_items_per_file", 40)),
            "max_items_per_chunk": int(runtime_extract.get("max_items_per_chunk", 10)),
            "snippet_max_chars": int(runtime_extract.get("snippet_max_chars", DEFAULT_EXTRACT_SNIPPET_MAX_CHARS)),
            "chunk_chars": chunk_chars if chunk_strategy == "character" else None,
            "chunk_tokens": int(chunk_tokens) if chunk_strategy == "token" and chunk_tokens is not None else None,
        },
        diagnostics=diagnostics,
    )
    final_result = FarmModelResult(
        payload=payload,
        markdown=render_extract_markdown(payload),
        raw_response="\n\n".join(f"## {record['chunk_id']}\n{record['result_json']}" for record in chunk_records),
        structured_valid=True,
        warnings=unique_warnings(warnings),
    )
    chunking = {
        "enabled": True,
        "strategy": strategy_name,
        "chunk_count": len(chunks),
        "coverage": "full",
        "chunk_chars": chunk_chars if chunk_strategy == "character" else None,
        "reduce_chars": None,
        "chunk_tokens": int(chunk_tokens) if chunk_strategy == "token" and chunk_tokens is not None else None,
        "reduce_tokens": None,
        "preserve_heading_ancestry": preserve_heading_ancestry,
        "chunk_overlap_chars": chunk_overlap_chars,
        "chunk_overlap_tokens": chunk_overlap_tokens,
        "tokenizer": token_counter.tokenizer_id if token_counter is not None else None,
        "counts_are_estimated": False if token_counter is not None else None,
        "chunks": chunk_records,
    }
    return final_result, chunking, compact_snippet_status({"policy": "off", "requested_count": 0})


def run_file_job(
    *,
    mode: str,
    job: dict[str, Any],
    job_dir: Path,
    run_dir: Path,
    content: str,
    instructions: str | None,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
    runtime_config: dict[str, Any],
    model_processor: ModelProcessor,
    call_timings: list[dict[str, Any]],
    token_counter: ExactTokenCounter | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[FarmModelResult, dict[str, Any], dict[str, Any]]:
    summarize = runtime_config["summarize"]
    extract = runtime_config["extract"]
    mode_config = extract if mode == "extract" else summarize
    chunk_strategy = str(mode_config.get("chunk_strategy", "character"))
    chunk_chars = int(mode_config["chunk_chars"])
    reduce_chars = int(summarize["reduce_chars"])
    chunk_tokens = mode_config.get("chunk_tokens")
    reduce_tokens = summarize.get("reduce_tokens")
    source_tokens = token_counter.count_tokens(content) if chunk_strategy == "token" and token_counter is not None else None
    should_chunk = mode == "summarize" and len(content) > chunk_chars
    if mode == "summarize" and chunk_strategy == "token":
        if token_counter is None or chunk_tokens is None:
            raise ValueError("Token-aware chunking requires an exact token counter and chunk token budget.")
        source_tokens = token_counter.count_tokens(content)
        should_chunk = source_tokens > int(chunk_tokens)
    if mode == "extract":
        should_chunk = len(content) > chunk_chars
        if chunk_strategy == "token":
            if token_counter is None or chunk_tokens is None:
                raise ValueError("Token-aware extract chunking requires an exact token counter and chunk token budget.")
            source_tokens = token_counter.count_tokens(content)
            should_chunk = source_tokens > int(chunk_tokens)

    if should_chunk and mode == "summarize":
        return run_chunked_summary_job(
            job=job,
            job_dir=job_dir,
            run_dir=run_dir,
            content=content,
            instructions=instructions,
            agent=agent,
            ollama_base_url=ollama_base_url,
            timeout=timeout,
            chunk_chars=chunk_chars,
            reduce_chars=reduce_chars,
            chunk_strategy=chunk_strategy,
            chunk_tokens=int(chunk_tokens) if chunk_tokens is not None else None,
            reduce_tokens=int(reduce_tokens) if reduce_tokens is not None else None,
            token_counter=token_counter,
            model_processor=model_processor,
            call_timings=call_timings,
            runtime_summarize=summarize,
            failure_policy=runtime_config["failure_policy"],
            progress_callback=progress_callback,
        )
    if should_chunk and mode == "extract":
        return run_chunked_extract_job(
            job=job,
            job_dir=job_dir,
            run_dir=run_dir,
            content=content,
            agent=agent,
            ollama_base_url=ollama_base_url,
            timeout=timeout,
            chunk_strategy=chunk_strategy,
            token_counter=token_counter,
            model_processor=model_processor,
            call_timings=call_timings,
            runtime_extract=extract,
            failure_policy=runtime_config["failure_policy"],
            progress_callback=progress_callback,
        )
    snippet_request = resolve_snippet_request(
        summarize,
        source_chars=len(content),
        source_tokens=source_tokens,
        chunk_count=1,
    )
    return run_single_pass_job(
        mode=mode,
        file_path=job["input_path"],
        content=content,
        instructions=instructions,
        agent=agent,
        ollama_base_url=ollama_base_url,
        timeout=timeout,
        chunk_chars=chunk_chars,
        chunk_strategy=chunk_strategy,
        chunk_tokens=int(chunk_tokens) if chunk_tokens is not None else None,
        token_counter=token_counter,
        model_processor=model_processor,
        call_timings=call_timings,
        snippet_request=snippet_request,
        extract_config=extract if mode == "extract" else None,
        progress_callback=progress_callback,
    )


def call_timing_summary(call_timings: list[dict[str, Any]]) -> dict[str, Any]:
    duration = None
    if call_timings:
        duration = duration_between(call_timings[0].get("started_at"), call_timings[-1].get("completed_at"))
    return {
        "duration_ms": duration,
        "calls": call_timings,
    }


def extract_failure_summary(job: dict[str, Any]) -> dict[str, Any]:
    failure = job.get("failure") if isinstance(job.get("failure"), dict) else {}
    return {
        "job_id": job.get("job_id"),
        "file": job.get("input_path"),
        "error": job.get("error"),
        "failure": failure,
    }


def build_extract_run_results(run_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
    jobs = [job for job in status.get("jobs", []) if isinstance(job, dict)]
    completed_jobs = [job for job in jobs if job.get("status") in {"complete", "complete_with_warnings"}]
    failed_jobs = [job for job in jobs if job.get("status") == "failed"]
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    for job in completed_jobs:
        result_ref = job.get("result_json")
        if not result_ref:
            continue
        result_path = run_dir / str(result_ref)
        if not result_path.exists():
            warnings.append(f"missing_result_json:{job.get('job_id')}")
            continue
        try:
            result = read_json(result_path)
        except Exception as exc:
            warnings.append(f"malformed_result_json:{job.get('job_id')}:{exc}")
            continue
        payload = result.get("result") if isinstance(result.get("result"), dict) else {}
        items.extend(item for item in payload.get("items", []) if isinstance(item, dict))
        warnings.extend(str(item) for item in result.get("warnings", []) if str(item).strip())

    runtime = status.get("runtime") if isinstance(status.get("runtime"), dict) else {}
    extract = runtime.get("extract") if isinstance(runtime.get("extract"), dict) else {}
    deduped, dedupe = dedupe_items(items, max_items=max(1, int(extract.get("max_items_per_file", 40))) * max(1, len(completed_jobs)))
    coverage_status = "partial" if failed_jobs else "complete"
    if not completed_jobs and failed_jobs:
        coverage_status = "failed"
    result = {
        "schema_version": 1,
        "run_id": status.get("run_id"),
        "mode": "extract",
        "preset": extract.get("preset", DEFAULT_EXTRACT_PRESET),
        "focus": extract.get("focus"),
        "status": status.get("status"),
        "coverage": {
            "status": coverage_status,
            "total_jobs": len(jobs),
            "completed_jobs": len(completed_jobs),
            "failed_jobs": len(failed_jobs),
            "skipped_files": len(status.get("skipped_files") or []),
        },
        "counts": {
            "items": len(deduped),
            "by_type": {},
        },
        "items": deduped,
        "failures": [extract_failure_summary(job) for job in failed_jobs],
        "artifacts": {
            "markdown": "EXTRACT_RESULTS.md",
            "json": "extract-results.json",
        },
        "diagnostics": {
            "warnings": unique_warnings(warnings),
            "dedupe": dedupe,
        },
    }
    from src.sift_farm_extract import count_by_type

    result["counts"]["by_type"] = count_by_type(deduped)
    return result


def render_extract_run_markdown(result: dict[str, Any]) -> str:
    coverage = result.get("coverage") if isinstance(result.get("coverage"), dict) else {}
    lines = [
        f"# Extract Run {result.get('run_id', '')}",
        "",
        f"Status: `{result.get('status', '')}`",
        f"Preset: `{result.get('preset', '')}`",
        f"Coverage: `{coverage.get('status', '')}`",
        f"Items: `{(result.get('counts') or {}).get('items', 0)}`",
    ]
    if result.get("focus"):
        lines.append(f"Focus: {result.get('focus')}")
    lines.extend(["", "## Items", ""])
    items = [item for item in result.get("items", []) if isinstance(item, dict)]
    if not items:
        lines.append("No extract items found.")
    for item in items:
        lines.append(f"- `{item.get('type', '')}` {item.get('text', '')}")
        sources = [source for source in item.get("sources", []) if isinstance(source, dict)]
        if sources:
            source = sources[0]
            location = source.get("file") or ""
            if source.get("char_start") is not None and source.get("char_end") is not None:
                location = f"{location}@{source.get('char_start')}-{source.get('char_end')}"
            lines.append(f"  - Source: `{location}`")
    failures = [item for item in result.get("failures", []) if isinstance(item, dict)]
    if failures:
        lines.extend(["", "## Failures", ""])
        for failure in failures:
            detail = failure.get("failure") if isinstance(failure.get("failure"), dict) else {}
            lines.append(
                f"- `{failure.get('file', '')}`: {detail.get('code', 'unknown')} - "
                f"{detail.get('recommended_action') or failure.get('error') or ''}"
            )
    lines.append("")
    return "\n".join(lines)


def write_extract_run_results(run_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
    result = build_extract_run_results(run_dir, status)
    write_json(run_dir / "extract-results.json", result)
    (run_dir / "EXTRACT_RESULTS.md").write_text(render_extract_run_markdown(result), encoding="utf-8")
    status.setdefault("artifacts", {})["extract_results_json"] = "extract-results.json"
    status.setdefault("artifacts", {})["extract_results_md"] = "EXTRACT_RESULTS.md"
    return result


def execute_job(
    *,
    mode: str,
    job: dict[str, Any],
    item: Any,
    job_dir: Path,
    run_dir: Path,
    instructions: str | None,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
    runtime_config: dict[str, Any],
    max_attempts: int,
    model_processor: ModelProcessor,
    token_counter: ExactTokenCounter | None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    last_error: str | None = None
    call_timings: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        try:
            content = item.path.read_text(encoding="utf-8", errors="replace")
            if not content.strip():
                raise ValueError("Input file contains no usable text.")
            result, chunking, snippets = run_file_job(
                mode=mode,
                job=job,
                job_dir=job_dir,
                run_dir=run_dir,
                content=content,
                instructions=instructions,
                agent=agent,
                ollama_base_url=ollama_base_url,
                timeout=timeout,
                runtime_config=runtime_config,
                model_processor=model_processor,
                call_timings=call_timings,
                token_counter=token_counter,
                progress_callback=progress_callback,
            )

            envelope = write_result_files(
                result=result,
                job_dir=job_dir,
                job=job,
                mode=mode,
                run_dir=run_dir,
                agent=agent,
                chunking=chunking,
                snippets=snippets,
                timing=call_timing_summary(call_timings),
            )
            return {
                "status": envelope["status"],
                "result_json": f"jobs/{job['job_id']}/result.json",
                "result_md": f"jobs/{job['job_id']}/result.md",
                "raw_response": f"jobs/{job['job_id']}/raw-response.txt",
                "warnings": result.warnings,
                "chunking": compact_chunking(chunking),
                "snippets": snippets,
                "error": None,
                "timing": {
                    "calls": call_timings,
                },
            }
        except Exception as exc:
            last_error = str(exc)
            if attempt < max_attempts:
                continue
            failure = classify_failure(exc)
            (job_dir / "log.md").write_text(f"# Failure\n\n{last_error}\n", encoding="utf-8")
            failure_chunking = job.get("chunking", single_pass_chunking())
            failure_snippets = job.get("snippets", compact_snippet_status({"policy": "off", "requested_count": 0}))
            failure_envelope = write_failure_result_files(
                job=job,
                mode=mode,
                run_dir=run_dir,
                job_dir=job_dir,
                agent=agent,
                failure=failure,
                chunking=failure_chunking,
                snippets=failure_snippets,
                timing=call_timing_summary(call_timings),
            )
            return {
                "status": "failed",
                "result_json": f"jobs/{job['job_id']}/result.json",
                "result_md": f"jobs/{job['job_id']}/result.md",
                "raw_response": f"jobs/{job['job_id']}/raw-response.txt",
                "warnings": [],
                "chunking": failure_envelope["chunking"],
                "snippets": failure_envelope["snippets"],
                "error": last_error,
                "failure": failure,
                "timing": {
                    "calls": call_timings,
                },
            }

    raise RuntimeError("Job execution ended without a result.")


def apply_job_update(job: dict[str, Any], update: dict[str, Any]) -> None:
    for key in ["status", "result_json", "result_md", "raw_response", "warnings", "chunking", "snippets", "error"]:
        job[key] = update[key]
    if "failure" in update:
        job["failure"] = update["failure"]
    else:
        job.pop("failure", None)
    job.setdefault("timing", {})["calls"] = update.get("timing", {}).get("calls", [])
    job["progress"] = terminal_progress(job)


def run_scheduled_jobs(
    *,
    jobs: list[dict[str, Any]],
    items: list[Any],
    jobs_dir: Path,
    run_dir: Path,
    status: dict[str, Any],
    skipped_count: int,
    mode: str,
    instructions: str | None,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
    runtime_config: dict[str, Any],
    max_attempts: int,
    model_processor: ModelProcessor,
    token_counter: ExactTokenCounter | None,
) -> None:
    max_workers = max(1, int(runtime_config["concurrency"]["jobs"]))
    queued = list(zip(jobs, items))
    in_flight: dict[Future[dict[str, Any]], dict[str, Any]] = {}
    status_lock = Lock()

    def make_progress_callback(job: dict[str, Any]) -> ProgressCallback:
        def progress_callback(update: dict[str, Any]) -> None:
            with status_lock:
                if "calls" in update:
                    job.setdefault("timing", {})["calls"] = deepcopy(update["calls"])
                if "chunking" in update:
                    job["chunking"] = deepcopy(update["chunking"])
                progress = deepcopy(update["progress"]) if isinstance(update.get("progress"), dict) else {}
                if progress:
                    current_call = update.get("current_call")
                    if current_call is not None:
                        progress["current_call"] = deepcopy(current_call)
                    job["progress"] = progress
                status["counts"] = count_jobs(jobs, skipped=skipped_count)
                write_status(run_dir, status)

        return progress_callback

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while queued or in_flight:
            while queued and len(in_flight) < max_workers:
                job, item = queued.pop(0)
                started_at = timestamp_now()
                timing = job.setdefault("timing", {})
                timing["started_at"] = started_at
                timing["queue_wait_ms"] = duration_between(timing.get("queued_at"), started_at)
                job["status"] = "running"
                job["progress"] = progress_snapshot(
                    phase="starting",
                    message="Starting job.",
                )
                with status_lock:
                    status["counts"] = count_jobs(jobs, skipped=skipped_count)
                    write_status(run_dir, status)
                future = executor.submit(
                    execute_job,
                    mode=mode,
                    job=job,
                    item=item,
                    job_dir=jobs_dir / job["job_id"],
                    run_dir=run_dir,
                    instructions=instructions,
                    agent=agent,
                    ollama_base_url=ollama_base_url,
                    timeout=timeout,
                    runtime_config=runtime_config,
                    max_attempts=max_attempts,
                    model_processor=model_processor,
                    token_counter=token_counter,
                    progress_callback=make_progress_callback(job),
                )
                in_flight[future] = job

            done, _pending = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                job = in_flight.pop(future)
                with status_lock:
                    apply_job_update(job, future.result())
                    completed_at = timestamp_now()
                    timing = job.setdefault("timing", {})
                    timing["completed_at"] = completed_at
                    timing["duration_ms"] = duration_between(timing.get("started_at"), completed_at)
                    status["counts"] = count_jobs(jobs, skipped=skipped_count)
                    write_status(run_dir, status)


def resolve_run_agent_and_config(
    *,
    root: Path,
    agent_id: str,
    default_model: str,
    config_path: Path | None = None,
    profile: str | None = None,
    resource_mode: str | None = None,
    model: str | None = None,
    chunk_chars: int | None = None,
    reduce_chars: int | None = None,
    chunk_strategy: str | None = None,
    chunk_tokens: int | None = None,
    reduce_tokens: int | None = None,
    token_safety_margin: float | None = None,
    preserve_heading_ancestry: bool | None = None,
    chunk_overlap_chars: int | None = None,
    chunk_overlap_tokens: int | None = None,
    snippets: str | None = None,
    snippet_max_chars: int | None = None,
    extract_preset: str | None = None,
    extract_focus: str | None = None,
    extract_max_items_per_file: int | None = None,
    extract_max_items_per_chunk: int | None = None,
    extract_snippet_max_chars: int | None = None,
    parallel_jobs: int | None = None,
    parallel_chunks: int | None = None,
    max_attempts: int | None = None,
    per_file_timeout_seconds: int | None = None,
    chunk_max_attempts: int | None = None,
    reduce_max_attempts: int | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_config = resolve_runtime_config(
        root=root,
        default_model=default_model,
        config_path=config_path,
        overrides=RuntimeOverrides(
            profile=profile,
            resource_mode=resource_mode,
            model=model,
            chunk_strategy=chunk_strategy,
            chunk_chars=chunk_chars,
            reduce_chars=reduce_chars,
            chunk_tokens=chunk_tokens,
            reduce_tokens=reduce_tokens,
            token_safety_margin=token_safety_margin,
            preserve_heading_ancestry=preserve_heading_ancestry,
            chunk_overlap_chars=chunk_overlap_chars,
            chunk_overlap_tokens=chunk_overlap_tokens,
            snippets=snippets,
            snippet_max_chars=snippet_max_chars,
            extract_preset=extract_preset,
            extract_focus=extract_focus,
            extract_max_items_per_file=extract_max_items_per_file,
            extract_max_items_per_chunk=extract_max_items_per_chunk,
            extract_snippet_max_chars=extract_snippet_max_chars,
            parallel_jobs=parallel_jobs,
            parallel_chunks=parallel_chunks,
            max_attempts=max_attempts,
            per_file_timeout_seconds=per_file_timeout_seconds,
            chunk_max_attempts=chunk_max_attempts,
            reduce_max_attempts=reduce_max_attempts,
            include=tuple(include or ()),
            exclude=tuple(exclude or ()),
        ),
    )
    agent = load_agent(root, agent_id, str(runtime_config["model"]))
    if model_is_explicit(runtime_config):
        agent["model"] = runtime_config["model"]
        apply_model_metadata(agent)
    runtime_config = set_effective_model(runtime_config, str(agent["model"]))
    runtime_config = finalize_runtime_config_for_agent(runtime_config, agent)
    return agent, runtime_config


def _source_input_folder(root: Path, source_status: dict[str, Any]) -> Path:
    input_record = source_status.get("input") if isinstance(source_status.get("input"), dict) else {}
    raw_path = str(input_record.get("path") or "")
    if not raw_path:
        raise ValueError("Source run status is missing input.path.")
    input_folder = Path(raw_path)
    if not input_folder.is_absolute():
        input_folder = root / input_folder
    return input_folder


def _load_source_runtime_config(source_run_dir: Path) -> dict[str, Any] | None:
    config_path = source_run_dir / "farm-config.resolved.json"
    if not config_path.exists():
        return None
    return read_json(config_path)


def _request_instructions(source_status: dict[str, Any]) -> tuple[bool, str | None]:
    request = source_status.get("request") if isinstance(source_status.get("request"), dict) else {}
    if "instructions" not in request:
        return False, None
    value = request.get("instructions")
    return True, str(value) if value is not None else None


def failure_counts_for_jobs(jobs: list[dict[str, Any]]) -> dict[str, int]:
    retryable = 0
    non_retryable = 0
    unknown = 0
    for job in jobs:
        failure = job.get("failure") if isinstance(job.get("failure"), dict) else None
        if failure is None or "retryable" not in failure:
            unknown += 1
        elif failure.get("retryable"):
            retryable += 1
        else:
            non_retryable += 1
    return {
        "retryable": retryable,
        "non_retryable": non_retryable,
        "unknown": unknown,
    }


def build_retry_failed_plan(
    *,
    root: Path,
    source_run_dir: Path,
    default_model: str,
    instructions: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    source_status = load_run_status(source_run_dir)
    failed_jobs = [job for job in source_status.get("jobs", []) if isinstance(job, dict) and job.get("status") == "failed"]
    if not failed_jobs:
        raise ValueError(f"Source run has no failed jobs: {source_status.get('run_id', source_run_dir.name)}")

    input_folder = _source_input_folder(root, source_status)
    missing: list[str] = []
    selected_files: list[DiscoveredFile] = []
    retry_jobs: list[dict[str, Any]] = []

    for index, job in enumerate(failed_jobs, start=1):
        relative_path = str(job.get("input_path") or "")
        if not relative_path:
            missing.append(f"{job.get('job_id', f'job-{index:04d}')} missing input_path")
            continue
        source_path = input_folder / Path(relative_path)
        if not source_path.is_file():
            missing.append(relative_path)
            continue
        retry_job_id = job_id_for(index)
        selected_files.append(DiscoveredFile(path=source_path, relative_path=relative_path))
        retry_jobs.append(
            {
                "source_job_id": str(job.get("job_id") or ""),
                "retry_job_id": retry_job_id,
                "input_path": relative_path,
                "source_error": job.get("error"),
                "source_failure": deepcopy(job.get("failure")) if isinstance(job.get("failure"), dict) else None,
            }
        )

    if missing:
        raise FileNotFoundError(
            "Cannot retry failed jobs because source files are missing: " + ", ".join(missing)
        )

    source_mode = str(source_status.get("mode") or "summarize")
    has_prior_instructions, prior_instructions = _request_instructions(source_status)
    effective_instructions = instructions if instructions is not None else prior_instructions
    warnings: list[str] = []
    if instructions is None and not has_prior_instructions:
        warnings.append("Source run does not contain request.instructions; retrying without prior instructions.")
    if source_mode == "prompt" and not effective_instructions:
        raise ValueError("Cannot retry a prompt-mode run without instructions. Pass --instructions.")
    selected_failure_counts = failure_counts_for_jobs(failed_jobs)
    if selected_failure_counts["non_retryable"]:
        warnings.append(
            "Selected failed jobs include "
            f"{selected_failure_counts['non_retryable']} known non-retryable failure(s); "
            "retry may repeat until the recommended fix is applied."
        )

    request = source_status.get("request") if isinstance(source_status.get("request"), dict) else {}
    effective_agent_id = agent_id or str(request.get("agent") or source_status.get("agent") or "default")
    runtime_config = _load_source_runtime_config(source_run_dir)
    if runtime_config is not None:
        runtime_config = deepcopy(runtime_config)
        agent = load_agent(root, effective_agent_id, str(runtime_config.get("model") or default_model))
        if model_is_explicit(runtime_config):
            agent["model"] = runtime_config["model"]
        runtime_config = set_effective_model(runtime_config, str(agent["model"]))
        runtime_config = finalize_runtime_config_for_agent(runtime_config, agent)
    else:
        agent, runtime_config = resolve_run_agent_and_config(
            root=root,
            agent_id=effective_agent_id,
            default_model=default_model,
        )
        warnings.append("Source run is missing farm-config.resolved.json; retrying with current defaults.")

    source_run_id = str(source_status.get("run_id") or source_run_dir.name)
    retry = {
        "source_run_id": source_run_id,
        "source_run_path": relative_to(source_run_dir, root),
        "selected_statuses": ["failed"],
        "source_failed_count": len(failed_jobs),
        "retried_count": len(selected_files),
        "failure_counts": selected_failure_counts,
        "jobs": retry_jobs,
        "warnings": warnings,
    }

    return {
        "source_run_dir": source_run_dir,
        "source_status": source_status,
        "input_folder": input_folder,
        "discovery": DiscoveryResult(files=selected_files, skipped=[]),
        "mode": source_mode,
        "instructions": effective_instructions,
        "agent_id": effective_agent_id,
        "agent": agent,
        "model": agent["model"],
        "runtime_config": runtime_config,
        "retry": retry,
        "warnings": warnings,
    }


def retry_failed_result(status: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    retry = status.get("retry") if isinstance(status.get("retry"), dict) else {}
    return {
        "schema_version": 1,
        "status": status.get("status"),
        "source_run": {
            "run_id": retry.get("source_run_id"),
            "path": retry.get("source_run_path"),
            "failed_jobs": retry.get("source_failed_count", 0),
        },
        "retry_run": {
            "run_id": status.get("run_id"),
            "path": (status.get("output") or {}).get("path") if isinstance(status.get("output"), dict) else None,
            "retried_jobs": retry.get("retried_count", 0),
        },
        "failure_counts": retry.get("failure_counts", {"retryable": 0, "non_retryable": 0, "unknown": 0}),
        "selected_jobs": retry.get("jobs", []),
        "counts": status.get("counts", {}),
        "warnings": plan.get("warnings", []),
        "errors": [],
    }


def retry_failed_error_result(*, run_ref: str, error: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "error",
        "source_run": {
            "run_ref": run_ref,
            "run_id": None,
            "path": None,
            "failed_jobs": 0,
        },
        "retry_run": {
            "run_id": None,
            "path": None,
            "retried_jobs": 0,
        },
        "failure_counts": {"retryable": 0, "non_retryable": 0, "unknown": 0},
        "selected_jobs": [],
        "counts": {},
        "warnings": [],
        "errors": [error],
    }


def run_retry_failed_plan(
    *,
    root: Path,
    plan: dict[str, Any],
    output_dir: Path | None,
    default_model: str,
    ollama_base_url: str,
    model_processor: ModelProcessor = default_model_processor,
    token_counter: ExactTokenCounter | None = None,
    token_counter_loader: TokenCounterLoader = load_exact_token_counter,
) -> tuple[dict[str, Any], dict[str, Any]]:
    status = run_farm(
        root=root,
        input_folder=plan["input_folder"],
        output_dir=output_dir,
        mode=str(plan["mode"]),
        instructions=plan.get("instructions"),
        agent_id=str(plan["agent_id"]),
        default_model=default_model,
        ollama_base_url=ollama_base_url,
        runtime_config=deepcopy(plan["runtime_config"]),
        model_processor=model_processor,
        token_counter=token_counter,
        token_counter_loader=token_counter_loader,
        discovery=plan["discovery"],
        retry=deepcopy(plan["retry"]),
    )
    return status, retry_failed_result(status, plan)


def run_retry_failed(
    *,
    root: Path,
    source_run_dir: Path,
    output_dir: Path | None,
    default_model: str,
    ollama_base_url: str,
    instructions: str | None = None,
    agent_id: str | None = None,
    model_processor: ModelProcessor = default_model_processor,
    token_counter: ExactTokenCounter | None = None,
    token_counter_loader: TokenCounterLoader = load_exact_token_counter,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = build_retry_failed_plan(
        root=root,
        source_run_dir=source_run_dir,
        default_model=default_model,
        instructions=instructions,
        agent_id=agent_id,
    )
    return run_retry_failed_plan(
        root=root,
        plan=plan,
        output_dir=output_dir,
        default_model=default_model,
        ollama_base_url=ollama_base_url,
        model_processor=model_processor,
        token_counter=token_counter,
        token_counter_loader=token_counter_loader,
    )


def run_farm(
    *,
    root: Path,
    input_folder: Path,
    output_dir: Path | None,
    mode: str,
    instructions: str | None,
    agent_id: str,
    default_model: str,
    ollama_base_url: str,
    config_path: Path | None = None,
    profile: str | None = None,
    resource_mode: str | None = None,
    model: str | None = None,
    chunk_chars: int | None = None,
    reduce_chars: int | None = None,
    chunk_strategy: str | None = None,
    chunk_tokens: int | None = None,
    reduce_tokens: int | None = None,
    token_safety_margin: float | None = None,
    preserve_heading_ancestry: bool | None = None,
    chunk_overlap_chars: int | None = None,
    chunk_overlap_tokens: int | None = None,
    snippets: str | None = None,
    snippet_max_chars: int | None = None,
    extract_preset: str | None = None,
    extract_focus: str | None = None,
    extract_max_items_per_file: int | None = None,
    extract_max_items_per_chunk: int | None = None,
    extract_snippet_max_chars: int | None = None,
    parallel_jobs: int | None = None,
    parallel_chunks: int | None = None,
    runtime_config: dict[str, Any] | None = None,
    max_attempts: int | None = None,
    per_file_timeout_seconds: int | None = None,
    chunk_max_attempts: int | None = None,
    reduce_max_attempts: int | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    model_processor: ModelProcessor = default_model_processor,
    token_counter: ExactTokenCounter | None = None,
    token_counter_loader: TokenCounterLoader = load_exact_token_counter,
    discovery: DiscoveryResult | None = None,
    retry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported farm mode: {mode}")
    if mode == "prompt" and not instructions:
        raise ValueError("prompt mode requires --instructions.")
    if mode == "extract" and instructions:
        raise ValueError("extract mode uses --extract-focus for brief steering; do not pass --instructions.")

    if runtime_config is None:
        agent, runtime_config = resolve_run_agent_and_config(
            root=root,
            agent_id=agent_id,
            default_model=default_model,
            config_path=config_path,
            profile=profile,
            resource_mode=resource_mode,
            model=model,
            chunk_strategy=chunk_strategy,
            chunk_chars=chunk_chars,
            reduce_chars=reduce_chars,
            chunk_tokens=chunk_tokens,
            reduce_tokens=reduce_tokens,
            token_safety_margin=token_safety_margin,
            preserve_heading_ancestry=preserve_heading_ancestry,
            chunk_overlap_chars=chunk_overlap_chars,
            chunk_overlap_tokens=chunk_overlap_tokens,
            snippets=snippets,
            snippet_max_chars=snippet_max_chars,
            extract_preset=extract_preset,
            extract_focus=extract_focus,
            extract_max_items_per_file=extract_max_items_per_file,
            extract_max_items_per_chunk=extract_max_items_per_chunk,
            extract_snippet_max_chars=extract_snippet_max_chars,
            parallel_jobs=parallel_jobs,
            parallel_chunks=parallel_chunks,
            max_attempts=max_attempts,
            per_file_timeout_seconds=per_file_timeout_seconds,
            chunk_max_attempts=chunk_max_attempts,
            reduce_max_attempts=reduce_max_attempts,
            include=include,
            exclude=exclude,
        )
    else:
        agent = load_agent(root, agent_id, str(runtime_config["model"]))
        if model_is_explicit(runtime_config):
            agent["model"] = runtime_config["model"]
            apply_model_metadata(agent)
        runtime_config = set_effective_model(runtime_config, str(agent["model"]))
        runtime_config = finalize_runtime_config_for_agent(runtime_config, agent)

    runtime_config.setdefault("failure_policy", default_failure_policy())
    runtime_config.setdefault("discovery", default_discovery())
    runtime_config.setdefault("extract", {})
    if preserve_heading_ancestry is not None:
        runtime_config["summarize"]["preserve_heading_ancestry"] = preserve_heading_ancestry
        if mode == "extract":
            runtime_config["extract"]["preserve_heading_ancestry"] = preserve_heading_ancestry
    if chunk_overlap_chars is not None:
        runtime_config["summarize"]["chunk_overlap_chars"] = chunk_overlap_chars
        if mode == "extract":
            runtime_config["extract"]["chunk_overlap_chars"] = chunk_overlap_chars
    if chunk_overlap_tokens is not None:
        runtime_config["summarize"]["chunk_overlap_tokens"] = chunk_overlap_tokens
        if mode == "extract":
            runtime_config["extract"]["chunk_overlap_tokens"] = chunk_overlap_tokens
    if mode == "extract":
        if chunk_strategy is not None:
            runtime_config["extract"]["chunk_strategy"] = chunk_strategy
        if chunk_chars is not None:
            runtime_config["extract"]["chunk_chars"] = chunk_chars
        if chunk_tokens is not None:
            runtime_config["extract"]["chunk_tokens"] = chunk_tokens
        if token_safety_margin is not None:
            runtime_config["extract"]["token_safety_margin"] = token_safety_margin
        if extract_preset is not None:
            runtime_config["extract"]["preset"] = extract_preset
        if extract_focus is not None:
            runtime_config["extract"]["focus"] = extract_focus
        if extract_max_items_per_file is not None:
            runtime_config["extract"]["max_items_per_file"] = extract_max_items_per_file
        if extract_max_items_per_chunk is not None:
            runtime_config["extract"]["max_items_per_chunk"] = extract_max_items_per_chunk
        if extract_snippet_max_chars is not None:
            runtime_config["extract"]["snippet_max_chars"] = extract_snippet_max_chars
    if max_attempts is not None:
        runtime_config["failure_policy"]["max_attempts"] = max_attempts
    if per_file_timeout_seconds is not None:
        runtime_config["failure_policy"]["per_file_timeout_seconds"] = per_file_timeout_seconds
    if chunk_max_attempts is not None:
        runtime_config["failure_policy"]["chunk_max_attempts"] = chunk_max_attempts
    if reduce_max_attempts is not None:
        runtime_config["failure_policy"]["reduce_max_attempts"] = reduce_max_attempts
    validate_resolved_config(runtime_config)

    token_needed = runtime_config["summarize"].get("chunk_strategy") == "token"
    if mode == "extract":
        token_needed = runtime_config["extract"].get("chunk_strategy") == "token"
    if token_needed and token_counter is None:
        token_counter = token_counter_loader(
            root=root,
            model=str(agent["model"]),
            model_metadata=agent.get("model_metadata"),
            local_files_only=True,
        )

    farm_root = farm_home(root)
    discovery_config = runtime_config.get("discovery") if isinstance(runtime_config.get("discovery"), dict) else {}
    discovery = discovery or discover_text_files(
        input_folder,
        include=discovery_config.get("include", []),
        exclude=discovery_config.get("exclude", []),
    )
    discovery_metadata = {
        "include": list(discovery_config.get("include", [])),
        "exclude": list(discovery_config.get("exclude", [])),
        "counts": {
            "selected": len(discovery.files),
            "skipped": len(discovery.skipped),
        },
        "skipped": list(discovery.skipped_details or []),
    }
    run_id, run_dir = create_run_dir(farm_root, output_dir)
    remember_run(root, run_id, run_dir)
    write_json(run_dir / "farm-config.resolved.json", runtime_config)
    jobs_dir = run_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[dict[str, Any]] = []
    for index, item in enumerate(discovery.files, start=1):
        job_id = job_id_for(index)
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        input_record = {
            "path": item.relative_path,
            "absolute_path": str(item.path),
        }
        write_json(job_dir / "input.json", input_record)
        jobs.append(
            {
                "job_id": job_id,
                "status": "queued",
                "input_path": item.relative_path,
                "result_json": None,
                "result_md": None,
                "raw_response": None,
                "error": None,
                "warnings": [],
                "chunking": single_pass_chunking(),
                "snippets": compact_snippet_status({"policy": "off", "requested_count": 0}),
                "timing": {
                    "queued_at": timestamp_now(),
                    "started_at": None,
                    "completed_at": None,
                    "queue_wait_ms": None,
                    "duration_ms": None,
                    "calls": [],
                },
            }
        )

    status = make_initial_status(
        run_id=run_id,
        run_dir=run_dir,
        mode=mode,
        agent=agent,
        instructions=instructions,
        extract_preset=str(runtime_config.get("extract", {}).get("preset", DEFAULT_EXTRACT_PRESET)) if mode == "extract" else None,
        extract_focus=runtime_config.get("extract", {}).get("focus") if mode == "extract" else None,
        input_folder=input_folder,
        jobs=jobs,
        skipped_files=discovery.skipped,
        discovery_metadata=discovery_metadata,
        runtime_config=runtime_config,
        retry=retry,
    )
    write_status(run_dir, status)

    run_scheduled_jobs(
        jobs=jobs,
        items=discovery.files,
        jobs_dir=jobs_dir,
        run_dir=run_dir,
        status=status,
        skipped_count=len(discovery.skipped),
        mode=mode,
        instructions=instructions,
        agent=agent,
        ollama_base_url=ollama_base_url,
        timeout=int(runtime_config["failure_policy"]["per_file_timeout_seconds"]),
        runtime_config=runtime_config,
        max_attempts=int(runtime_config["failure_policy"]["max_attempts"]),
        model_processor=model_processor,
        token_counter=token_counter,
    )

    status["status"] = final_run_status(jobs)
    status["counts"] = count_jobs(jobs, skipped=len(discovery.skipped))
    completed_at = timestamp_now()
    status["timing"]["completed_at"] = completed_at
    status["timing"]["duration_ms"] = duration_between(status["timing"].get("started_at"), completed_at)
    if mode == "extract":
        write_extract_run_results(run_dir, status)
    write_status(run_dir, status)
    write_timing_summary(run_dir, status)
    return status


def find_run_dirs(root: Path) -> list[Path]:
    home = farm_home(root)
    seen: set[Path] = set()
    run_dirs: list[Path] = []

    for entry in read_run_index(root):
        run_dir = Path(entry["path"])
        if run_dir not in seen and run_dir.is_dir() and run_status_path(run_dir).exists():
            seen.add(run_dir)
            run_dirs.append(run_dir)

    if not home.exists():
        return sorted(run_dirs, reverse=True)

    for path in home.iterdir():
        if path in seen or not path.is_dir() or not run_status_path(path).exists():
            continue
        seen.add(path)
        run_dirs.append(path)

    return sorted(run_dirs, reverse=True)


def load_runs(root: Path) -> list[dict[str, Any]]:
    runs = []
    for run_dir in find_run_dirs(root):
        try:
            runs.append(load_run_status(run_dir))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(runs, key=lambda run: str(run.get("updated_at", "")), reverse=True)


def find_run_dir(root: Path, run_id: str) -> Path:
    for run_dir in find_run_dirs(root):
        if run_dir.name == run_id:
            return run_dir
    raise FileNotFoundError(f"Unknown farm run: {run_id}")


def validate_run_dir(run_dir: Path, *, run_ref: str | None = None) -> Path:
    label = f" for {run_ref}" if run_ref else ""
    if run_dir.exists() and not run_dir.is_dir():
        raise FileNotFoundError(f"Farm run reference{label} is not a directory: {run_dir}")
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Farm run directory{label} does not exist: {run_dir}")
    if not run_status_path(run_dir).exists():
        raise FileNotFoundError(f"Farm run directory{label} is missing farm-status.json: {run_dir}")
    return run_dir


def resolve_run_reference(root: Path, run_ref: str) -> Path:
    candidate = Path(run_ref)
    if candidate.exists():
        return validate_run_dir(candidate)

    for entry in read_run_index(root):
        if entry.get("run_id") == run_ref:
            return validate_run_dir(Path(entry["path"]), run_ref=run_ref)

    try:
        return find_run_dir(root, run_ref)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Unknown farm run reference: {run_ref}. Run `python sift.py farm list` to see known runs, "
            "or pass a full run directory path."
        ) from exc


def list_runs_text(root: Path) -> str:
    return render_run_list(load_runs(root))


def status_text(root: Path, run_id: str | None = None) -> str:
    if run_id:
        return render_status_markdown(load_run_status(find_run_dir(root, run_id)))
    return render_farm_overview(load_runs(root))


def status_json(root: Path, run_id: str | None = None) -> dict[str, Any]:
    if run_id:
        return run_status_json(load_run_status(find_run_dir(root, run_id)))
    return farm_overview_json(load_runs(root))
