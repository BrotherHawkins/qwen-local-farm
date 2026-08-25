from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.sift_farm_snippets import (
    DEFAULT_SNIPPET_MAX_CHARS,
    DEFAULT_SNIPPET_MAX_COUNT,
    DEFAULT_SNIPPET_MIN_COUNT,
    DEFAULT_SNIPPET_POLICY,
    SNIPPET_POLICIES,
)


CONFIG_FILE_NAME = ".sift-farm.json"
PROFILE_NAMES = ["cpu-small", "local-4gb", "local-8gb", "local-12gb", "local-24gb", "custom"]
DEFAULT_PROFILE = "local-8gb"
RESOURCE_MODES = {"auto", "gpu", "hybrid", "cpu"}
EFFECTIVE_RESOURCE_MODES = {"gpu", "hybrid", "cpu"}

TOP_LEVEL_FIELDS = {"profile", "resource_mode", "model", "summarize", "concurrency", "failure_policy", "discovery"}
CHUNK_STRATEGIES = {"character", "token"}
SUMMARIZE_FIELDS = {
    "chunk_strategy",
    "chunk_chars",
    "reduce_chars",
    "chunk_tokens",
    "reduce_tokens",
    "token_safety_margin",
    "preserve_heading_ancestry",
    "chunk_overlap_chars",
    "chunk_overlap_tokens",
    "snippet_policy",
    "snippet_count",
    "snippet_min_count",
    "snippet_max_count",
    "snippet_max_chars",
}
CONCURRENCY_FIELDS = {"jobs", "chunks"}
FAILURE_POLICY_FIELDS = {
    "max_attempts",
    "per_file_timeout_seconds",
    "chunk_max_attempts",
    "reduce_max_attempts",
}
DISCOVERY_FIELDS = {"include", "exclude"}
DEFAULT_CHUNK_STRATEGY = "character"
DEFAULT_TOKEN_SAFETY_MARGIN = 0.10
DEFAULT_TOKEN_PROMPT_RESERVE = 1_024
DEFAULT_SUMMARIZE_TOKEN_BUDGET_CAP = 4_096
DEFAULT_PRESERVE_HEADING_ANCESTRY = True
DEFAULT_CHUNK_OVERLAP_CHARS = 0
DEFAULT_CHUNK_OVERLAP_TOKENS = 0
DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_PER_FILE_TIMEOUT_SECONDS = 600
DEFAULT_CHUNK_MAX_ATTEMPTS = 2
DEFAULT_REDUCE_MAX_ATTEMPTS = 2


@dataclass(frozen=True)
class RuntimeOverrides:
    profile: str | None = None
    resource_mode: str | None = None
    model: str | None = None
    chunk_strategy: str | None = None
    chunk_chars: int | None = None
    reduce_chars: int | None = None
    chunk_tokens: int | None = None
    reduce_tokens: int | None = None
    token_safety_margin: float | None = None
    preserve_heading_ancestry: bool | None = None
    chunk_overlap_chars: int | None = None
    chunk_overlap_tokens: int | None = None
    snippets: str | None = None
    snippet_policy: str | None = None
    snippet_count: int | None = None
    snippet_min_count: int | None = None
    snippet_max_count: int | None = None
    snippet_max_chars: int | None = None
    parallel_jobs: int | None = None
    parallel_chunks: int | None = None
    max_attempts: int | None = None
    per_file_timeout_seconds: int | None = None
    chunk_max_attempts: int | None = None
    reduce_max_attempts: int | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


def default_failure_policy() -> dict[str, int]:
    return {
        "max_attempts": DEFAULT_MAX_ATTEMPTS,
        "per_file_timeout_seconds": DEFAULT_PER_FILE_TIMEOUT_SECONDS,
        "chunk_max_attempts": DEFAULT_CHUNK_MAX_ATTEMPTS,
        "reduce_max_attempts": DEFAULT_REDUCE_MAX_ATTEMPTS,
    }


def default_discovery() -> dict[str, list[str]]:
    return {
        "include": [],
        "exclude": [],
    }


def default_snippet_fields() -> dict[str, Any]:
    return {
        "snippet_policy": DEFAULT_SNIPPET_POLICY,
        "snippet_count": None,
        "snippet_min_count": DEFAULT_SNIPPET_MIN_COUNT,
        "snippet_max_count": DEFAULT_SNIPPET_MAX_COUNT,
        "snippet_max_chars": DEFAULT_SNIPPET_MAX_CHARS,
    }


def default_chunk_context_fields() -> dict[str, Any]:
    return {
        "preserve_heading_ancestry": DEFAULT_PRESERVE_HEADING_ANCESTRY,
        "chunk_overlap_chars": DEFAULT_CHUNK_OVERLAP_CHARS,
        "chunk_overlap_tokens": DEFAULT_CHUNK_OVERLAP_TOKENS,
    }


def built_in_profile(profile: str, default_model: str) -> dict[str, Any]:
    if profile not in PROFILE_NAMES:
        raise ValueError(f"Unknown farm profile: {profile}")

    profiles: dict[str, dict[str, Any]] = {
        "cpu-small": {
            "profile": "cpu-small",
            "resource_mode": "cpu",
            "model": default_model,
            "summarize": {
                "chunk_strategy": DEFAULT_CHUNK_STRATEGY,
                "chunk_chars": 4_000,
                "reduce_chars": 4_000,
                "token_safety_margin": DEFAULT_TOKEN_SAFETY_MARGIN,
                "preserve_heading_ancestry": DEFAULT_PRESERVE_HEADING_ANCESTRY,
                "chunk_overlap_chars": DEFAULT_CHUNK_OVERLAP_CHARS,
                "chunk_overlap_tokens": DEFAULT_CHUNK_OVERLAP_TOKENS,
                "snippet_policy": DEFAULT_SNIPPET_POLICY,
                "snippet_count": None,
                "snippet_min_count": DEFAULT_SNIPPET_MIN_COUNT,
                "snippet_max_count": DEFAULT_SNIPPET_MAX_COUNT,
                "snippet_max_chars": DEFAULT_SNIPPET_MAX_CHARS,
            },
            "concurrency": {"jobs": 1, "chunks": 1},
            "failure_policy": default_failure_policy(),
            "discovery": default_discovery(),
        },
        "local-4gb": {
            "profile": "local-4gb",
            "resource_mode": "auto",
            "model": default_model,
            "summarize": {
                "chunk_strategy": DEFAULT_CHUNK_STRATEGY,
                "chunk_chars": 6_000,
                "reduce_chars": 6_000,
                "token_safety_margin": DEFAULT_TOKEN_SAFETY_MARGIN,
                "preserve_heading_ancestry": DEFAULT_PRESERVE_HEADING_ANCESTRY,
                "chunk_overlap_chars": DEFAULT_CHUNK_OVERLAP_CHARS,
                "chunk_overlap_tokens": DEFAULT_CHUNK_OVERLAP_TOKENS,
                "snippet_policy": DEFAULT_SNIPPET_POLICY,
                "snippet_count": None,
                "snippet_min_count": DEFAULT_SNIPPET_MIN_COUNT,
                "snippet_max_count": DEFAULT_SNIPPET_MAX_COUNT,
                "snippet_max_chars": DEFAULT_SNIPPET_MAX_CHARS,
            },
            "concurrency": {"jobs": 1, "chunks": 1},
            "failure_policy": default_failure_policy(),
            "discovery": default_discovery(),
        },
        "local-8gb": {
            "profile": "local-8gb",
            "resource_mode": "auto",
            "model": default_model,
            "summarize": {
                "chunk_strategy": DEFAULT_CHUNK_STRATEGY,
                "chunk_chars": 8_000,
                "reduce_chars": 8_000,
                "token_safety_margin": DEFAULT_TOKEN_SAFETY_MARGIN,
                "preserve_heading_ancestry": DEFAULT_PRESERVE_HEADING_ANCESTRY,
                "chunk_overlap_chars": DEFAULT_CHUNK_OVERLAP_CHARS,
                "chunk_overlap_tokens": DEFAULT_CHUNK_OVERLAP_TOKENS,
                "snippet_policy": DEFAULT_SNIPPET_POLICY,
                "snippet_count": None,
                "snippet_min_count": DEFAULT_SNIPPET_MIN_COUNT,
                "snippet_max_count": DEFAULT_SNIPPET_MAX_COUNT,
                "snippet_max_chars": DEFAULT_SNIPPET_MAX_CHARS,
            },
            "concurrency": {"jobs": 1, "chunks": 1},
            "failure_policy": default_failure_policy(),
            "discovery": default_discovery(),
        },
        "local-12gb": {
            "profile": "local-12gb",
            "resource_mode": "auto",
            "model": default_model,
            "summarize": {
                "chunk_strategy": DEFAULT_CHUNK_STRATEGY,
                "chunk_chars": 12_000,
                "reduce_chars": 12_000,
                "token_safety_margin": DEFAULT_TOKEN_SAFETY_MARGIN,
                "preserve_heading_ancestry": DEFAULT_PRESERVE_HEADING_ANCESTRY,
                "chunk_overlap_chars": DEFAULT_CHUNK_OVERLAP_CHARS,
                "chunk_overlap_tokens": DEFAULT_CHUNK_OVERLAP_TOKENS,
                "snippet_policy": DEFAULT_SNIPPET_POLICY,
                "snippet_count": None,
                "snippet_min_count": DEFAULT_SNIPPET_MIN_COUNT,
                "snippet_max_count": DEFAULT_SNIPPET_MAX_COUNT,
                "snippet_max_chars": DEFAULT_SNIPPET_MAX_CHARS,
            },
            "concurrency": {"jobs": 1, "chunks": 1},
            "failure_policy": default_failure_policy(),
            "discovery": default_discovery(),
        },
        "local-24gb": {
            "profile": "local-24gb",
            "resource_mode": "auto",
            "model": default_model,
            "summarize": {
                "chunk_strategy": DEFAULT_CHUNK_STRATEGY,
                "chunk_chars": 20_000,
                "reduce_chars": 20_000,
                "token_safety_margin": DEFAULT_TOKEN_SAFETY_MARGIN,
                "preserve_heading_ancestry": DEFAULT_PRESERVE_HEADING_ANCESTRY,
                "chunk_overlap_chars": DEFAULT_CHUNK_OVERLAP_CHARS,
                "chunk_overlap_tokens": DEFAULT_CHUNK_OVERLAP_TOKENS,
                "snippet_policy": DEFAULT_SNIPPET_POLICY,
                "snippet_count": None,
                "snippet_min_count": DEFAULT_SNIPPET_MIN_COUNT,
                "snippet_max_count": DEFAULT_SNIPPET_MAX_COUNT,
                "snippet_max_chars": DEFAULT_SNIPPET_MAX_CHARS,
            },
            "concurrency": {"jobs": 2, "chunks": 2},
            "failure_policy": default_failure_policy(),
            "discovery": default_discovery(),
        },
        "custom": {
            "profile": "custom",
            "resource_mode": "auto",
            "model": default_model,
            "summarize": {
                "chunk_strategy": DEFAULT_CHUNK_STRATEGY,
                "chunk_chars": 8_000,
                "reduce_chars": 8_000,
                "token_safety_margin": DEFAULT_TOKEN_SAFETY_MARGIN,
                "preserve_heading_ancestry": DEFAULT_PRESERVE_HEADING_ANCESTRY,
                "chunk_overlap_chars": DEFAULT_CHUNK_OVERLAP_CHARS,
                "chunk_overlap_tokens": DEFAULT_CHUNK_OVERLAP_TOKENS,
                "snippet_policy": DEFAULT_SNIPPET_POLICY,
                "snippet_count": None,
                "snippet_min_count": DEFAULT_SNIPPET_MIN_COUNT,
                "snippet_max_count": DEFAULT_SNIPPET_MAX_COUNT,
                "snippet_max_chars": DEFAULT_SNIPPET_MAX_CHARS,
            },
            "concurrency": {"jobs": 1, "chunks": 1},
            "failure_policy": default_failure_policy(),
            "discovery": default_discovery(),
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


def validate_resource_mode(value: Any, field_path: str = "resource_mode") -> str:
    mode = str(value).strip().lower()
    if mode not in RESOURCE_MODES:
        allowed = ", ".join(sorted(RESOURCE_MODES))
        raise ValueError(f"{field_path} must be one of: {allowed}.")
    return mode


def validate_model(value: Any) -> str:
    model = str(value).strip()
    if not model:
        raise ValueError("model must be a non-empty string.")
    return model


def validate_pattern_list(value: Any, field_path: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_path} must be an array of strings.")
    patterns: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{field_path}[{index}] must be a string.")
        pattern = item.strip()
        if not pattern:
            raise ValueError(f"{field_path}[{index}] must be a non-empty string.")
        patterns.append(pattern)
    return patterns


def validate_chunk_strategy(value: Any) -> str:
    strategy = str(value).strip().lower()
    if strategy not in CHUNK_STRATEGIES:
        allowed = ", ".join(sorted(CHUNK_STRATEGIES))
        raise ValueError(f"summarize.chunk_strategy must be one of: {allowed}.")
    return strategy


def validate_non_negative_int(value: Any, field_path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_path} must be a non-negative integer.")
    return value


def validate_bool(value: Any, field_path: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_path} must be a boolean.")
    return value


def validate_snippet_policy(value: Any) -> str:
    policy = str(value).strip().lower()
    if policy not in SNIPPET_POLICIES:
        allowed = ", ".join(sorted(SNIPPET_POLICIES))
        raise ValueError(f"summarize.snippet_policy must be one of: {allowed}.")
    return policy


def validate_snippet_count(value: Any, field_path: str) -> int | None:
    if value is None:
        return None
    return validate_non_negative_int(value, field_path)


def parse_snippets_override(value: str) -> dict[str, Any]:
    text = value.strip().lower()
    if text in {"off", "none", "false", "0"}:
        return {"snippet_policy": "off", "snippet_count": None}
    if text == "auto":
        return {"snippet_policy": "auto", "snippet_count": None}
    try:
        count = int(text)
    except ValueError as exc:
        raise ValueError("--snippets must be off, auto, 0, or a non-negative integer.") from exc
    if count < 0:
        raise ValueError("--snippets must be off, auto, 0, or a non-negative integer.")
    if count == 0:
        return {"snippet_policy": "off", "snippet_count": None}
    return {"snippet_policy": "fixed", "snippet_count": count}


def validate_snippet_settings(summarize: dict[str, Any]) -> None:
    policy = validate_snippet_policy(summarize.get("snippet_policy", DEFAULT_SNIPPET_POLICY))
    count = validate_snippet_count(summarize.get("snippet_count"), "summarize.snippet_count")
    min_count = validate_non_negative_int(
        summarize.get("snippet_min_count", DEFAULT_SNIPPET_MIN_COUNT),
        "summarize.snippet_min_count",
    )
    max_count = validate_non_negative_int(
        summarize.get("snippet_max_count", DEFAULT_SNIPPET_MAX_COUNT),
        "summarize.snippet_max_count",
    )
    validate_positive_int(
        summarize.get("snippet_max_chars", DEFAULT_SNIPPET_MAX_CHARS),
        "summarize.snippet_max_chars",
    )
    if max_count < min_count:
        raise ValueError("summarize.snippet_max_count must be greater than or equal to snippet_min_count.")
    if policy == "fixed" and count is None:
        raise ValueError("summarize.snippet_count is required when snippet_policy is fixed.")
    if policy in {"auto", "off"} and count is not None:
        raise ValueError("summarize.snippet_count must be null when snippet_policy is auto or off.")


def validate_safety_margin(value: Any, field_path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_path} must be a number from 0 to 0.75.")
    margin = float(value)
    if margin < 0 or margin > 0.75:
        raise ValueError(f"{field_path} must be a number from 0 to 0.75.")
    return margin


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
    if "resource_mode" in data:
        normalized["resource_mode"] = validate_resource_mode(data["resource_mode"])
    if "model" in data:
        normalized["model"] = validate_model(data["model"])
    if "summarize" in data:
        summarize = data["summarize"]
        if not isinstance(summarize, dict):
            raise ValueError("summarize must be an object.")
        reject_unknown_fields(summarize, SUMMARIZE_FIELDS, "summarize")
        normalized["summarize"] = {}
        if "chunk_strategy" in summarize:
            normalized["summarize"]["chunk_strategy"] = validate_chunk_strategy(summarize["chunk_strategy"])
        if "chunk_chars" in summarize:
            normalized["summarize"]["chunk_chars"] = validate_positive_int(
                summarize["chunk_chars"], "summarize.chunk_chars"
            )
        if "reduce_chars" in summarize:
            normalized["summarize"]["reduce_chars"] = validate_positive_int(
                summarize["reduce_chars"], "summarize.reduce_chars"
            )
        if "chunk_tokens" in summarize:
            normalized["summarize"]["chunk_tokens"] = validate_positive_int(
                summarize["chunk_tokens"], "summarize.chunk_tokens"
            )
        if "reduce_tokens" in summarize:
            normalized["summarize"]["reduce_tokens"] = validate_positive_int(
                summarize["reduce_tokens"], "summarize.reduce_tokens"
            )
        if "token_safety_margin" in summarize:
            normalized["summarize"]["token_safety_margin"] = validate_safety_margin(
                summarize["token_safety_margin"], "summarize.token_safety_margin"
            )
        if "preserve_heading_ancestry" in summarize:
            normalized["summarize"]["preserve_heading_ancestry"] = validate_bool(
                summarize["preserve_heading_ancestry"], "summarize.preserve_heading_ancestry"
            )
        if "chunk_overlap_chars" in summarize:
            normalized["summarize"]["chunk_overlap_chars"] = validate_non_negative_int(
                summarize["chunk_overlap_chars"], "summarize.chunk_overlap_chars"
            )
        if "chunk_overlap_tokens" in summarize:
            normalized["summarize"]["chunk_overlap_tokens"] = validate_non_negative_int(
                summarize["chunk_overlap_tokens"], "summarize.chunk_overlap_tokens"
            )
        if "snippet_policy" in summarize:
            normalized["summarize"]["snippet_policy"] = validate_snippet_policy(summarize["snippet_policy"])
        if "snippet_count" in summarize:
            normalized["summarize"]["snippet_count"] = validate_snippet_count(
                summarize["snippet_count"], "summarize.snippet_count"
            )
        if "snippet_min_count" in summarize:
            normalized["summarize"]["snippet_min_count"] = validate_non_negative_int(
                summarize["snippet_min_count"], "summarize.snippet_min_count"
            )
        if "snippet_max_count" in summarize:
            normalized["summarize"]["snippet_max_count"] = validate_non_negative_int(
                summarize["snippet_max_count"], "summarize.snippet_max_count"
            )
        if "snippet_max_chars" in summarize:
            normalized["summarize"]["snippet_max_chars"] = validate_positive_int(
                summarize["snippet_max_chars"], "summarize.snippet_max_chars"
            )
        validate_snippet_settings({**default_snippet_fields(), **normalized["summarize"]})
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
    if "failure_policy" in data:
        failure_policy = data["failure_policy"]
        if not isinstance(failure_policy, dict):
            raise ValueError("failure_policy must be an object.")
        reject_unknown_fields(failure_policy, FAILURE_POLICY_FIELDS, "failure_policy")
        normalized["failure_policy"] = {}
        for field in sorted(FAILURE_POLICY_FIELDS):
            if field in failure_policy:
                normalized["failure_policy"][field] = validate_positive_int(
                    failure_policy[field],
                    f"failure_policy.{field}",
                )
    if "discovery" in data:
        discovery = data["discovery"]
        if not isinstance(discovery, dict):
            raise ValueError("discovery must be an object.")
        reject_unknown_fields(discovery, DISCOVERY_FIELDS, "discovery")
        normalized["discovery"] = {}
        if "include" in discovery:
            normalized["discovery"]["include"] = validate_pattern_list(discovery["include"], "discovery.include")
        if "exclude" in discovery:
            normalized["discovery"]["exclude"] = validate_pattern_list(discovery["exclude"], "discovery.exclude")
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
    if "resource_mode" in update:
        target["resource_mode"] = update["resource_mode"]
    if "model" in update:
        target["model"] = update["model"]
    if "summarize" in update:
        target["summarize"].update(update["summarize"])
    if "concurrency" in update:
        target["concurrency"].update(update["concurrency"])
    if "failure_policy" in update:
        target["failure_policy"].update(update["failure_policy"])
    if "discovery" in update:
        target.setdefault("discovery", default_discovery())
        if "include" in update["discovery"]:
            target["discovery"]["include"].extend(update["discovery"]["include"])
        if "exclude" in update["discovery"]:
            target["discovery"]["exclude"].extend(update["discovery"]["exclude"])


def override_config(overrides: RuntimeOverrides) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if overrides.profile is not None:
        data["profile"] = validate_profile_name(overrides.profile)
    if overrides.resource_mode is not None:
        data["resource_mode"] = validate_resource_mode(overrides.resource_mode, "--resource-mode")
    if overrides.model is not None:
        data["model"] = validate_model(overrides.model)

    summarize: dict[str, Any] = {}
    if overrides.chunk_strategy is not None:
        summarize["chunk_strategy"] = validate_chunk_strategy(overrides.chunk_strategy)
    if overrides.chunk_chars is not None:
        summarize["chunk_chars"] = validate_positive_int(overrides.chunk_chars, "--chunk-chars")
    if overrides.reduce_chars is not None:
        summarize["reduce_chars"] = validate_positive_int(overrides.reduce_chars, "--reduce-chars")
    if overrides.chunk_tokens is not None:
        summarize["chunk_tokens"] = validate_positive_int(overrides.chunk_tokens, "--chunk-tokens")
    if overrides.reduce_tokens is not None:
        summarize["reduce_tokens"] = validate_positive_int(overrides.reduce_tokens, "--reduce-tokens")
    if overrides.token_safety_margin is not None:
        summarize["token_safety_margin"] = validate_safety_margin(
            overrides.token_safety_margin, "--token-safety-margin"
        )
    if overrides.preserve_heading_ancestry is not None:
        summarize["preserve_heading_ancestry"] = validate_bool(
            overrides.preserve_heading_ancestry,
            "--preserve-heading-ancestry",
        )
    if overrides.chunk_overlap_chars is not None:
        summarize["chunk_overlap_chars"] = validate_non_negative_int(
            overrides.chunk_overlap_chars,
            "--chunk-overlap-chars",
        )
    if overrides.chunk_overlap_tokens is not None:
        summarize["chunk_overlap_tokens"] = validate_non_negative_int(
            overrides.chunk_overlap_tokens,
            "--chunk-overlap-tokens",
        )
    if overrides.snippets is not None:
        summarize.update(parse_snippets_override(overrides.snippets))
    if overrides.snippet_policy is not None:
        summarize["snippet_policy"] = validate_snippet_policy(overrides.snippet_policy)
    if overrides.snippet_count is not None:
        summarize["snippet_count"] = validate_non_negative_int(overrides.snippet_count, "--snippets")
    if overrides.snippet_min_count is not None:
        summarize["snippet_min_count"] = validate_non_negative_int(
            overrides.snippet_min_count, "--snippet-min-count"
        )
    if overrides.snippet_max_count is not None:
        summarize["snippet_max_count"] = validate_non_negative_int(
            overrides.snippet_max_count, "--snippet-max-count"
        )
    if overrides.snippet_max_chars is not None:
        summarize["snippet_max_chars"] = validate_positive_int(overrides.snippet_max_chars, "--snippet-max-chars")
    if summarize:
        data["summarize"] = summarize

    concurrency: dict[str, Any] = {}
    if overrides.parallel_jobs is not None:
        concurrency["jobs"] = validate_positive_int(overrides.parallel_jobs, "--parallel-jobs")
    if overrides.parallel_chunks is not None:
        concurrency["chunks"] = validate_positive_int(overrides.parallel_chunks, "--parallel-chunks")
    if concurrency:
        data["concurrency"] = concurrency

    failure_policy: dict[str, Any] = {}
    if overrides.max_attempts is not None:
        failure_policy["max_attempts"] = validate_positive_int(overrides.max_attempts, "--max-attempts")
    if overrides.per_file_timeout_seconds is not None:
        failure_policy["per_file_timeout_seconds"] = validate_positive_int(
            overrides.per_file_timeout_seconds,
            "--per-file-timeout-seconds",
        )
    if overrides.chunk_max_attempts is not None:
        failure_policy["chunk_max_attempts"] = validate_positive_int(
            overrides.chunk_max_attempts,
            "--chunk-max-attempts",
        )
    if overrides.reduce_max_attempts is not None:
        failure_policy["reduce_max_attempts"] = validate_positive_int(
            overrides.reduce_max_attempts,
            "--reduce-max-attempts",
        )
    if failure_policy:
        data["failure_policy"] = failure_policy
    discovery: dict[str, Any] = {}
    if overrides.include:
        discovery["include"] = validate_pattern_list(list(overrides.include), "--include")
    if overrides.exclude:
        discovery["exclude"] = validate_pattern_list(list(overrides.exclude), "--exclude")
    if discovery:
        data["discovery"] = discovery
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
    if "resource_mode" in config:
        resource_mode = config["resource_mode"]
        if isinstance(resource_mode, dict):
            requested = resource_mode.get("requested")
            effective = resource_mode.get("effective")
            validate_resource_mode(requested)
            if str(effective) not in EFFECTIVE_RESOURCE_MODES:
                allowed = ", ".join(sorted(EFFECTIVE_RESOURCE_MODES))
                raise ValueError(f"resource_mode.effective must be one of: {allowed}.")
        else:
            validate_resource_mode(resource_mode)
    validate_model(config.get("model"))
    summarize = config.get("summarize")
    if not isinstance(summarize, dict):
        raise ValueError("resolved summarize config must be an object.")
    validate_chunk_strategy(summarize.get("chunk_strategy", DEFAULT_CHUNK_STRATEGY))
    validate_positive_int(summarize.get("chunk_chars"), "summarize.chunk_chars")
    validate_positive_int(summarize.get("reduce_chars"), "summarize.reduce_chars")
    if summarize.get("chunk_tokens") is not None:
        validate_positive_int(summarize.get("chunk_tokens"), "summarize.chunk_tokens")
    if summarize.get("reduce_tokens") is not None:
        validate_positive_int(summarize.get("reduce_tokens"), "summarize.reduce_tokens")
    validate_safety_margin(
        summarize.get("token_safety_margin", DEFAULT_TOKEN_SAFETY_MARGIN),
        "summarize.token_safety_margin",
    )
    validate_bool(
        summarize.get("preserve_heading_ancestry", DEFAULT_PRESERVE_HEADING_ANCESTRY),
        "summarize.preserve_heading_ancestry",
    )
    validate_non_negative_int(
        summarize.get("chunk_overlap_chars", DEFAULT_CHUNK_OVERLAP_CHARS),
        "summarize.chunk_overlap_chars",
    )
    validate_non_negative_int(
        summarize.get("chunk_overlap_tokens", DEFAULT_CHUNK_OVERLAP_TOKENS),
        "summarize.chunk_overlap_tokens",
    )
    validate_snippet_settings(summarize)
    concurrency = config.get("concurrency")
    if not isinstance(concurrency, dict):
        raise ValueError("resolved concurrency config must be an object.")
    validate_positive_int(concurrency.get("jobs"), "concurrency.jobs")
    validate_positive_int(concurrency.get("chunks"), "concurrency.chunks")
    failure_policy = config.get("failure_policy")
    if not isinstance(failure_policy, dict):
        raise ValueError("resolved failure_policy config must be an object.")
    reject_unknown_fields(failure_policy, FAILURE_POLICY_FIELDS, "failure_policy")
    for field in sorted(FAILURE_POLICY_FIELDS):
        validate_positive_int(failure_policy.get(field), f"failure_policy.{field}")
    discovery = config.get("discovery")
    if not isinstance(discovery, dict):
        raise ValueError("resolved discovery config must be an object.")
    reject_unknown_fields(discovery, DISCOVERY_FIELDS, "discovery")
    validate_pattern_list(discovery.get("include", []), "discovery.include")
    validate_pattern_list(discovery.get("exclude", []), "discovery.exclude")


def model_is_explicit(runtime_config: dict[str, Any]) -> bool:
    provenance = runtime_config.get("provenance") or {}
    explicit_fields = set(provenance.get("config_fields") or []) | set(provenance.get("cli_override_fields") or [])
    return "model" in explicit_fields


def set_effective_model(runtime_config: dict[str, Any], model: str) -> dict[str, Any]:
    updated = deepcopy(runtime_config)
    updated["model"] = validate_model(model)
    return updated


def agent_context_tokens(agent: dict[str, Any]) -> int | None:
    options = agent.get("options") or {}
    if not isinstance(options, dict):
        return None
    num_ctx = options.get("num_ctx")
    if isinstance(num_ctx, bool) or not isinstance(num_ctx, int) or num_ctx <= 0:
        return None
    return num_ctx


def derive_token_budget(num_ctx: int, safety_margin: float) -> int:
    after_margin = int(num_ctx * (1 - safety_margin))
    return max(1, min(DEFAULT_SUMMARIZE_TOKEN_BUDGET_CAP, after_margin - DEFAULT_TOKEN_PROMPT_RESERVE))


def finalize_runtime_config_for_agent(runtime_config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(runtime_config)
    updated.setdefault("discovery", default_discovery())
    updated["model_metadata"] = deepcopy(agent.get("model_metadata") or {})
    updated = resolve_resource_mode_for_agent(updated, agent)
    summarize = updated["summarize"]
    summarize.setdefault("chunk_strategy", DEFAULT_CHUNK_STRATEGY)
    summarize.setdefault("token_safety_margin", DEFAULT_TOKEN_SAFETY_MARGIN)
    summarize.update({**default_chunk_context_fields(), **summarize})
    summarize.update({**default_snippet_fields(), **summarize})
    if summarize["chunk_strategy"] == "token":
        if summarize.get("chunk_tokens") is None or summarize.get("reduce_tokens") is None:
            num_ctx = agent_context_tokens(agent)
            if num_ctx is None:
                raise ValueError("Token-aware chunking requires agent options.num_ctx or explicit token budgets.")
            budget = derive_token_budget(num_ctx, float(summarize["token_safety_margin"]))
            summarize.setdefault("chunk_tokens", budget)
            summarize.setdefault("reduce_tokens", budget)
    validate_resolved_config(updated)
    return updated


def agent_options(agent: dict[str, Any]) -> dict[str, Any]:
    options = agent.get("options")
    return options if isinstance(options, dict) else {}


def agent_forces_cpu(agent: dict[str, Any]) -> bool:
    return agent_options(agent).get("num_gpu") == 0


def agent_uses_partial_gpu(agent: dict[str, Any]) -> bool:
    num_gpu = agent_options(agent).get("num_gpu")
    return isinstance(num_gpu, int) and not isinstance(num_gpu, bool) and num_gpu > 0


def resource_mode_source(runtime_config: dict[str, Any]) -> str:
    provenance = runtime_config.get("provenance") or {}
    cli_fields = set(provenance.get("cli_override_fields") or [])
    config_fields = set(provenance.get("config_fields") or [])
    if "resource_mode" in cli_fields:
        return "cli"
    if "resource_mode" in config_fields:
        return "config"
    return "profile"


def requested_resource_mode(runtime_config: dict[str, Any]) -> str:
    current = runtime_config.get("resource_mode", "auto")
    if isinstance(current, dict):
        current = current.get("requested", "auto")
    return validate_resource_mode(current)


def resolve_effective_resource_mode(requested: str, profile: str, agent: dict[str, Any]) -> tuple[str, str]:
    if requested == "cpu":
        return "cpu", "Requested cpu mode forces CPU/RAM placement with num_gpu 0."
    if requested in {"gpu", "hybrid"}:
        if agent_forces_cpu(agent):
            agent_id = str(agent.get("id") or "")
            raise ValueError(
                f"Resource mode `{requested}` conflicts with selected agent `{agent_id}`, "
                "which explicitly sets options.num_gpu to 0. Use --resource-mode cpu/auto or choose a GPU-capable agent."
            )
        if requested == "gpu":
            return "gpu", "Requested gpu mode allows Ollama to use GPU placement for the selected agent."
        return "hybrid", "Requested hybrid mode allows partial GPU offload or Ollama-managed fallback."

    if profile == "cpu-small":
        return "cpu", "Auto resolved to cpu because the selected profile is cpu-small."
    if agent_forces_cpu(agent):
        agent_id = str(agent.get("id") or "")
        return "cpu", f"Auto resolved to cpu because selected agent `{agent_id}` sets options.num_gpu to 0."
    if agent_uses_partial_gpu(agent):
        agent_id = str(agent.get("id") or "")
        return "hybrid", f"Auto resolved to hybrid because selected agent `{agent_id}` sets positive options.num_gpu."
    return "gpu", f"Auto resolved to gpu because profile `{profile}` can use GPU placement and the agent does not force CPU."


def resolve_resource_mode_for_agent(runtime_config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(runtime_config)
    requested = requested_resource_mode(updated)
    profile = validate_profile_name(updated.get("profile"))
    effective, reason = resolve_effective_resource_mode(requested, profile, agent)
    source = resource_mode_source(updated)
    override: dict[str, Any] | None = None
    if effective == "cpu":
        agent.setdefault("options", {})
        if not isinstance(agent["options"], dict):
            agent["options"] = {}
        previous = agent["options"].get("num_gpu")
        agent["options"]["num_gpu"] = 0
        override = {"path": "agent.options.num_gpu", "before": previous, "after": 0}
    updated["resource_mode"] = {
        "requested": requested,
        "effective": effective,
        "source": source,
        "reason": reason,
        "agent_option_override": override,
    }
    return updated


def compact_runtime_config(runtime_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": runtime_config["profile"],
        "resource_mode": runtime_config.get("resource_mode"),
        "model": runtime_config["model"],
        "model_metadata": deepcopy(runtime_config.get("model_metadata") or {}),
        "summarize": {
            "chunk_strategy": runtime_config["summarize"].get("chunk_strategy", DEFAULT_CHUNK_STRATEGY),
            "chunk_chars": runtime_config["summarize"]["chunk_chars"],
            "reduce_chars": runtime_config["summarize"]["reduce_chars"],
            "chunk_tokens": runtime_config["summarize"].get("chunk_tokens"),
            "reduce_tokens": runtime_config["summarize"].get("reduce_tokens"),
            "token_safety_margin": runtime_config["summarize"].get(
                "token_safety_margin", DEFAULT_TOKEN_SAFETY_MARGIN
            ),
            "preserve_heading_ancestry": runtime_config["summarize"].get(
                "preserve_heading_ancestry", DEFAULT_PRESERVE_HEADING_ANCESTRY
            ),
            "chunk_overlap_chars": runtime_config["summarize"].get(
                "chunk_overlap_chars", DEFAULT_CHUNK_OVERLAP_CHARS
            ),
            "chunk_overlap_tokens": runtime_config["summarize"].get(
                "chunk_overlap_tokens", DEFAULT_CHUNK_OVERLAP_TOKENS
            ),
            "snippet_policy": runtime_config["summarize"].get("snippet_policy", DEFAULT_SNIPPET_POLICY),
            "snippet_count": runtime_config["summarize"].get("snippet_count"),
            "snippet_min_count": runtime_config["summarize"].get(
                "snippet_min_count", DEFAULT_SNIPPET_MIN_COUNT
            ),
            "snippet_max_count": runtime_config["summarize"].get(
                "snippet_max_count", DEFAULT_SNIPPET_MAX_COUNT
            ),
            "snippet_max_chars": runtime_config["summarize"].get(
                "snippet_max_chars", DEFAULT_SNIPPET_MAX_CHARS
            ),
        },
        "concurrency": {
            "jobs": runtime_config["concurrency"]["jobs"],
            "chunks": runtime_config["concurrency"]["chunks"],
        },
        "failure_policy": {
            "max_attempts": runtime_config["failure_policy"]["max_attempts"],
            "per_file_timeout_seconds": runtime_config["failure_policy"]["per_file_timeout_seconds"],
            "chunk_max_attempts": runtime_config["failure_policy"]["chunk_max_attempts"],
            "reduce_max_attempts": runtime_config["failure_policy"]["reduce_max_attempts"],
        },
        "discovery": {
            "include": list(runtime_config.get("discovery", {}).get("include", [])),
            "exclude": list(runtime_config.get("discovery", {}).get("exclude", [])),
        },
    }
