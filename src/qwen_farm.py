from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import json
from pathlib import Path
from typing import Any, Callable

from src.qwen_farm_chunks import (
    CHUNK_STRATEGY,
    TOKEN_CHUNK_STRATEGY,
    TextChunk,
    chunk_text,
    chunk_text_by_tokens,
    render_chunk_input,
    render_reduce_input,
)
from src.qwen_farm_files import (
    FARM_SCHEMA_VERSION,
    create_run_dir,
    discover_text_files,
    farm_home,
    job_id_for,
    relative_to,
    utc_timestamp,
)
from src.qwen_farm_model import (
    SUMMARY_MAX_INPUT_CHARS,
    SUMMARY_NUM_BATCH,
    SUMMARY_NUM_PREDICT,
    FarmModelResult,
    OllamaChatClient,
    process_file_with_model,
    render_summary_markdown,
)
from src.qwen_farm_profiles import (
    RuntimeOverrides,
    compact_runtime_config,
    finalize_runtime_config_for_agent,
    model_is_explicit,
    resolve_runtime_config,
    set_effective_model,
)
from src.qwen_farm_status import (
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
from src.qwen_farm_snippets import (
    DEFAULT_CHUNK_CANDIDATE_SNIPPETS,
    apply_snippet_warning_policy,
    compact_snippet_status,
    empty_snippet_diagnostics,
    resolve_snippet_request,
    reselect_snippets,
)
from src.qwen_farm_timing import duration_between, finish_timing, timestamp_now, utc_now, write_timing_summary
from src.qwen_farm_tokenizer import ExactTokenCounter, load_exact_token_counter


DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_PER_FILE_TIMEOUT_SECONDS = 600
SUPPORTED_MODES = {"summarize", "prompt"}

ModelProcessor = Callable[..., FarmModelResult]
TokenCounterLoader = Callable[..., ExactTokenCounter]


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
    return agent


def make_initial_status(
    *,
    run_id: str,
    run_dir: Path,
    mode: str,
    agent: dict[str, Any],
    input_folder: Path,
    jobs: list[dict[str, Any]],
    skipped_files: list[str],
    runtime_config: dict[str, Any],
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
        "created_at": created_at,
        "updated_at": created_at,
        "timing": {
            "created_at": timing_created_at,
            "started_at": timing_created_at,
            "completed_at": None,
            "duration_ms": None,
        },
    }
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


def chunk_result_envelope(
    *,
    job: dict[str, Any],
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
) -> dict[str, Any]:
    envelope = {
        "schema_version": FARM_SCHEMA_VERSION,
        "job_id": job["job_id"],
        "chunk_id": chunk_id,
        "mode": "summarize",
        "status": result_status(result),
        "structured_valid": result.structured_valid,
        "input": {
            "source_path": job["input_path"],
            "chunk_path": relative_to(chunk_input_path, run_dir),
            "chunk_index": chunk_index,
            "chunk_total": chunk_total,
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
) -> FarmModelResult:
    options = dict(agent.get("options", {}))
    if mode == "summarize":
        requested_snippets = int((snippet_request or {}).get("requested_count", 0))
        options.setdefault("num_predict", SUMMARY_NUM_PREDICT + min(512, requested_snippets * 128))
        options.setdefault("num_batch", SUMMARY_NUM_BATCH)
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
    chunk_id: str | None = None,
    reduce_generation: int | None = None,
    reduce_batch_index: int | None = None,
) -> FarmModelResult:
    started = utc_now()
    record: dict[str, Any] = {
        "kind": kind,
        "file_path": file_path,
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
    }
    if chunk_id is not None:
        record["chunk_id"] = chunk_id
    if reduce_generation is not None:
        record["reduce_generation"] = reduce_generation
    if reduce_batch_index is not None:
        record["reduce_batch_index"] = reduce_batch_index

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
        )
    except Exception as exc:
        record.update(finish_timing(started))
        record["status"] = "failed"
        record["error"] = str(exc)
        call_timings.append(record)
        raise

    record.update(finish_timing(started))
    record["status"] = result_status(result)
    if result.warnings:
        record["warnings"] = result.warnings
    call_timings.append(record)
    return result


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
            result = timed_model_call(
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
            result = timed_model_call(
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
) -> tuple[FarmModelResult, dict[str, Any], dict[str, Any]]:
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
) -> tuple[FarmModelResult, dict[str, Any], dict[str, Any]]:
    if chunk_strategy == "token":
        if token_counter is None or chunk_tokens is None:
            raise ValueError("Token-aware chunking requires an exact token counter and chunk token budget.")
        chunks = chunk_text_by_tokens(
            content,
            max_input_tokens=chunk_tokens,
            token_counter=token_counter,
            source_path=job["input_path"],
        )
        strategy_name = TOKEN_CHUNK_STRATEGY
    else:
        chunks = chunk_text(content, max_chars=chunk_body_budget(job["input_path"], chunk_chars))
        strategy_name = CHUNK_STRATEGY
    chunks_dir = job_dir / "chunks"
    chunk_results_dir = job_dir / "chunk-results"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_results_dir.mkdir(parents=True, exist_ok=True)

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

        chunk_result = timed_model_call(
            call_timings=call_timings,
            kind="chunk_map",
            mode="summarize",
            file_path=f"{job['input_path']}#{chunk.chunk_id}",
            content=chunk_input,
            instructions=instructions,
            agent=agent,
            ollama_base_url=ollama_base_url,
            timeout=timeout,
            summary_max_input_chars=len(chunk_input) if chunk_strategy == "token" else chunk_chars,
            model_processor=model_processor,
            snippet_request=chunk_snippet_request,
            chunk_id=chunk.chunk_id,
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
        )
        write_json(json_path, envelope)
        chunk_payloads.append(chunk_result.payload)
        chunk_records.append(
            {
                "chunk_id": chunk.chunk_id,
                "chars": chunk.chars or len(chunk.text),
                "tokens": chunk.tokens,
                "input": relative_to(chunk_input_path, run_dir),
                "result_json": relative_to(json_path, run_dir),
                "result_md": relative_to(markdown_path, run_dir),
                "status": envelope["status"],
                "warnings": chunk_result.warnings,
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
) -> tuple[FarmModelResult, dict[str, Any], dict[str, Any]]:
    summarize = runtime_config["summarize"]
    chunk_strategy = str(summarize.get("chunk_strategy", "character"))
    chunk_chars = int(summarize["chunk_chars"])
    reduce_chars = int(summarize["reduce_chars"])
    chunk_tokens = summarize.get("chunk_tokens")
    reduce_tokens = summarize.get("reduce_tokens")
    source_tokens = token_counter.count_tokens(content) if chunk_strategy == "token" and token_counter is not None else None
    should_chunk = mode == "summarize" and len(content) > chunk_chars
    if mode == "summarize" and chunk_strategy == "token":
        if token_counter is None or chunk_tokens is None:
            raise ValueError("Token-aware chunking requires an exact token counter and chunk token budget.")
        source_tokens = token_counter.count_tokens(content)
        should_chunk = source_tokens > int(chunk_tokens)

    if should_chunk:
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
    )


def call_timing_summary(call_timings: list[dict[str, Any]]) -> dict[str, Any]:
    duration = None
    if call_timings:
        duration = duration_between(call_timings[0].get("started_at"), call_timings[-1].get("completed_at"))
    return {
        "duration_ms": duration,
        "calls": call_timings,
    }


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
) -> dict[str, Any]:
    last_error: str | None = None
    call_timings: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        try:
            content = item.path.read_text(encoding="utf-8", errors="replace")
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
            (job_dir / "log.md").write_text(f"# Failure\n\n{last_error}\n", encoding="utf-8")
            return {
                "status": "failed",
                "result_json": None,
                "result_md": None,
                "raw_response": None,
                "warnings": [],
                "chunking": job.get("chunking", single_pass_chunking()),
                "snippets": job.get("snippets", compact_snippet_status({"policy": "off", "requested_count": 0})),
                "error": last_error,
                "timing": {
                    "calls": call_timings,
                },
            }

    raise RuntimeError("Job execution ended without a result.")


def apply_job_update(job: dict[str, Any], update: dict[str, Any]) -> None:
    for key in ["status", "result_json", "result_md", "raw_response", "warnings", "chunking", "snippets", "error"]:
        job[key] = update[key]
    job.setdefault("timing", {})["calls"] = update.get("timing", {}).get("calls", [])


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

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while queued or in_flight:
            while queued and len(in_flight) < max_workers:
                job, item = queued.pop(0)
                started_at = timestamp_now()
                timing = job.setdefault("timing", {})
                timing["started_at"] = started_at
                timing["queue_wait_ms"] = duration_between(timing.get("queued_at"), started_at)
                job["status"] = "running"
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
                )
                in_flight[future] = job

            done, _pending = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                job = in_flight.pop(future)
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
    model: str | None = None,
    chunk_chars: int | None = None,
    reduce_chars: int | None = None,
    chunk_strategy: str | None = None,
    chunk_tokens: int | None = None,
    reduce_tokens: int | None = None,
    token_safety_margin: float | None = None,
    snippets: str | None = None,
    snippet_max_chars: int | None = None,
    parallel_jobs: int | None = None,
    parallel_chunks: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_config = resolve_runtime_config(
        root=root,
        default_model=default_model,
        config_path=config_path,
        overrides=RuntimeOverrides(
            profile=profile,
            model=model,
            chunk_strategy=chunk_strategy,
            chunk_chars=chunk_chars,
            reduce_chars=reduce_chars,
            chunk_tokens=chunk_tokens,
            reduce_tokens=reduce_tokens,
            token_safety_margin=token_safety_margin,
            snippets=snippets,
            snippet_max_chars=snippet_max_chars,
            parallel_jobs=parallel_jobs,
            parallel_chunks=parallel_chunks,
        ),
    )
    agent = load_agent(root, agent_id, str(runtime_config["model"]))
    if model_is_explicit(runtime_config):
        agent["model"] = runtime_config["model"]
    runtime_config = set_effective_model(runtime_config, str(agent["model"]))
    runtime_config = finalize_runtime_config_for_agent(runtime_config, agent)
    return agent, runtime_config


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
    model: str | None = None,
    chunk_chars: int | None = None,
    reduce_chars: int | None = None,
    chunk_strategy: str | None = None,
    chunk_tokens: int | None = None,
    reduce_tokens: int | None = None,
    token_safety_margin: float | None = None,
    snippets: str | None = None,
    snippet_max_chars: int | None = None,
    parallel_jobs: int | None = None,
    parallel_chunks: int | None = None,
    runtime_config: dict[str, Any] | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    per_file_timeout_seconds: int = DEFAULT_PER_FILE_TIMEOUT_SECONDS,
    model_processor: ModelProcessor = default_model_processor,
    token_counter: ExactTokenCounter | None = None,
    token_counter_loader: TokenCounterLoader = load_exact_token_counter,
) -> dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported farm mode: {mode}")
    if mode == "prompt" and not instructions:
        raise ValueError("prompt mode requires --instructions.")

    if runtime_config is None:
        agent, runtime_config = resolve_run_agent_and_config(
            root=root,
            agent_id=agent_id,
            default_model=default_model,
            config_path=config_path,
            profile=profile,
            model=model,
            chunk_strategy=chunk_strategy,
            chunk_chars=chunk_chars,
            reduce_chars=reduce_chars,
            chunk_tokens=chunk_tokens,
            reduce_tokens=reduce_tokens,
            token_safety_margin=token_safety_margin,
            snippets=snippets,
            snippet_max_chars=snippet_max_chars,
            parallel_jobs=parallel_jobs,
            parallel_chunks=parallel_chunks,
        )
    else:
        agent = load_agent(root, agent_id, str(runtime_config["model"]))
        if model_is_explicit(runtime_config):
            agent["model"] = runtime_config["model"]
        runtime_config = set_effective_model(runtime_config, str(agent["model"]))
        runtime_config = finalize_runtime_config_for_agent(runtime_config, agent)

    if runtime_config["summarize"].get("chunk_strategy") == "token" and token_counter is None:
        token_counter = token_counter_loader(root=root, model=str(agent["model"]), local_files_only=True)

    farm_root = farm_home(root)
    discovery = discover_text_files(input_folder)
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
        input_folder=input_folder,
        jobs=jobs,
        skipped_files=discovery.skipped,
        runtime_config=runtime_config,
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
        timeout=per_file_timeout_seconds,
        runtime_config=runtime_config,
        max_attempts=max_attempts,
        model_processor=model_processor,
        token_counter=token_counter,
    )

    status["status"] = final_run_status(jobs)
    status["counts"] = count_jobs(jobs, skipped=len(discovery.skipped))
    completed_at = timestamp_now()
    status["timing"]["completed_at"] = completed_at
    status["timing"]["duration_ms"] = duration_between(status["timing"].get("started_at"), completed_at)
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
            f"Unknown farm run reference: {run_ref}. Run `python qwen.py farm list` to see known runs, "
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
