from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_FILE_NAME = ".qwen-farm.json"
PROFILE_NAMES = ["cpu-small", "local-4gb", "local-8gb", "local-12gb", "local-24gb", "custom"]
DEFAULT_PROFILE = "local-8gb"

TOP_LEVEL_FIELDS = {"profile", "model", "summarize", "concurrency"}
SUMMARIZE_FIELDS = {"chunk_chars", "reduce_chars"}
CONCURRENCY_FIELDS = {"jobs", "chunks"}


@dataclass(frozen=True)
class RuntimeOverrides:
    profile: str | None = None
    model: str | None = None
    chunk_chars: int | None = None
    reduce_chars: int | None = None
    parallel_jobs: int | None = None
    parallel_chunks: int | None = None


def built_in_profile(profile: str, default_model: str) -> dict[str, Any]:
    if profile not in PROFILE_NAMES:
        raise ValueError(f"Unknown farm profile: {profile}")

    profiles: dict[str, dict[str, Any]] = {
        "cpu-small": {
            "profile": "cpu-small",
            "model": default_model,
            "summarize": {"chunk_chars": 4_000, "reduce_chars": 4_000},
            "concurrency": {"jobs": 1, "chunks": 1},
        },
        "local-4gb": {
            "profile": "local-4gb",
            "model": default_model,
            "summarize": {"chunk_chars": 6_000, "reduce_chars": 6_000},
            "concurrency": {"jobs": 1, "chunks": 1},
        },
        "local-8gb": {
            "profile": "local-8gb",
            "model": default_model,
            "summarize": {"chunk_chars": 8_000, "reduce_chars": 8_000},
            "concurrency": {"jobs": 1, "chunks": 1},
        },
        "local-12gb": {
            "profile": "local-12gb",
            "model": default_model,
            "summarize": {"chunk_chars": 12_000, "reduce_chars": 12_000},
            "concurrency": {"jobs": 1, "chunks": 1},
        },
        "local-24gb": {
            "profile": "local-24gb",
            "model": default_model,
            "summarize": {"chunk_chars": 20_000, "reduce_chars": 20_000},
            "concurrency": {"jobs": 2, "chunks": 2},
        },
        "custom": {
            "profile": "custom",
            "model": default_model,
            "summarize": {"chunk_chars": 8_000, "reduce_chars": 8_000},
            "concurrency": {"jobs": 1, "chunks": 1},
        },
    }
    return deepcopy(profiles[profile])


def validate_positive_int(value: Any, field_path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_path} must be a positive integer.")
    return value


def validate_profile_name(value: Any) -> str:
    profile = str(value)
    if profile not in PROFILE_NAMES:
        raise ValueError(f"Unknown farm profile: {profile}")
    return profile


def validate_model(value: Any) -> str:
    model = str(value).strip()
    if not model:
        raise ValueError("model must be a non-empty string.")
    return model


def reject_unknown_fields(data: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"Unknown {label} field(s): {joined}")


def normalize_config_data(data: dict[str, Any]) -> dict[str, Any]:
    reject_unknown_fields(data, TOP_LEVEL_FIELDS, "config")

    normalized: dict[str, Any] = {}
    if "profile" in data:
        normalized["profile"] = validate_profile_name(data["profile"])
    if "model" in data:
        normalized["model"] = validate_model(data["model"])
    if "summarize" in data:
        summarize = data["summarize"]
        if not isinstance(summarize, dict):
            raise ValueError("summarize must be an object.")
        reject_unknown_fields(summarize, SUMMARIZE_FIELDS, "summarize")
        normalized["summarize"] = {}
        if "chunk_chars" in summarize:
            normalized["summarize"]["chunk_chars"] = validate_positive_int(
                summarize["chunk_chars"], "summarize.chunk_chars"
            )
        if "reduce_chars" in summarize:
            normalized["summarize"]["reduce_chars"] = validate_positive_int(
                summarize["reduce_chars"], "summarize.reduce_chars"
            )
    if "concurrency" in data:
        concurrency = data["concurrency"]
        if not isinstance(concurrency, dict):
            raise ValueError("concurrency must be an object.")
        reject_unknown_fields(concurrency, CONCURRENCY_FIELDS, "concurrency")
        normalized["concurrency"] = {}
        if "jobs" in concurrency:
            normalized["concurrency"]["jobs"] = validate_positive_int(concurrency["jobs"], "concurrency.jobs")
        if "chunks" in concurrency:
            normalized["concurrency"]["chunks"] = validate_positive_int(concurrency["chunks"], "concurrency.chunks")
    return normalized


def read_config_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid farm config JSON at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Farm config at {path} must contain a JSON object.")
    return normalize_config_data(data)


def merge_config(target: dict[str, Any], update: dict[str, Any]) -> None:
    if "profile" in update:
        target["profile"] = update["profile"]
    if "model" in update:
        target["model"] = update["model"]
    if "summarize" in update:
        target["summarize"].update(update["summarize"])
    if "concurrency" in update:
        target["concurrency"].update(update["concurrency"])


def override_config(overrides: RuntimeOverrides) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if overrides.profile is not None:
        data["profile"] = validate_profile_name(overrides.profile)
    if overrides.model is not None:
        data["model"] = validate_model(overrides.model)

    summarize: dict[str, Any] = {}
    if overrides.chunk_chars is not None:
        summarize["chunk_chars"] = validate_positive_int(overrides.chunk_chars, "--chunk-chars")
    if overrides.reduce_chars is not None:
        summarize["reduce_chars"] = validate_positive_int(overrides.reduce_chars, "--reduce-chars")
    if summarize:
        data["summarize"] = summarize

    concurrency: dict[str, Any] = {}
    if overrides.parallel_jobs is not None:
        concurrency["jobs"] = validate_positive_int(overrides.parallel_jobs, "--parallel-jobs")
    if overrides.parallel_chunks is not None:
        concurrency["chunks"] = validate_positive_int(overrides.parallel_chunks, "--parallel-chunks")
    if concurrency:
        data["concurrency"] = concurrency
    return data


def field_names(data: dict[str, Any]) -> list[str]:
    names = []
    for key, value in data.items():
        if isinstance(value, dict):
            names.extend(f"{key}.{child}" for child in value)
        else:
            names.append(key)
    return sorted(names)


def discover_config_path(root: Path, explicit_path: Path | None) -> tuple[Path | None, bool]:
    if explicit_path is not None:
        return explicit_path, True
    discovered = root / CONFIG_FILE_NAME
    if discovered.exists():
        return discovered, False
    return None, False


def resolve_runtime_config(
    *,
    root: Path,
    default_model: str,
    config_path: Path | None = None,
    overrides: RuntimeOverrides | None = None,
) -> dict[str, Any]:
    overrides = overrides or RuntimeOverrides()
    override_data = override_config(overrides)
    config_source, explicit_config = discover_config_path(root, config_path)

    config_data: dict[str, Any] = {}
    if config_source is not None:
        if not config_source.exists():
            raise ValueError(f"Farm config file does not exist: {config_source}")
        config_data = read_config_file(config_source)

    selected_profile = (
        override_data.get("profile")
        or config_data.get("profile")
        or DEFAULT_PROFILE
    )
    resolved = built_in_profile(str(selected_profile), default_model)
    merge_config(resolved, config_data)
    merge_config(resolved, override_data)
    validate_resolved_config(resolved)

    provenance = {
        "default_profile": DEFAULT_PROFILE,
        "config_path": str(config_source) if config_source is not None else None,
        "config_explicit": explicit_config if config_source is not None else False,
        "config_fields": field_names(config_data),
        "cli_override_fields": field_names(override_data),
    }
    resolved["provenance"] = provenance
    return resolved


def validate_resolved_config(config: dict[str, Any]) -> None:
    validate_profile_name(config.get("profile"))
    validate_model(config.get("model"))
    summarize = config.get("summarize")
    if not isinstance(summarize, dict):
        raise ValueError("resolved summarize config must be an object.")
    validate_positive_int(summarize.get("chunk_chars"), "summarize.chunk_chars")
    validate_positive_int(summarize.get("reduce_chars"), "summarize.reduce_chars")
    concurrency = config.get("concurrency")
    if not isinstance(concurrency, dict):
        raise ValueError("resolved concurrency config must be an object.")
    validate_positive_int(concurrency.get("jobs"), "concurrency.jobs")
    validate_positive_int(concurrency.get("chunks"), "concurrency.chunks")


def model_is_explicit(runtime_config: dict[str, Any]) -> bool:
    provenance = runtime_config.get("provenance") or {}
    explicit_fields = set(provenance.get("config_fields") or []) | set(provenance.get("cli_override_fields") or [])
    return "model" in explicit_fields


def set_effective_model(runtime_config: dict[str, Any], model: str) -> dict[str, Any]:
    updated = deepcopy(runtime_config)
    updated["model"] = validate_model(model)
    return updated


def compact_runtime_config(runtime_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": runtime_config["profile"],
        "model": runtime_config["model"],
        "summarize": {
            "chunk_chars": runtime_config["summarize"]["chunk_chars"],
            "reduce_chars": runtime_config["summarize"]["reduce_chars"],
        },
        "concurrency": {
            "jobs": runtime_config["concurrency"]["jobs"],
            "chunks": runtime_config["concurrency"]["chunks"],
        },
    }
