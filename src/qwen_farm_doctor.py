from __future__ import annotations

import contextlib
import io
import json
import platform
import sys
from pathlib import Path
from typing import Any, Callable

from src import qwen_farm
from src.qwen_farm_files import utc_timestamp
from src.qwen_farm_profiles import compact_runtime_config
from src.qwen_farm_tokenizer import SUPPORTED_QWEN_TOKENIZERS, tokenizer_status


DOCTOR_SCHEMA_VERSION = 1
DEFAULT_REPORT_JSON = "setup-doctor.json"
DEFAULT_REPORT_MD = "setup-doctor.md"

FindOllama = Callable[[], str | None]
RequestJson = Callable[..., dict[str, Any]]
TokenizerStatus = Callable[..., dict[str, Any]]


def default_output_dir(root: Path) -> Path:
    return root / ".run" / "reports"


def check(check_id: str, status: str, message: str) -> dict[str, str]:
    return {"id": check_id, "status": status, "message": message}


def recommendation(recommendation_id: str, priority: str, message: str, command: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"id": recommendation_id, "priority": priority, "message": message}
    if command:
        item["command"] = command
    return item


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


def recent_runs(root: Path, limit: int = 5) -> dict[str, Any]:
    runs = qwen_farm.load_runs(root)
    latest = []
    for run in runs[:limit]:
        latest.append(
            {
                "run_id": run.get("run_id"),
                "status": run.get("status"),
                "mode": run.get("mode"),
                "updated_at": run.get("updated_at"),
                "output": run.get("output"),
                "counts": run.get("counts"),
            }
        )
    return {"known_count": len(runs), "latest": latest}


def calculate_report_status(checks: list[dict[str, str]]) -> str:
    statuses = {item.get("status") for item in checks}
    if "fail" in statuses:
        return "needs_setup"
    if "warn" in statuses or "unknown" in statuses:
        return "ready_with_warnings"
    if checks:
        return "ready"
    return "unknown"


def build_doctor_report(
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
    platform_name: str | None = None,
    python_version: tuple[int, int, int] | None = None,
) -> dict[str, Any]:
    report_dir = output_dir or default_output_dir(root)
    json_path = report_dir / DEFAULT_REPORT_JSON
    markdown_path = report_dir / DEFAULT_REPORT_MD
    checks: list[dict[str, str]] = []
    recommendations: list[dict[str, Any]] = []

    version = python_version or sys.version_info[:3]
    python_ok = version >= (3, 10, 0)
    if python_ok:
        checks.append(check("environment.python", "ok", "Python version is supported."))
    else:
        checks.append(check("environment.python", "fail", "Python 3.10 or newer is required."))
        recommendations.append(
            recommendation("python.upgrade", "required", "Install Python 3.10 or newer before running the farm.")
        )

    ollama_path = find_ollama_fn() if find_ollama_fn else None
    ollama_found = bool(ollama_path)
    if ollama_found:
        checks.append(check("ollama.executable", "ok", "Ollama executable found."))
    else:
        checks.append(check("ollama.executable", "fail", "Ollama executable was not found."))
        recommendations.append(
            recommendation("ollama.install", "required", "Install Ollama, then run setup.", "python qwen.py setup")
        )

    endpoint_ready = False
    ollama_error = None
    models: list[str] = []
    if request_json_fn is None:
        ollama_error = "No Ollama endpoint probe was provided."
        checks.append(check("ollama.endpoint", "unknown", ollama_error))
    else:
        try:
            tags = request_json_fn("GET", f"{ollama_base_url}/api/tags", timeout=3)
            models = installed_model_names(tags)
            endpoint_ready = True
            checks.append(check("ollama.endpoint", "ok", "Ollama endpoint responded."))
        except Exception as exc:
            ollama_error = str(exc)
            checks.append(check("ollama.endpoint", "warn", "Ollama endpoint did not respond."))
            if ollama_found:
                recommendations.append(
                    recommendation("ollama.start", "recommended", "Start the local service and rerun doctor.", "python qwen.py start")
                )

    agent: dict[str, Any] = {
        "id": agent_id,
        "model": None,
        "model_installed": "unknown",
        "error": None,
    }
    runtime: dict[str, Any] = {"error": None}
    try:
        loaded_agent, runtime_config = qwen_farm.resolve_run_agent_and_config(
            root=root,
            agent_id=agent_id,
            default_model=default_model,
            profile=profile,
        )
        agent.update(
            {
                "id": loaded_agent.get("id"),
                "name": loaded_agent.get("name"),
                "model": loaded_agent.get("model"),
            }
        )
        runtime = compact_runtime_config(runtime_config)
        checks.append(check("runtime.config", "ok", "Runtime config resolved."))
    except Exception as exc:
        agent["error"] = str(exc)
        runtime = {"error": str(exc)}
        checks.append(check("runtime.config", "fail", "Runtime config or agent loading failed."))

    model = str(agent.get("model") or "")
    if model:
        if endpoint_ready:
            model_installed = model in models
            agent["model_installed"] = model_installed
            if model_installed:
                checks.append(check("ollama.model_installed", "ok", f"Selected model `{model}` appears installed."))
            else:
                checks.append(check("ollama.model_installed", "warn", f"Selected model `{model}` was not listed by Ollama."))
                recommendations.append(
                    recommendation(
                        "model.setup",
                        "recommended",
                        f"Pull or configure the selected model `{model}`.",
                        "python qwen.py setup",
                    )
                )
        else:
            agent["model_installed"] = "unknown"
            checks.append(check("ollama.model_installed", "unknown", "Model installation could not be checked until Ollama responds."))

    try:
        tokenizer_probe_stderr = io.StringIO()
        with contextlib.redirect_stderr(tokenizer_probe_stderr):
            tokenizer = tokenizer_status_fn(root=root, models=list(SUPPORTED_QWEN_TOKENIZERS), download=False)
        diagnostic_stderr = tokenizer_probe_stderr.getvalue().strip()
        if diagnostic_stderr:
            tokenizer["probe_stderr"] = diagnostic_stderr
    except Exception as exc:
        tokenizer = {
            "ready": False,
            "cache_dir": str(root / ".run" / "tokenizers" / "hf-cache"),
            "models": [],
            "error": str(exc),
        }
    if tokenizer.get("ready"):
        checks.append(check("tokenizers.ready", "ok", "Exact local tokenizers are ready."))
    else:
        checks.append(check("tokenizers.ready", "warn", "Exact local tokenizers are not fully ready."))
        recommendations.append(
            recommendation(
                "tokenizer.setup",
                "optional",
                "Run tokenizer setup before enabling token-aware chunking.",
                "python qwen.py farm tokenizer setup",
            )
        )

    concurrency = runtime.get("concurrency") if isinstance(runtime, dict) else None
    if isinstance(concurrency, dict) and int(concurrency.get("jobs") or 1) > 1:
        recommendations.append(
            recommendation(
                "concurrency.smoke",
                "optional",
                "Run a small folder before increasing farm/Ollama parallelism further.",
            )
        )

    recommendations.append(
        recommendation(
            "smoke.run",
            "optional",
            "Run a tiny model-free-sized farm input before a large batch.",
            "python qwen.py farm run <input-folder> --mode summarize",
        )
    )

    report = {
        "schema_version": DOCTOR_SCHEMA_VERSION,
        "generated_at": generated_at or utc_timestamp(),
        "status": calculate_report_status(checks),
        "root": str(root),
        "environment": {
            "os": platform_name or platform.system(),
            "python": ".".join(str(part) for part in version),
            "python_ok": python_ok,
        },
        "ollama": {
            "executable": ollama_path,
            "found": ollama_found,
            "base_url": ollama_base_url,
            "endpoint_ready": endpoint_ready,
            "models": models,
            "error": ollama_error,
        },
        "agent": agent,
        "runtime": runtime,
        "tokenizers": tokenizer,
        "runs": recent_runs(root),
        "profile_recommendation": latest_profile_recommendation(root),
        "checks": checks,
        "recommendations": recommendations,
        "report_paths": {
            "markdown": str(markdown_path),
            "json": str(json_path),
        },
    }
    return report


def render_doctor_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Farm Doctor",
        "",
        f"Status: `{report.get('status', '')}`",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Root: `{report.get('root', '')}`",
        "",
        "## Environment",
        "",
    ]
    environment = report.get("environment", {}) if isinstance(report.get("environment"), dict) else {}
    lines.extend(
        [
            f"- OS: `{environment.get('os', '')}`",
            f"- Python: `{environment.get('python', '')}`",
            f"- Python OK: `{bool(environment.get('python_ok'))}`",
            "",
            "## Ollama",
            "",
        ]
    )
    ollama = report.get("ollama", {}) if isinstance(report.get("ollama"), dict) else {}
    lines.extend(
        [
            f"- Executable: `{ollama.get('executable') or ''}`",
            f"- Found: `{bool(ollama.get('found'))}`",
            f"- Base URL: `{ollama.get('base_url') or ''}`",
            f"- Endpoint ready: `{bool(ollama.get('endpoint_ready'))}`",
            f"- Models: `{', '.join(ollama.get('models') or [])}`",
        ]
    )
    if ollama.get("error"):
        lines.append(f"- Error: `{ollama.get('error')}`")

    agent = report.get("agent", {}) if isinstance(report.get("agent"), dict) else {}
    runtime = report.get("runtime", {}) if isinstance(report.get("runtime"), dict) else {}
    lines.extend(
        [
            "",
            "## Agent And Runtime",
            "",
            f"- Agent: `{agent.get('id') or ''}`",
            f"- Model: `{agent.get('model') or ''}`",
            f"- Model installed: `{agent.get('model_installed')}`",
            f"- Profile: `{runtime.get('profile') or ''}`",
            f"- Chunk strategy: `{((runtime.get('summarize') or {}) if isinstance(runtime.get('summarize'), dict) else {}).get('chunk_strategy') or ''}`",
            f"- Parallel jobs: `{((runtime.get('concurrency') or {}) if isinstance(runtime.get('concurrency'), dict) else {}).get('jobs') or ''}`",
            "",
            "## Tokenizers",
            "",
        ]
    )
    tokenizers = report.get("tokenizers", {}) if isinstance(report.get("tokenizers"), dict) else {}
    lines.extend(
        [
            f"- Ready: `{bool(tokenizers.get('ready'))}`",
            f"- Cache: `{tokenizers.get('cache_dir') or ''}`",
        ]
    )
    for record in tokenizers.get("models") or []:
        if not isinstance(record, dict):
            continue
        lines.append(
            f"- `{record.get('model')}`: ready `{bool(record.get('ready'))}`, "
            f"offline `{bool(record.get('offline_verified'))}`"
        )

    runs = report.get("runs", {}) if isinstance(report.get("runs"), dict) else {}
    lines.extend(
        [
            "",
            "## Recent Runs",
            "",
            f"Known runs: `{runs.get('known_count', 0)}`",
        ]
    )
    for run in runs.get("latest") or []:
        if not isinstance(run, dict):
            continue
        lines.append(f"- `{run.get('run_id')}`: `{run.get('status')}` `{run.get('mode')}` `{run.get('updated_at')}`")

    profile_recommendation = (
        report.get("profile_recommendation")
        if isinstance(report.get("profile_recommendation"), dict)
        else {}
    )
    lines.extend(["", "## Profile Recommendation", ""])
    if profile_recommendation.get("exists"):
        lines.extend(
            [
                f"- Status: `{profile_recommendation.get('status')}`",
                f"- Generated: `{profile_recommendation.get('generated_at') or ''}`",
                f"- Profile: `{profile_recommendation.get('profile') or ''}`",
                f"- Resource mode: `{profile_recommendation.get('resource_mode') or ''}`",
                f"- Parallel jobs: `{profile_recommendation.get('parallel_jobs') or ''}`",
                f"- `OLLAMA_NUM_PARALLEL`: `{profile_recommendation.get('ollama_num_parallel') or ''}`",
                f"- JSON: `{profile_recommendation.get('path') or ''}`",
            ]
        )
    else:
        lines.append(
            f"- Missing measured recommendation. Run: `{profile_recommendation.get('command') or 'python qwen.py farm recommend'}`"
        )

    lines.extend(["", "## Checks", "", "| Check | Status | Message |", "| --- | --- | --- |"])
    for item in report.get("checks") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"| `{item.get('id', '')}` | `{item.get('status', '')}` | {item.get('message', '')} |")

    lines.extend(["", "## Recommendations", ""])
    recommendations = [item for item in report.get("recommendations") or [] if isinstance(item, dict)]
    if not recommendations:
        lines.append("No recommendations.")
    for item in recommendations:
        command = f" Command: `{item.get('command')}`" if item.get("command") else ""
        lines.append(f"- `{item.get('priority')}` {item.get('message')}{command}")

    report_paths = report.get("report_paths", {}) if isinstance(report.get("report_paths"), dict) else {}
    lines.extend(
        [
            "",
            "## Report Paths",
            "",
            f"- Markdown: `{report_paths.get('markdown') or ''}`",
            f"- JSON: `{report_paths.get('json') or ''}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_doctor_report(report: dict[str, Any]) -> tuple[Path, Path]:
    paths = report.get("report_paths", {}) if isinstance(report.get("report_paths"), dict) else {}
    markdown_path = Path(str(paths.get("markdown") or DEFAULT_REPORT_MD))
    json_path = Path(str(paths.get("json") or DEFAULT_REPORT_JSON))
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_doctor_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return markdown_path, json_path


def latest_profile_recommendation(root: Path) -> dict[str, Any]:
    path = root / ".run" / "recommendations" / "farm-recommendation.json"
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "status": "missing",
            "generated_at": None,
            "command": "python qwen.py farm recommend",
        }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "exists": True,
            "path": str(path),
            "status": "unreadable",
            "generated_at": None,
            "error": str(exc),
            "command": "python qwen.py farm recommend",
        }
    if not isinstance(data, dict):
        return {
            "exists": True,
            "path": str(path),
            "status": "unreadable",
            "generated_at": None,
            "error": "Recommendation JSON must contain an object.",
            "command": "python qwen.py farm recommend",
        }

    profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    resource_mode = data.get("resource_mode") if isinstance(data.get("resource_mode"), dict) else {}
    concurrency = data.get("concurrency") if isinstance(data.get("concurrency"), dict) else {}
    parallel_jobs = concurrency.get("parallel_jobs") if isinstance(concurrency.get("parallel_jobs"), dict) else {}
    ollama_parallel = (
        concurrency.get("ollama_num_parallel")
        if isinstance(concurrency.get("ollama_num_parallel"), dict)
        else {}
    )
    return {
        "exists": True,
        "path": str(path),
        "status": data.get("status"),
        "generated_at": data.get("generated_at"),
        "agent": data.get("agent"),
        "model": data.get("model"),
        "profile": profile.get("recommended"),
        "resource_mode": resource_mode.get("recommended"),
        "parallel_jobs": parallel_jobs.get("recommended"),
        "ollama_num_parallel": ollama_parallel.get("recommended"),
        "command": "python qwen.py farm recommend",
    }
