from __future__ import annotations

from copy import deepcopy
from typing import Any


BACKENDS = {"ollama"}
MODEL_FAMILIES = {"qwen", "llama", "mistral", "gemma", "phi", "deepseek", "unknown"}
SUPPORT_LEVELS = {"tested", "experimental", "unknown"}
TOKENIZER_STRATEGIES = {"huggingface", "none", "unknown"}

QWEN_TOKENIZERS = {
    "qwen3.5:4b": "Qwen/Qwen3.5-4B",
    "qwen3:4b": "Qwen/Qwen3-4B",
    "qwen3:8b": "Qwen/Qwen3-8B",
    "qwen3:14b": "Qwen/Qwen3-14B",
}


def validate_metadata_string(value: Any, field_path: str, allowed: set[str]) -> str:
    text = str(value).strip().lower()
    if text not in allowed:
        raise ValueError(f"{field_path} must be one of: {', '.join(sorted(allowed))}.")
    return text


def validate_backend(value: Any) -> str:
    return validate_metadata_string(value, "backend", BACKENDS)


def validate_model_family(value: Any) -> str:
    return validate_metadata_string(value, "model_family", MODEL_FAMILIES)


def validate_support(value: Any) -> str:
    return validate_metadata_string(value, "support", SUPPORT_LEVELS)


def validate_tokenizer_strategy(value: Any) -> str:
    return validate_metadata_string(value, "tokenizer.strategy", TOKENIZER_STRATEGIES)


def infer_model_family(model: str) -> str:
    model_name = model.lower()
    if model_name.startswith("qwen"):
        return "qwen"
    if model_name.startswith("llama"):
        return "llama"
    if model_name.startswith("mistral"):
        return "mistral"
    if model_name.startswith("gemma"):
        return "gemma"
    if model_name.startswith("phi"):
        return "phi"
    if model_name.startswith("deepseek"):
        return "deepseek"
    return "unknown"


def default_support(model: str, family: str) -> str:
    if family == "qwen" and model in QWEN_TOKENIZERS:
        return "tested"
    if family == "unknown":
        return "unknown"
    return "experimental"


def inferred_tokenizer(model: str, family: str) -> dict[str, Any]:
    tokenizer_id = QWEN_TOKENIZERS.get(model)
    if family == "qwen" and tokenizer_id:
        return {
            "strategy": "huggingface",
            "id": tokenizer_id,
            "exact": True,
        }
    return {
        "strategy": "unknown" if family == "unknown" else "none",
        "id": None,
        "exact": False,
    }


def normalize_tokenizer(value: Any, *, model: str, family: str) -> dict[str, Any]:
    if value is None:
        return inferred_tokenizer(model, family)
    if not isinstance(value, dict):
        raise ValueError("tokenizer must be an object.")

    tokenizer = inferred_tokenizer(model, family)
    tokenizer.update(deepcopy(value))
    tokenizer["strategy"] = validate_tokenizer_strategy(tokenizer.get("strategy", "unknown"))

    tokenizer_id = tokenizer.get("id")
    if tokenizer_id is not None:
        tokenizer_id = str(tokenizer_id).strip()
        if not tokenizer_id:
            raise ValueError("tokenizer.id must be a non-empty string when provided.")
    tokenizer["id"] = tokenizer_id

    exact = tokenizer.get("exact")
    if exact is None:
        exact = tokenizer["strategy"] == "huggingface" and bool(tokenizer_id)
    if not isinstance(exact, bool):
        raise ValueError("tokenizer.exact must be a boolean.")
    tokenizer["exact"] = exact

    if tokenizer["strategy"] == "huggingface" and not tokenizer_id:
        raise ValueError("tokenizer.id is required when tokenizer.strategy is huggingface.")
    if tokenizer["strategy"] in {"none", "unknown"}:
        tokenizer["id"] = None
        tokenizer["exact"] = False
    return tokenizer


def context_metadata(agent: dict[str, Any]) -> dict[str, Any]:
    options = agent.get("options") if isinstance(agent.get("options"), dict) else {}
    num_ctx = options.get("num_ctx")
    if isinstance(num_ctx, bool) or not isinstance(num_ctx, int) or num_ctx <= 0:
        return {"tokens": None, "source": None}
    return {"tokens": num_ctx, "source": "agent.options.num_ctx"}


def resolve_model_metadata(agent: dict[str, Any]) -> dict[str, Any]:
    model = str(agent.get("model") or "").strip()
    if not model:
        raise ValueError("agent.model must be a non-empty string.")

    backend = validate_backend(agent.get("backend", "ollama"))
    family = validate_model_family(agent.get("model_family", infer_model_family(model)))
    support = validate_support(agent.get("support", default_support(model, family)))
    tokenizer = normalize_tokenizer(agent.get("tokenizer"), model=model, family=family)
    return {
        "model": model,
        "backend": backend,
        "family": family,
        "support": support,
        "tokenizer": tokenizer,
        "context": context_metadata(agent),
    }


def apply_model_metadata(agent: dict[str, Any]) -> dict[str, Any]:
    agent["model_metadata"] = resolve_model_metadata(agent)
    return agent


def tokenizer_id_for_model(model: str) -> str | None:
    return QWEN_TOKENIZERS.get(model)


def exact_tokenizer_id(model: str, model_metadata: dict[str, Any] | None = None) -> str | None:
    metadata = model_metadata if isinstance(model_metadata, dict) else None
    tokenizer = metadata.get("tokenizer") if metadata else None
    if isinstance(tokenizer, dict):
        if tokenizer.get("exact") and tokenizer.get("strategy") == "huggingface":
            tokenizer_id = tokenizer.get("id")
            if tokenizer_id:
                return str(tokenizer_id)
        return None
    return tokenizer_id_for_model(model)


def exact_tokenizer_models() -> list[str]:
    return sorted(QWEN_TOKENIZERS)
