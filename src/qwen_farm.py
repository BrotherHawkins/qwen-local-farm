from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from src.qwen_farm_files import (
    FARM_SCHEMA_VERSION,
    create_run_dir,
    discover_text_files,
    farm_home,
    job_id_for,
    relative_to,
    utc_timestamp,
)
from src.qwen_farm_model import FarmModelResult, OllamaChatClient, process_file_with_model
from src.qwen_farm_status import (
    count_jobs,
    final_run_status,
    load_run_status,
    render_farm_overview,
    render_run_list,
    render_status_markdown,
    run_status_path,
    write_json,
    write_status,
)


DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_PER_FILE_TIMEOUT_SECONDS = 600
SUPPORTED_MODES = {"summarize", "prompt"}

ModelProcessor = Callable[..., FarmModelResult]


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
) -> dict[str, Any]:
    created_at = utc_timestamp()
    status = {
        "schema_version": FARM_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "running",
        "mode": mode,
        "agent": agent["id"],
        "model": agent["model"],
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
) -> dict[str, Any]:
    status = "complete_with_warnings" if result.warnings or not result.structured_valid else "complete"
    return {
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


def default_model_processor(
    *,
    mode: str,
    file_path: str,
    content: str,
    instructions: str | None,
    agent: dict[str, Any],
    ollama_base_url: str,
    timeout: int,
) -> FarmModelResult:
    client = OllamaChatClient(ollama_base_url, str(agent["model"]), agent.get("options", {}))
    return process_file_with_model(
        client=client,
        mode=mode,
        file_path=file_path,
        content=content,
        instructions=instructions,
        timeout=timeout,
        agent_system_prompt=str(agent.get("system_prompt", "")),
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
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    per_file_timeout_seconds: int = DEFAULT_PER_FILE_TIMEOUT_SECONDS,
    model_processor: ModelProcessor = default_model_processor,
) -> dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported farm mode: {mode}")
    if mode == "prompt" and not instructions:
        raise ValueError("prompt mode requires --instructions.")

    agent = load_agent(root, agent_id, default_model)
    farm_root = farm_home(root)
    discovery = discover_text_files(input_folder)
    run_id, run_dir = create_run_dir(farm_root, output_dir)
    remember_run(root, run_id, run_dir)
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
    )
    write_status(run_dir, status)

    for job, item in zip(jobs, discovery.files):
        job_dir = jobs_dir / job["job_id"]
        job["status"] = "running"
        status["counts"] = count_jobs(jobs, skipped=len(discovery.skipped))
        write_status(run_dir, status)

        last_error: str | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                content = item.path.read_text(encoding="utf-8", errors="replace")
                result = model_processor(
                    mode=mode,
                    file_path=item.relative_path,
                    content=content,
                    instructions=instructions,
                    agent=agent,
                    ollama_base_url=ollama_base_url,
                    timeout=per_file_timeout_seconds,
                )

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
                )
                write_json(json_path, envelope)

                job["status"] = envelope["status"]
                job["result_json"] = relative_to(json_path, run_dir)
                job["result_md"] = relative_to(markdown_path, run_dir)
                job["raw_response"] = relative_to(raw_path, run_dir)
                job["warnings"] = result.warnings
                job["error"] = None
                break
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_attempts:
                    continue
                job["status"] = "failed"
                job["error"] = last_error
                (job_dir / "log.md").write_text(f"# Failure\n\n{last_error}\n", encoding="utf-8")

        status["counts"] = count_jobs(jobs, skipped=len(discovery.skipped))
        write_status(run_dir, status)

    status["status"] = final_run_status(jobs)
    status["counts"] = count_jobs(jobs, skipped=len(discovery.skipped))
    write_status(run_dir, status)
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


def list_runs_text(root: Path) -> str:
    return render_run_list(load_runs(root))


def status_text(root: Path, run_id: str | None = None) -> str:
    if run_id:
        return render_status_markdown(load_run_status(find_run_dir(root, run_id)))
    return render_farm_overview(load_runs(root))
