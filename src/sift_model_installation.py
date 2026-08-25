from __future__ import annotations

import json
from pathlib import Path
from typing import Any


GUIDE_PATH = "docs/model-installation.md"
CATALOG_PATH = "docs/model-installation.json"
SCHEMA_PATH = "schemas/model-installation.schema.json"
DEFAULT_BAND = "local-8gb"


def load_guidance_catalog(root: Path) -> dict[str, Any]:
    path = root / CATALOG_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{CATALOG_PATH} must contain a JSON object.")
    return data


def guidance_for_report(
    *,
    root: Path,
    agent: dict[str, Any],
    runtime: dict[str, Any],
    ollama: dict[str, Any],
    preferred_profile: str | None = None,
) -> dict[str, Any]:
    profile = str(runtime.get("profile") or preferred_profile or DEFAULT_BAND)
    agent_id = str(agent.get("id") or "")
    model = str(agent.get("model") or runtime.get("model") or "")
    resource_mode = _resource_mode(runtime)
    installed_models = [str(item) for item in ollama.get("models") or []]
    endpoint_ready = bool(ollama.get("endpoint_ready"))
    missing_models = [model] if endpoint_ready and model and model not in installed_models else []
    band = _band_for_profile(root=root, profile=profile, agent_id=agent_id)
    next_actions = _next_actions(
        model=model,
        missing_models=missing_models,
        endpoint_ready=endpoint_ready,
        ollama_found=bool(ollama.get("found")),
    )

    return {
        "guide_path": GUIDE_PATH,
        "catalog_path": CATALOG_PATH,
        "schema_path": SCHEMA_PATH,
        "suggested_band": band.get("id", profile),
        "band_label": band.get("label") or profile,
        "recommended_profile": band.get("recommended_profile") or profile,
        "recommended_agent": band.get("recommended_agent") or agent_id,
        "recommended_model": band.get("recommended_model") or model,
        "resource_mode": band.get("resource_mode") or resource_mode,
        "selected_agent": agent_id,
        "selected_model": model,
        "selected_profile": profile,
        "selected_resource_mode": resource_mode,
        "model_installed": model in installed_models if endpoint_ready and model else "unknown",
        "missing_models": missing_models,
        "next_actions": next_actions,
        "approval_required": any(bool(item.get("approval_required")) for item in next_actions),
        "notes": [
            "Use this guidance as a starting point, then verify with farm recommend and a tiny smoke test.",
            "Sift does not install Ollama, pull models, or write config unless the user explicitly approves the command.",
        ],
    }


def _resource_mode(runtime: dict[str, Any]) -> str:
    value = runtime.get("resource_mode")
    if isinstance(value, dict):
        return str(value.get("effective") or value.get("requested") or "auto")
    if value:
        return str(value)
    return "auto"


def _band_for_profile(*, root: Path, profile: str, agent_id: str) -> dict[str, Any]:
    try:
        catalog = load_guidance_catalog(root)
    except Exception:
        return {"id": profile or DEFAULT_BAND, "label": profile or DEFAULT_BAND}
    bands = [item for item in catalog.get("hardware_bands") or [] if isinstance(item, dict)]
    for band in bands:
        if band.get("id") == profile:
            return band
    for band in bands:
        if band.get("recommended_agent") == agent_id:
            return band
    default_band = catalog.get("default_band") or DEFAULT_BAND
    for band in bands:
        if band.get("id") == default_band:
            return band
    return {"id": str(default_band), "label": str(default_band)}


def _next_actions(
    *,
    model: str,
    missing_models: list[str],
    endpoint_ready: bool,
    ollama_found: bool,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if not ollama_found:
        actions.append(
            {
                "id": "ollama.install",
                "command": "python sift.py setup",
                "approval_required": True,
                "reason": "Ollama was not found; setup will print platform-specific install guidance.",
            }
        )
    if missing_models:
        actions.append(
            {
                "id": "model.pull",
                "command": f"ollama pull {model}",
                "approval_required": True,
                "reason": "Downloads the selected local model through Ollama.",
            }
        )
    elif not endpoint_ready:
        actions.append(
            {
                "id": "ollama.start",
                "command": "python sift.py start",
                "approval_required": False,
                "reason": "Starts local services so Sift can inspect installed models.",
            }
        )
    actions.append(
        {
            "id": "recommend.measure",
            "command": "python sift.py farm recommend --json",
            "approval_required": False,
            "reason": "Runs the normal measured recommendation path once the selected model is available.",
        }
    )
    return actions
