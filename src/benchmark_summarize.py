from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


OLLAMA_BASE = "http://127.0.0.1:11434"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".run" / "benchmarks"


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{OLLAMA_BASE}{path}", data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=900) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def ollama_exe() -> str:
    candidates = [
        Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
        Path("C:/Program Files/Ollama/ollama.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "ollama"


def stop_model(model: str) -> None:
    subprocess.run([ollama_exe(), "stop", model], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def stop_all(models: list[str]) -> None:
    for model in sorted(set(models)):
        stop_model(model)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        loaded = request_json("GET", "/api/ps").get("models", [])
        if not loaded:
            return
        time.sleep(0.5)


def ns_to_seconds(value: int | float | None) -> float:
    return round((value or 0) / 1_000_000_000, 3)


def summarize_result(config: dict[str, Any], phase: str, payload: dict[str, Any], response: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    eval_count = response.get("eval_count") or 0
    eval_seconds = (response.get("eval_duration") or 0) / 1_000_000_000
    prompt_count = response.get("prompt_eval_count") or 0
    prompt_seconds = (response.get("prompt_eval_duration") or 0) / 1_000_000_000
    ps = request_json("GET", "/api/ps").get("models", [])
    loaded = next((item for item in ps if item.get("model") == config["model"]), ps[0] if ps else {})

    return {
        "id": config["id"],
        "model": config["model"],
        "phase": phase,
        "options": payload["options"],
        "wall_seconds": round(wall_seconds, 3),
        "ollama_total_seconds": ns_to_seconds(response.get("total_duration")),
        "load_seconds": ns_to_seconds(response.get("load_duration")),
        "prompt_eval_count": prompt_count,
        "prompt_eval_seconds": round(prompt_seconds, 3),
        "prompt_tokens_per_second": round(prompt_count / prompt_seconds, 2) if prompt_seconds else None,
        "completion_eval_count": eval_count,
        "completion_eval_seconds": round(eval_seconds, 3),
        "completion_tokens_per_second": round(eval_count / eval_seconds, 2) if eval_seconds else None,
        "loaded_size": loaded.get("size"),
        "loaded_size_vram": loaded.get("size_vram"),
        "loaded_context": loaded.get("context_length"),
        "summary": response.get("message", {}).get("content", "").strip(),
    }


def run_once(config: dict[str, Any], phase: str, prompt: str) -> dict[str, Any]:
    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "system",
                "content": "You summarize technical writing for an offline research worker. Be concise and faithful.",
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "keep_alive": "5m",
        "options": config["options"],
    }
    start = time.perf_counter()
    response = request_json("POST", "/api/chat", payload)
    wall_seconds = time.perf_counter() - start
    return summarize_result(config, phase, payload, response, wall_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    args = parser.parse_args()

    article = args.file.read_text(encoding="utf-8")
    prompt = (
        "Summarize the following Markdown article in exactly 8 bullets. "
        "Focus on the core claims, practical lessons, and any terminology a local-LLM user should retain. "
        "Do not include chain-of-thought or reasoning traces.\n\n"
        f"{article}"
    )

    configs = [
        {
            "id": "qwen3.5-4b-gpu",
            "model": "qwen3.5:4b",
            "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096, "num_batch": 128, "num_predict": 384},
        },
        {
            "id": "qwen3-4b-gpu",
            "model": "qwen3:4b",
            "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096, "num_batch": 128, "num_predict": 384},
        },
        {
            "id": "qwen3-8b-gpu",
            "model": "qwen3:8b",
            "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096, "num_batch": 128, "num_predict": 384},
        },
        {
            "id": "qwen3-8b-cpu",
            "model": "qwen3:8b",
            "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096, "num_batch": 64, "num_predict": 384, "num_gpu": 0},
        },
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_models = [config["model"] for config in configs]
    results: list[dict[str, Any]] = []

    for config in configs:
        print(f"== {config['id']} cold ==", flush=True)
        stop_all(all_models)
        results.append(run_once(config, "cold", prompt))

        print(f"== {config['id']} warm ==", flush=True)
        results.append(run_once(config, "warm", prompt))
        stop_all(all_models)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results_path = OUT_DIR / f"summarize-{stamp}.json"
    summary_path = OUT_DIR / f"summarize-{stamp}.md"

    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = ["# Qwen Summarization Benchmark", ""]
    lines.append("| Run | Wall s | Load s | Prompt tok/s | Output tok/s | Output tokens | VRAM bytes |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in results:
        lines.append(
            "| {id} {phase} | {wall_seconds} | {load_seconds} | {prompt_tokens_per_second} | "
            "{completion_tokens_per_second} | {completion_eval_count} | {loaded_size_vram} |".format(**item)
        )
    lines.append("")
    for item in results:
        lines.append(f"## {item['id']} {item['phase']}")
        lines.append("")
        lines.append(item["summary"])
        lines.append("")
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"results": results, "results_path": str(results_path), "summary_path": str(summary_path)}, indent=2))


if __name__ == "__main__":
    main()

