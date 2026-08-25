from __future__ import annotations

import json
import shutil
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from src import qwen_farm
from src.qwen_farm_files import utc_timestamp
from src.qwen_farm_model_metadata import apply_model_metadata, exact_tokenizer_models
from src.qwen_farm_profiles import compact_runtime_config, derive_token_budget, normalize_config_data, read_config_file
from src.qwen_farm_schema import EXIT_VALID, validate_artifact
from src.qwen_farm_tokenizer import tokenizer_status


RECOMMENDATION_SCHEMA_VERSION = 1
DEFAULT_OUTPUT_DIR = ".run/recommendations"
DEFAULT_REPORT_JSON = "farm-recommendation.json"
DEFAULT_REPORT_MD = "FARM_RECOMMENDATION.md"
DEFAULT_APPLY_JSON = "farm-config-apply.json"
DEFAULT_APPLY_MD = "FARM_CONFIG_APPLY.md"
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


def apply_report_paths(output_dir: Path) -> dict[str, str]:
    return {
        "json": str(output_dir / DEFAULT_APPLY_JSON),
        "markdown": str(output_dir / DEFAULT_APPLY_MD),
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
            "command": "python sift.py farm recommend",
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
        "command": "python sift.py farm recommend",
    }


def build_recommendation_report(
    *,
    root: Path,
    default_model: str,
    ollama_base_url: str,
    agent_id: str = "default",
    profile: str | None = None,
    resource_mode: str | None = None,
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
        resource_mode=resource_mode,
    )
    model = str(agent.get("model") or runtime.get("model") or default_model)
    model_metadata = agent.get("model_metadata") if isinstance(agent.get("model_metadata"), dict) else {}

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
        next_actions.append(action("ollama.install", "required", "Install Ollama, then run setup.", "python sift.py setup"))
    elif not ollama["endpoint_ready"]:
        next_actions.append(action("ollama.start", "recommended", "Start Ollama before measuring local performance.", "python sift.py start"))
    elif ollama["model_installed"] is False:
        next_actions.append(action("model.setup", "recommended", f"Pull or configure `{model}`.", "python sift.py setup"))

    tokenizer = _safe_tokenizer_status(root=root, tokenizer_status_fn=tokenizer_status_fn)
    if not tokenizer.get("ready"):
        next_actions.append(
            action(
                "tokenizer.setup",
                "optional",
                "Run tokenizer setup before using token-aware chunking.",
                "python sift.py farm tokenizer setup",
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

    resource_mode = recommend_resource_mode(runtime=runtime, agent=agent, ollama=ollama, benchmark=benchmark)
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
        "model_metadata": model_metadata,
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


def recommend_resource_mode(
    *,
    runtime: dict[str, Any],
    agent: dict[str, Any],
    ollama: dict[str, Any],
    benchmark: dict[str, Any],
) -> dict[str, Any]:
    runtime_resource = runtime.get("resource_mode") if isinstance(runtime.get("resource_mode"), dict) else {}
    effective = runtime_resource.get("effective")
    requested = runtime_resource.get("requested")
    if effective in {"gpu", "hybrid", "cpu"}:
        confidence = "high" if requested != "auto" or effective == "cpu" else "medium"
        return {
            "recommended": effective,
            "confidence": confidence,
            "reason": runtime_resource.get("reason") or "Use the resource mode resolved by the current runtime config.",
        }
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
    model_metadata = agent.get("model_metadata") if isinstance(agent.get("model_metadata"), dict) else {}
    exact_tokenizer = (model_metadata.get("tokenizer") or {}) if isinstance(model_metadata.get("tokenizer"), dict) else {}
    selected_exact_ready = bool(tokenizer.get("ready")) and bool(exact_tokenizer.get("exact"))
    if selected_exact_ready:
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
            "reason": "Exact local tokenizer readiness was reported for the selected model metadata, so token-aware chunking should reduce avoidable extra calls.",
        }
    if model_metadata.get("support") not in {"tested"}:
        reason = "The selected model family is not dogfood-tested yet; character chunking is the conservative default."
    elif not exact_tokenizer.get("exact"):
        reason = "The selected model metadata does not advertise exact tokenizer support; character chunking is the safest default."
    else:
        reason = "Exact local tokenizer readiness was missing; character chunking is the safest default."
    return {
        "chunk_strategy": "character",
        "chunk_tokens": None,
        "reduce_tokens": None,
        "chunk_chars": summarize.get("chunk_chars"),
        "reduce_chars": summarize.get("reduce_chars"),
        "token_safety_margin": summarize.get("token_safety_margin", 0.10),
        "confidence": "medium",
        "reason": reason,
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
    model_metadata = report.get("model_metadata") if isinstance(report.get("model_metadata"), dict) else {}
    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    benchmark = evidence.get("benchmark") if isinstance(evidence.get("benchmark"), dict) else {}

    lines = [
        "# Farm Recommendation",
        "",
        f"Status: `{report.get('status', '')}`",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Agent: `{report.get('agent', '')}`",
        f"Model: `{report.get('model', '')}`",
        f"Model family: `{model_metadata.get('family') or ''}`",
        f"Model support: `{model_metadata.get('support') or ''}`",
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
            "python sift.py farm doctor --json",
            "python sift.py farm recommend --agent default --profile local-8gb --resource-mode auto --output .run/recommendations",
            "python sift.py farm schema validate .run/recommendations/farm-recommendation.json",
            "python sift.py farm recommend apply",
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


def build_config_apply_report(
    *,
    root: Path,
    recommendation_path: Path | None = None,
    config_path: Path | None = None,
    output_dir: Path | None = None,
    write: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    report_dir = output_dir or default_output_dir(root)
    recommendation_source = recommendation_path or latest_recommendation_path(root)
    target_config = config_path or root / ".sift-farm.json"
    dry_run = not write
    generated = generated_at or utc_timestamp()

    recommendation_validation = validate_artifact(
        root,
        recommendation_source,
        "schemas/farm-recommendation.schema.json",
    )
    if int(recommendation_validation["exit_code"]) != EXIT_VALID:
        raise ValueError("Recommendation JSON failed schema validation: " + "; ".join(recommendation_validation["errors"]))

    recommendation = load_json_object(recommendation_source)
    recommendation_status = str(recommendation.get("status") or "unknown")
    warnings = [str(item) for item in recommendation.get("warnings") or []]
    next_actions: list[dict[str, Any]] = []
    if recommendation_status == "needs_setup":
        raise ValueError("Recommendation status is needs_setup; fix setup and rerun farm recommend before applying config.")
    if recommendation_status == "ready_with_warnings":
        warnings.append("Recommendation status is ready_with_warnings; review caveats before using the applied config.")

    existing_config, existing_error = load_existing_config(target_config)
    if existing_error:
        raise ValueError(existing_error)

    recommended_config = config_from_recommendation(recommendation)
    proposed_config = merge_configs(existing_config, recommended_config)
    proposed_config = normalize_config_data(proposed_config)
    changes = diff_configs(existing_config, proposed_config)
    not_applied = not_applied_guidance(recommendation)
    backup_path = None
    status = "preview"

    if dry_run:
        next_actions.append(
            action(
                "config.apply",
                "optional",
                "Apply the proposed config after reviewing the preview.",
                apply_command(recommendation_source, target_config, report_dir, write=True),
            )
        )
    else:
        backup_path = write_config_with_backup(target_config, proposed_config)
        status = "applied"
        next_actions.append(
            action(
                "config.verify",
                "optional",
                "Verify the resolved setup after applying config.",
                "python sift.py farm doctor",
            )
        )

    report = {
        "schema_version": 1,
        "generated_at": generated,
        "status": status,
        "dry_run": dry_run,
        "recommendation_path": str(recommendation_source),
        "config_path": str(target_config),
        "backup_path": str(backup_path) if backup_path else None,
        "recommendation": {
            "status": recommendation.get("status"),
            "agent": recommendation.get("agent"),
            "model": recommendation.get("model"),
            "generated_at": recommendation.get("generated_at"),
        },
        "existing_config": existing_config,
        "proposed_config": proposed_config,
        "changes": changes,
        "not_applied": not_applied,
        "warnings": dedupe_strings(warnings),
        "next_actions": next_actions,
        "report_paths": apply_report_paths(report_dir),
    }
    return report


def write_config_apply_report(report: dict[str, Any]) -> tuple[Path, Path]:
    paths = report.get("report_paths", {}) if isinstance(report.get("report_paths"), dict) else {}
    json_path = Path(str(paths.get("json") or DEFAULT_APPLY_JSON))
    markdown_path = Path(str(paths.get("markdown") or DEFAULT_APPLY_MD))
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_config_apply_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def load_existing_config(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, None
    try:
        return read_config_file(path), None
    except Exception as exc:
        return {}, f"Existing farm config is invalid and was not changed: {exc}"


def config_from_recommendation(recommendation: dict[str, Any]) -> dict[str, Any]:
    profile = recommendation.get("profile") if isinstance(recommendation.get("profile"), dict) else {}
    resource_mode = recommendation.get("resource_mode") if isinstance(recommendation.get("resource_mode"), dict) else {}
    summarize = recommendation.get("summarize") if isinstance(recommendation.get("summarize"), dict) else {}
    concurrency = recommendation.get("concurrency") if isinstance(recommendation.get("concurrency"), dict) else {}
    parallel_jobs = concurrency.get("parallel_jobs") if isinstance(concurrency.get("parallel_jobs"), dict) else {}

    config: dict[str, Any] = {}
    if profile.get("recommended"):
        config["profile"] = profile["recommended"]
    if resource_mode.get("recommended"):
        config["resource_mode"] = resource_mode["recommended"]
    if recommendation.get("model"):
        config["model"] = recommendation["model"]

    summarize_config: dict[str, Any] = {}
    if summarize.get("chunk_strategy"):
        summarize_config["chunk_strategy"] = summarize["chunk_strategy"]
    for key in ("chunk_tokens", "reduce_tokens", "chunk_chars", "reduce_chars", "token_safety_margin"):
        if summarize.get(key) is not None:
            summarize_config[key] = summarize[key]
    if summarize_config:
        config["summarize"] = summarize_config

    concurrency_config: dict[str, Any] = {}
    if parallel_jobs.get("recommended") is not None:
        concurrency_config["jobs"] = parallel_jobs["recommended"]
    concurrency_config["chunks"] = 1
    config["concurrency"] = concurrency_config
    return normalize_config_data(config)


def merge_configs(existing: dict[str, Any], recommended: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(existing)
    for key in ("profile", "model"):
        if key in recommended:
            merged[key] = recommended[key]
    if "resource_mode" in recommended:
        merged["resource_mode"] = recommended["resource_mode"]
    if "summarize" in recommended:
        current = merged.get("summarize") if isinstance(merged.get("summarize"), dict) else {}
        merged["summarize"] = {**current, **recommended["summarize"]}
    if "concurrency" in recommended:
        current = merged.get("concurrency") if isinstance(merged.get("concurrency"), dict) else {}
        merged["concurrency"] = {**current, **recommended["concurrency"]}
    return merged


def diff_configs(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(set(flatten_config(before)) | set(flatten_config(after))):
        before_present, before_value = config_value_at(before, path)
        after_present, after_value = config_value_at(after, path)
        if before_present and after_present and before_value == after_value:
            continue
        if before_present and after_present:
            action_name = "update"
        elif after_present:
            action_name = "add"
        else:
            action_name = "remove"
        rows.append(
            {
                "path": path,
                "before": before_value if before_present else None,
                "after": after_value if after_present else None,
                "action": action_name,
            }
        )
    return rows


def flatten_config(config: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in config.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(flatten_config(value, path))
        else:
            flattened[path] = value
    return flattened


def config_value_at(config: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = config
    parts = path.split(".")
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def not_applied_guidance(recommendation: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    concurrency = recommendation.get("concurrency") if isinstance(recommendation.get("concurrency"), dict) else {}
    ollama_parallel = (
        concurrency.get("ollama_num_parallel")
        if isinstance(concurrency.get("ollama_num_parallel"), dict)
        else {}
    )
    if ollama_parallel.get("recommended") is not None:
        rows.append(
            {
                "path": "OLLAMA_NUM_PARALLEL",
                "value": str(ollama_parallel["recommended"]),
                "reason": "OLLAMA_NUM_PARALLEL is an Ollama service environment setting, not a farm config field.",
            }
        )
    return rows


def write_config_with_backup(path: Path, config: dict[str, Any]) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if path.exists():
        backup_path = path.with_name(f"{path.name}.{safe_timestamp()}.bak")
        shutil.copy2(path, backup_path)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)
    return backup_path


def safe_timestamp() -> str:
    return utc_timestamp().replace(":", "").replace("-", "").replace("T", "-").replace("Z", "")


def apply_command(recommendation_path: Path, config_path: Path, output_dir: Path, *, write: bool) -> str:
    pieces = ["python sift.py farm recommend apply", str(recommendation_path)]
    pieces.extend(["--config", str(config_path)])
    pieces.extend(["--output", str(output_dir)])
    if write:
        pieces.append("--write")
    return " ".join(pieces)


def render_config_apply_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Farm Config Apply",
        "",
        f"Status: `{report.get('status', '')}`",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Dry run: `{bool(report.get('dry_run'))}`",
        f"Recommendation: `{report.get('recommendation_path', '')}`",
        f"Config: `{report.get('config_path', '')}`",
        f"Backup: `{report.get('backup_path') or ''}`",
        "",
        "## Changes",
        "",
    ]
    changes = [item for item in report.get("changes") or [] if isinstance(item, dict)]
    if changes:
        lines.extend(["| Path | Action | Before | After |", "| --- | --- | --- | --- |"])
        for item in changes:
            lines.append(
                f"| `{item.get('path', '')}` | `{item.get('action', '')}` | "
                f"`{markdown_value(item.get('before'))}` | `{markdown_value(item.get('after'))}` |"
            )
    else:
        lines.append("No config changes.")

    lines.extend(["", "## Not Applied", ""])
    not_applied = [item for item in report.get("not_applied") or [] if isinstance(item, dict)]
    if not_applied:
        for item in not_applied:
            lines.append(f"- `{item.get('path')}` = `{item.get('value', '')}`: {item.get('reason')}")
    else:
        lines.append("No guidance-only fields.")

    lines.extend(["", "## Warnings", ""])
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
        lines.append("No next actions.")
    lines.append("")
    return "\n".join(lines)


def markdown_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


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
    resource_mode: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    try:
        agent, runtime = qwen_farm.resolve_run_agent_and_config(
            root=root,
            agent_id=agent_id,
            default_model=default_model,
            profile=profile,
            resource_mode=resource_mode,
        )
        return agent, compact_runtime_config(runtime), None
    except Exception as exc:
        fallback = apply_model_metadata({"id": agent_id, "model": default_model, "options": {}})
        runtime = {
            "profile": profile or "local-8gb",
            "resource_mode": {
                "requested": resource_mode or "auto",
                "effective": "cpu" if resource_mode == "cpu" else "gpu",
                "source": "fallback",
                "reason": "Runtime config did not resolve cleanly.",
                "agent_option_override": None,
            },
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
        status = tokenizer_status_fn(root=root, models=exact_tokenizer_models(), download=False)
        return status if isinstance(status, dict) else {"ready": False, "models": [], "cache_dir": ""}
    except Exception as exc:
        return {
            "ready": False,
            "cache_dir": str(root / ".run" / "tokenizers" / "hf-cache"),
            "models": [],
            "error": str(exc),
        }
