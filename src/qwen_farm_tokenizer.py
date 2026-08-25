from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.qwen_farm_model_metadata import (
    QWEN_TOKENIZERS,
    exact_tokenizer_id,
    exact_tokenizer_models,
    resolve_model_metadata,
    tokenizer_id_for_model,
)

SUPPORTED_QWEN_TOKENIZERS = QWEN_TOKENIZERS

TOKENIZER_REPORT_JSON = "tokenizer-status.json"
TOKENIZER_REPORT_MD = "TOKENIZER_STATUS.md"

TokenizerLoader = Callable[..., Any]


class TokenizerUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExactTokenCounter:
    model: str
    tokenizer_id: str
    tokenizer: Any

    @property
    def counts_are_estimated(self) -> bool:
        return False

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False))


def tokenizer_root(root: Path) -> Path:
    return root / ".run" / "tokenizers"


def tokenizer_cache_dir(root: Path) -> Path:
    return tokenizer_root(root) / "hf-cache"


def tokenizer_report_paths(root: Path) -> tuple[Path, Path]:
    base = tokenizer_root(root)
    return base / TOKENIZER_REPORT_JSON, base / TOKENIZER_REPORT_MD


def tokenizer_id_for_model(model: str) -> str | None:
    return SUPPORTED_QWEN_TOKENIZERS.get(model)


def tokenizer_dependencies_available() -> bool:
    return importlib.util.find_spec("transformers") is not None


def missing_dependency_message() -> str:
    return (
        "Tokenizer dependencies are not installed. Run "
        '`python -m pip install --user "transformers>=5.15" "tokenizers>=0.22"` '
        "and then run `python sift.py farm tokenizer setup`."
    )


def import_auto_tokenizer() -> Any:
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise TokenizerUnavailableError(missing_dependency_message()) from exc
    return AutoTokenizer


def load_exact_token_counter(
    *,
    root: Path,
    model: str,
    model_metadata: dict[str, Any] | None = None,
    local_files_only: bool = True,
    tokenizer_loader: TokenizerLoader | None = None,
) -> ExactTokenCounter:
    tokenizer_id = exact_tokenizer_id(model, model_metadata)
    if tokenizer_id is None:
        supported = ", ".join(exact_tokenizer_models())
        raise TokenizerUnavailableError(
            f"No exact tokenizer mapping is configured for model `{model}`. "
            f"Supported models: {supported}. Use `summarize.chunk_strategy: character` "
            "or add a tokenizer adapter for this model."
        )

    loader = tokenizer_loader or import_auto_tokenizer().from_pretrained
    try:
        tokenizer = loader(
            tokenizer_id,
            cache_dir=str(tokenizer_cache_dir(root)),
            local_files_only=local_files_only,
        )
    except Exception as exc:
        mode = "local cache" if local_files_only else "setup download"
        raise TokenizerUnavailableError(
            f"Could not load exact tokenizer for model `{model}` from {mode}. "
            f"Tokenizer ID: `{tokenizer_id}`. Run `python sift.py farm tokenizer setup` "
            "or use `--chunk-strategy character`."
        ) from exc

    return ExactTokenCounter(model=model, tokenizer_id=tokenizer_id, tokenizer=tokenizer)


def tokenizer_status(
    *,
    root: Path,
    models: list[str] | None = None,
    download: bool = False,
    tokenizer_loader: TokenizerLoader | None = None,
) -> dict[str, Any]:
    selected_models = models or exact_tokenizer_models()
    records = []
    dependency_available = tokenizer_dependencies_available() if tokenizer_loader is None else True

    for model in selected_models:
        model_metadata = resolve_model_metadata({"model": model, "options": {}})
        tokenizer_id = exact_tokenizer_id(model, model_metadata)
        record: dict[str, Any] = {
            "model": model,
            "model_metadata": model_metadata,
            "tokenizer_id": tokenizer_id,
            "supported": tokenizer_id is not None,
            "dependency_available": dependency_available,
            "cache_dir": str(tokenizer_cache_dir(root)),
            "ready": False,
            "offline_verified": False,
            "tokens_for_probe": None,
            "error": None,
        }

        if tokenizer_id is None:
            record["error"] = f"No tokenizer mapping configured for {model}."
            records.append(record)
            continue
        if not dependency_available:
            record["error"] = missing_dependency_message()
            records.append(record)
            continue

        try:
            if download:
                load_exact_token_counter(
                    root=root,
                    model=model,
                    model_metadata=model_metadata,
                    local_files_only=False,
                    tokenizer_loader=tokenizer_loader,
                )
            counter = load_exact_token_counter(
                root=root,
                model=model,
                model_metadata=model_metadata,
                local_files_only=True,
                tokenizer_loader=tokenizer_loader,
            )
            record["tokens_for_probe"] = counter.count_tokens("hello world\nThis is a tokenizer probe.")
            record["ready"] = True
            record["offline_verified"] = True
        except TokenizerUnavailableError as exc:
            record["error"] = str(exc)
        records.append(record)

    ready = all(record["ready"] for record in records)
    return {
        "ready": ready,
        "counts_are_estimated": False,
        "cache_dir": str(tokenizer_cache_dir(root)),
        "models": records,
    }


def render_tokenizer_status_markdown(status: dict[str, Any]) -> str:
    lines = [
        "# Tokenizer Status",
        "",
        f"Ready: `{bool(status.get('ready'))}`",
        f"Cache: `{status.get('cache_dir', '')}`",
        f"Counts estimated: `{bool(status.get('counts_are_estimated'))}`",
        "",
        "| Model | Tokenizer | Ready | Offline | Probe Tokens | Error |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for record in status.get("models") or []:
        error = str(record.get("error") or "").replace("\n", " ")
        lines.append(
            f"| `{record.get('model', '')}` | `{record.get('tokenizer_id') or ''}` | "
            f"`{bool(record.get('ready'))}` | `{bool(record.get('offline_verified'))}` | "
            f"{record.get('tokens_for_probe') or ''} | {error} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_tokenizer_status(root: Path, status: dict[str, Any]) -> None:
    json_path, md_path = tokenizer_report_paths(root)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_tokenizer_status_markdown(status), encoding="utf-8")
