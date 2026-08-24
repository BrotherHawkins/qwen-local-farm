from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from src import qwen_farm
from src.qwen_farm_files import utc_timestamp
from src.qwen_farm_profiles import compact_runtime_config, derive_token_budget
from src.qwen_farm_tokenizer import SUPPORTED_QWEN_TOKENIZERS, tokenizer_status


RECOMMENDATION_SCHEMA_VERSION = 1
DEFAULT_OUTPUT_DIR = ".run/recommendations"
DEFAULT_REPORT_JSON = "farm-recommendation.json"
DEFAULT_REPORT_MD = "FARM_RECOMMENDATION.md"
STALE_AFTER_DAYS = 14

FindOllama = Callable[[], str | None]
RequestJson = Callable[..., dict[str, Any]]
TokenizerStatus = Callable[..., dict[str, Any]]


def default_output_dir(root: Path) -> Path:
    return root / DEFAULT_OUTPUT_DIR


def recommendation_paths(output_dir: Path) -> dict[str, str]:
    return {
        "json": str(output_dir / DEFAULT_REPORT_JSON),
        "markdown": str(output_dir / DEFAULT_REPORT_MD),
    }


def latest_recommendation_path(root: Path, output_dir: Path | None = None) -> Path:
    return (output_dir or default_output_dir(root)) / DEFAULT_REPORT_JSON


def load_latest_recommendation(root: Path, output_dir: Path | None = None) -> dict[str, Any] | None:
    path = latest_recommendation_path(root, output_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def recommendation_summary(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    path = latest_recommendation_path(root, output_dir)
    report = load_latest_recommendation(root, output_dir)
    if report is None:
        return {
            "exists": False,
            "path": str(path),
            "status": "missing",
            "generated_at": None,
            "command": "python qwen.py farm recommend",
        }

    profile = report.get("profile") if isinstance(report.get("profile"), dict) else {}
    resource_mode = report.get("resource_mode") if isinstance(report.get("resource_mode"), dict) else {}
    concurrency = report.get("concurrency") if isinstance(report.get("concurrency"), dict) else {}
    parallel_jobs = concurrency.get("parallel_jobs") if isinstance(concurrency.get("parallel_jobs"), dict) else {}
    ollama_parallel = (
        concurrency.get("ollama_num_parallel")
        if isinstance(concurrency.get("ollama_num_parallel"), dict)
        else {}
    )
    return {
        "exists": True,
        "path": str(path),
        "status": report.get("status"),
        "generated_at": report.get("generated_at"),
        "agent": report.get("agent"),
        "model": report.get("model"),
        "profile": profile.get("recommended"),
        "resource_mode": resource_mode.get("recommended"),
        "parallel_jobs": parallel_jobs.get("recommended"),
        "ollama_num_parallel": ollama_parallel.get("recommended"),
        "command": "python qwen.py farm recommend",
    }


def build_recommendation_report(
    *,
    root: Path,
    default_model: str,
    ollama_base_url: str,
    agent_id: str = "default",
    profile: str | None = None,
    output_dir: Path | None = None,
    generated_at: str | None = None,
    find_ollama_fn: FindOllama | None = None,
    request_json_fn: RequestJson | None = None,
    tokenizer_status_fn: TokenizerStatus = tokenizer_status,
) -> dict[str, Any]:
    report_dir = output_dir or default_output_dir(root)
    generated = generated_at or utc_timestamp()
    warnings: list[str] = []
    next_actions: list[dict[str, Any]] = []

    agent, runtime, runtime_error = _resolve_agent_runtime(
        root=root,
        agent_id=agent_id,
        default_model=default_model,
        profile=profile,
    )
    model = str(agent.get("model") or runtime.get("model") or default_model)

    ollama = _probe_ollama(
        ollama_base_url=ollama_base_url,
        model=model,
        find_ollama_fn=find_ollama_fn,
        request_json_fn=request_json_fn,
    )
    if runtime_error:
        warnings.append(runtime_error)
        next_actions.append(action("runtime.config", "required", runtime_error))
    if not ollama["found"]:
        next_actions.append(action("ollama.install", "required", "Install Ollama, then run setup.", "python qwen.py setup"))
    elif not ollama["endpoint_ready"]:
        next_actions.append(action("ollama.start", "recommended", "Start Ollama before measuring local performance.", "python qwen.py start"))
    elif ollama["model_installed"] is False:
        next_actions.append(action("model.setup", "recommended", f"Pull or configure `{model}`.", "python qwen.py setup"))

    tokenizer = _safe_tokenizer_status(root=root, tokenizer_status_fn=tokenizer_status_fn)
    if not tokenizer.get("ready"):
        next_actions.append(
            action(
                "tokenizer.setup",
                "optional",
                "Run tokenizer setup before using token-aware chunking.",
                "python qwen.py farm tokenizer setup",
            )
        )

    benchmark = run_tiny_benchmark_probe(
        ollama_base_url=ollama_base_url,
        agent=agent,
        model=model,
        request_json_fn=request_json_fn,
    ) if ollama["endpoint_ready"] and ollama["model_installed"] is not False else skipped_benchmark(ollama)

    if benchmark.get("status") != "complete":
        warnings.append(str(benchmark.get("message") or "Benchmark probe did not complete."))

    resource_mode = recommend_resource_mode(agent=agent, ollama=ollama, benchmark=benchmark)
    profile_rec = recommend_profile(runtime=runtime, requested_profile=profile, benchmark=benchmark, runtime_error=runtime_error)
    concurrency = recommend_concurrency(runtime=runtime, benchmark=benchmark)
    summarize = recommend_summarize(runtime=runtime, tokenizer=tokenizer, agent=agent)

    if int(((runtime.get("concurrency") or {}).get("jobs") if isinstance(runtime.get("concurrency"), dict) else 1) or 1) > 1:
        warnings.append("Current runtime allows more than one farm job, but this recommendation did not benchmark parallel load.")

    status = report_status(runtime_error=runtime_error, ollama=ollama, benchmark=benchmark)
    report = {
        "schema_version": RECOMMENDATION_SCHEMA_VERSION,
        "generated_at": generated,
        "status": status,
        "agent": str(agent.get("id") or agent_id),
        "model": model,
        "resource_mode": resource_mode,
        "profile": profile_rec,
        "concurrency": concurrency,
        "summarize": summarize,
        "evidence": {
            "benchmark": benchmark,
            "ollama": ollama,
            "runtime": runtime,
            "tokenizers": tokenizer,
        },
        "warnings": dedupe_strings(warnings),
        "next_actions": next_actions,
        "report_paths": recommendation_paths(report_dir),
    }
    return report


def run_tiny_benchmark_probe(
    *,
    ollama_base_url: str,
    agent: dict[str, Any],
    model: str,
    request_json_fn: RequestJson | None,
) -> dict[str, Any]:
    started_at = utc_timestamp()
    if request_json_fn is None:
        return {
            "status": "skipped",
            "started_at": started_at,
            "completed_at": utc_timestamp(),
            "duration_ms": None,
            "model": model,
            "message": "No Ollama request function was provided.",
        }

    options = dict(agent.get("options") or {})
    options.setdefault("temperature", 0)
    options.setdefault("num_predict", 16)
    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": "user", "content": "Reply with exactly: ready"}],
        "options": options,
    }
    started = time.perf_counter()
    try:
        response = request_json_fn("POST", f"{ollama_base_url}/api/chat", payload=payload, timeout=120)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "status": "complete",
            "started_at": started_at,
            "completed_at": utc_timestamp(),
            "duration_ms": duration_ms,
            "model": model,
            "agent": agent.get("id"),
            "prompt_size": "tiny",
            "options": compact_probe_options(options),
            "response_keys": sorted(str(key) for key in response.keys()),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "started_at": started_at,
            "completed_at": utc_timestamp(),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "model": model,
            "agent": agent.get("id"),
            "prompt_size": "tiny",
            "message": str(exc),
        }


def skipped_benchmark(ollama: dict[str, Any]) -> dict[str, Any]:
    if not ollama.get("endpoint_ready"):
        message = "Ollama endpoint was not ready, so no benchmark probe ran."
    elif ollama.get("model_installed") is False:
        message = "Selected model was not listed by Ollama, so no benchmark probe ran."
    else:
        message = "Benchmark probe was skipped."
    return {
        "status": "skipped",
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "model": ollama.get("model"),
        "message": message,
    }


def recommend_resource_mode(*, agent: dict[str, Any], ollama: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    options = agent.get("options") if isinstance(agent.get("options"), dict) else {}
    num_gpu = options.get("num_gpu")
    agent_id = str(agent.get("id") or "").lower()
    if num_gpu == 0 or agent_id.endswith("-cpu"):
        return {
            "recommended": "cpu",
            "confidence": "high",
            "reason": "The selected agent explicitly sets num_gpu to 0 or is a CPU agent.",
        }
    if isinstance(num_gpu, int) and num_gpu > 0:
        return {
            "recommended": "hybrid",
            "confidence": "high",
            "reason": "The selected agent uses partial GPU offload through num_gpu.",
        }
    if not ollama.get("endpoint_ready") or benchmark.get("status") != "complete":
        return {
            "recommended": "auto",
            "confidence": "low",
            "reason": "Run measured recommendations again after Ollama and the selected model are ready.",
        }
    return {
        "recommended": "hybrid",
        "confidence": "medium",
        "reason": "The agent leaves placement to Ollama; keep GPU use opportunistic with CPU/RAM fallback expectations.",
    }


def recommend_profile(
    *,
    runtime: dict[str, Any],
    requested_profile: str | None,
    benchmark: dict[str, Any],
    runtime_error: str | None,
) -> dict[str, Any]:
    selected = str(runtime.get("profile") or requested_profile or "local-8gb")
    if runtime_error:
        return {
            "recommended": selected,
            "confidence": "low",
            "reason": "Runtime config did not resolve cleanly; keep the default profile until setup is fixed.",
        }
    if benchmark.get("status") == "complete":
        return {
            "recommended": selected,
            "confidence": "medium",
            "reason": "The selected profile resolved and the tiny local benchmark probe completed.",
        }
    return {
        "recommended": selected,
        "confidence": "low",
        "reason": "The selected profile resolved, but no completed benchmark evidence was available.",
    }


def recommend_concurrency(*, runtime: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    runtime_jobs = 1
    if isinstance(runtime.get("concurrency"), dict):
        runtime_jobs = int(runtime["concurrency"].get("jobs") or 1)
    reason = "Stay at one farm worker until a benchmark explicitly compares parallel load on this machine."
    if benchmark.get("status") == "complete":
        reason = "A tiny single-worker probe completed; parallel load was not measured, so keep concurrency conservative."
    return {
        "parallel_jobs": {
            "recommended": 1,
            "current": runtime_jobs,
            "confidence": "high",
            "reason": reason,
        },
        "ollama_num_parallel": {
            "recommended": 1,
            "current": None,
            "confidence": "medium",
            "reason": "Keep Ollama request parallelism aligned with farm worker concurrency unless a separate parallel benchmark supports more.",
        },
    }


def recommend_summarize(*, runtime: dict[str, Any], tokenizer: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
    summarize = runtime.get("summarize") if isinstance(runtime.get("summarize"), dict) else {}
    if tokenizer.get("ready"):
        chunk_tokens = summarize.get("chunk_tokens")
        reduce_tokens = summarize.get("reduce_tokens")
        if chunk_tokens is None or reduce_tokens is None:
            num_ctx = (agent.get("options") or {}).get("num_ctx") if isinstance(agent.get("options"), dict) else None
            if isinstance(num_ctx, int) and num_ctx > 0:
                derived = derive_token_budget(num_ctx, float(summarize.get("token_safety_margin") or 0.10))
                chunk_tokens = chunk_tokens or derived
                reduce_tokens = reduce_tokens or derived
        return {
            "chunk_strategy": "token",
            "chunk_tokens": chunk_tokens,
            "reduce_tokens": reduce_tokens,
            "chunk_chars": summarize.get("chunk_chars"),
            "reduce_chars": summarize.get("reduce_chars"),
            "token_safety_margin": summarize.get("token_safety_margin", 0.10),
            "confidence": "high",
            "reason": "Exact local tokenizer readiness was reported, so token-aware chunking should reduce avoidable extra calls.",
        }
    return {
        "chunk_strategy": "character",
        "chunk_tokens": None,
        "reduce_tokens": None,
        "chunk_chars": summarize.get("chunk_chars"),
        "reduce_chars": summarize.get("reduce_chars"),
        "token_safety_margin": summarize.get("token_safety_margin", 0.10),
        "confidence": "medium",
        "reason": "Exact local tokenizer readiness was missing; character chunking is the safest default.",
    }


def render_recommendation_markdown(report: dict[str, Any]) -> str:
    profile = report.get("profile") if isinstance(report.get("profile"), dict) else {}
    resource_mode = report.get("resource_mode") if isinstance(report.get("resource_mode"), dict) else {}
    concurrency = report.get("concurrency") if isinstance(report.get("concurrency"), dict) else {}
    parallel_jobs = concurrency.get("parallel_jobs") if isinstance(concurrency.get("parallel_jobs"), dict) else {}
    ollama_parallel = (
        concurrency.get("ollama_num_parallel")
        if isinstance(concurrency.get("ollama_num_parallel"), dict)
        else {}
    )
    summarize = report.get("summarize") if isinstance(report.get("summarize"), dict) else {}
    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    benchmark = evidence.get("benchmark") if isinstance(evidence.get("benchmark"), dict) else {}

    lines = [
        "# Farm Recommendation",
        "",
        f"Status: `{report.get('status', '')}`",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Agent: `{report.get('agent', '')}`",
        f"Model: `{report.get('model', '')}`",
        "",
        "## Recommended Settings",
        "",
        f"- Profile: `{profile.get('recommended')}` ({profile.get('confidence')} confidence)",
        f"- Resource mode: `{resource_mode.get('recommended')}` ({resource_mode.get('confidence')} confidence)",
        f"- Farm parallel jobs: `{parallel_jobs.get('recommended')}` ({parallel_jobs.get('confidence')} confidence)",
        f"- `OLLAMA_NUM_PARALLEL`: `{ollama_parallel.get('recommended')}` ({ollama_parallel.get('confidence')} confidence)",
        f"- Summarize chunk strategy: `{summarize.get('chunk_strategy')}` ({summarize.get('confidence')} confidence)",
    ]
    if summarize.get("chunk_strategy") == "token":
        lines.extend(
            [
                f"- Chunk tokens: `{summarize.get('chunk_tokens')}`",
                f"- Reduce tokens: `{summarize.get('reduce_tokens')}`",
            ]
        )
    else:
        lines.extend(
            [
                f"- Chunk chars: `{summarize.get('chunk_chars')}`",
                f"- Reduce chars: `{summarize.get('reduce_chars')}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Reasons",
            "",
            f"- Profile: {profile.get('reason')}",
            f"- Resource mode: {resource_mode.get('reason')}",
            f"- Parallel jobs: {parallel_jobs.get('reason')}",
            f"- Ollama parallelism: {ollama_parallel.get('reason')}",
            f"- Summarize: {summarize.get('reason')}",
            "",
            "## Evidence",
            "",
            f"- Benchmark status: `{benchmark.get('status')}`",
            f"- Benchmark duration ms: `{benchmark.get('duration_ms')}`",
            f"- Benchmark message: `{benchmark.get('message') or ''}`",
            "",
            "## Warnings",
            "",
        ]
    )
    warnings = [str(item) for item in report.get("warnings") or []]
    if warnings:
        lines.extend(f"- {item}" for item in warnings)
    else:
        lines.append("No warnings.")

    lines.extend(["", "## Next Actions", ""])
    actions = [item for item in report.get("next_actions") or [] if isinstance(item, dict)]
    if actions:
        for item in actions:
            command = f" Command: `{item.get('command')}`" if item.get("command") else ""
            lines.append(f"- `{item.get('priority')}` {item.get('message')}{command}")
    else:
        lines.append("No required next actions.")

    lines.extend(
        [
            "",
            "## Copyable Commands",
            "",
            "```powershell",
            "python qwen.py farm doctor --json",
            "python qwen.py farm recommend --agent default --profile local-8gb --output .run/recommendations",
            "python qwen.py farm schema validate .run/recommendations/farm-recommendation.json",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_recommendation_report(report: dict[str, Any]) -> tuple[Path, Path]:
    paths = report.get("report_paths", {}) if isinstance(report.get("report_paths"), dict) else {}
    json_path = Path(str(paths.get("json") or DEFAULT_REPORT_JSON))
    markdown_path = Path(str(paths.get("markdown") or DEFAULT_REPORT_MD))
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_recommendation_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def action(action_id: str, priority: str, message: str, command: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"id": action_id, "priority": priority, "message": message}
    if command:
        item["command"] = command
    return item


def report_status(*, runtime_error: str | None, ollama: dict[str, Any], benchmark: dict[str, Any]) -> str:
    if runtime_error or not ollama.get("found"):
        return "needs_setup"
    if not ollama.get("endpoint_ready") or ollama.get("model_installed") is False:
        return "needs_setup"
    if benchmark.get("status") == "complete":
        return "ready"
    return "ready_with_warnings"


def compact_probe_options(options: dict[str, Any]) -> dict[str, Any]:
    keep = ["num_ctx", "num_batch", "num_gpu", "num_predict", "temperature", "top_p"]
    return {key: options[key] for key in keep if key in options}


def dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _resolve_agent_runtime(
    *,
    root: Path,
    agent_id: str,
    default_model: str,
    profile: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    try:
        agent, runtime = qwen_farm.resolve_run_agent_and_config(
            root=root,
            agent_id=agent_id,
            default_model=default_model,
            profile=profile,
        )
        return agent, compact_runtime_config(runtime), None
    except Exception as exc:
        fallback = {"id": agent_id, "model": default_model, "options": {}}
        runtime = {
            "profile": profile or "local-8gb",
            "model": default_model,
            "summarize": {},
            "concurrency": {"jobs": 1, "chunks": 1},
        }
        return fallback, runtime, str(exc)


def _probe_ollama(
    *,
    ollama_base_url: str,
    model: str,
    find_ollama_fn: FindOllama | None,
    request_json_fn: RequestJson | None,
) -> dict[str, Any]:
    executable = find_ollama_fn() if find_ollama_fn else None
    endpoint_ready = False
    models: list[str] = []
    error = None
    if request_json_fn is None:
        error = "No Ollama endpoint probe was provided."
    else:
        try:
            tags = request_json_fn("GET", f"{ollama_base_url}/api/tags", timeout=3)
            endpoint_ready = True
            models = installed_model_names(tags)
        except Exception as exc:
            error = str(exc)
    model_installed: bool | str = model in models if endpoint_ready else "unknown"
    return {
        "found": bool(executable),
        "executable": executable,
        "base_url": ollama_base_url,
        "endpoint_ready": endpoint_ready,
        "models": models,
        "model": model,
        "model_installed": model_installed,
        "error": error,
    }


def installed_model_names(tags: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    for item in tags.get("models") or []:
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            value = item.get(key)
            if value:
                names.add(str(value))
    return sorted(names)


def _safe_tokenizer_status(*, root: Path, tokenizer_status_fn: TokenizerStatus) -> dict[str, Any]:
    try:
        status = tokenizer_status_fn(root=root, models=list(SUPPORTED_QWEN_TOKENIZERS), download=False)
        return status if isinstance(status, dict) else {"ready": False, "models": [], "cache_dir": ""}
    except Exception as exc:
        return {
            "ready": False,
            "cache_dir": str(root / ".run" / "tokenizers" / "hf-cache"),
            "models": [],
            "error": str(exc),
        }
