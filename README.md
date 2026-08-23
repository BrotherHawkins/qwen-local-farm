# Local Qwen Worker

This folder sets up a local Qwen LLM service for Windows using Ollama.

Default model: `qwen3.5:4b`

That is the comfortable default for an 8GB VRAM card. The larger installed models are available for slower offline work when you want more depth.

Installed local models:

| Model | Size | Quantization | Best use |
| --- | --- | --- | --- |
| `qwen3.5:4b` | 4.7B | `Q4_K_M` | Default reliable worker on the 8GB GPU. |
| `qwen3:8b` | 8.2B | `Q4_K_M` | Deeper offline worker; fits in VRAM at `4096` context in testing. |
| `qwen3:14b` | 14.8B | `Q4_K_M` | Heavier offline worker; usable as partial GPU offload or CPU/RAM-only. |
| `qwen3:4b` | 4.0B | `Q4_K_M` | Fallback only; this model emitted thinking text in summarization tests. |

## Quick Start

Open PowerShell in this folder:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\qwen.ps1 setup
.\qwen.ps1 start
.\qwen.ps1 ask "Say hello in one sentence."
```

Stop it when you are done:

```powershell
.\qwen.ps1 stop
```

Check status:

```powershell
.\qwen.ps1 status
```

## What Gets Started

Two local endpoints are available:

| Purpose | URL | Notes |
| --- | --- | --- |
| Ollama native/OpenAI-compatible API | `http://127.0.0.1:11434` | Best for tools that already support Ollama or OpenAI-style local models. |
| Agent gateway | `http://127.0.0.1:8765` | Small wrapper in this repo that loads agent patterns from `agents/*.json`. |

For OpenAI-compatible clients, use:

```text
Base URL: http://127.0.0.1:11434/v1
API key: ollama
Model: qwen3.5:4b
```

Most clients only require an API key field because they were designed for hosted APIs. Ollama does not validate that value locally.

## Agent Gateway Examples

List agents:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/agents
```

Chat with the default agent:

```powershell
$body = @{ message = "Draft a tiny checklist for testing a script." } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8765/agents/default/chat -Method Post -Body $body -ContentType "application/json"
```

OpenAI-style call through the gateway:

```powershell
$body = @{
  model = "qwen3.5:4b"
  messages = @(
    @{ role = "user"; content = "Give me a JSON object with status=ok." }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod http://127.0.0.1:8765/v1/chat/completions -Method Post -Body $body -ContentType "application/json"
```

## Changing Model Size

For the current PowerShell session:

```powershell
$env:QWEN_MODEL = "qwen3.5:9b"
.\qwen.ps1 start
```

If the larger model feels slow or runs out of VRAM, go back to:

```powershell
$env:QWEN_MODEL = "qwen3:4b"
.\qwen.ps1 start
```

If you keep using a different model, update the `model` field in `agents/default.json`.

## Adding Agent Patterns

Add a new JSON file under `agents/`, for example `agents/reviewer.json`:

```json
{
  "id": "reviewer",
  "name": "Code Reviewer",
  "model": "qwen3.5:4b",
  "system_prompt": "You review code for correctness, edge cases, and missing tests. Be concise.",
  "options": {
    "temperature": 0.2,
    "num_ctx": 8192
  }
}
```

Then call:

```powershell
.\qwen.ps1 ask "Review this idea: ..." reviewer
```

Built-in agents:

| Agent | Model | Purpose |
| --- | --- | --- |
| `default` | `qwen3.5:4b` | Safe default for the 8GB GPU. |
| `coder` | `qwen3.5:4b` | Lower-temperature coding helper. |
| `qwen8` | `qwen3:8b` | Larger offline worker; lets Ollama decide GPU/RAM placement. |
| `qwen8-cpu` | `qwen3:8b` | Forces CPU/RAM mode with `num_gpu: 0`; slower but avoids VRAM pressure. |
| `qwen14-hybrid` | `qwen3:14b` | Partial GPU offload with `num_gpu: 24`; uses about 5.82 GB VRAM in the benchmark below. |
| `qwen14-cpu` | `qwen3:14b` | Forces CPU/RAM mode with `num_gpu: 0`; very slow, but preserves VRAM. |

Use an agent by passing its id:

```powershell
.\qwen.ps1 ask "Make a careful outline for this research task." qwen8
.\qwen.ps1 ask "Do the same in CPU/RAM mode." qwen8-cpu
.\qwen.ps1 ask "Do a deeper slow-pass analysis." qwen14-hybrid
.\qwen.ps1 ask "Do this without using GPU memory." qwen14-cpu
```

## Benchmarks

Benchmark file:

```text
C:\claude\karpathy-obsidian-spike\raw\articles\karpathy-llm-wiki-gist.md
```

Task: summarize the Markdown article in exactly 8 bullets using a `4096` token context and `384` max output tokens.

Results were saved under:

```text
C:\Github\GHE\qwen-local-farm\.run\benchmarks\
```

Committed benchmark records are archived under:

```text
C:\Github\GHE\qwen-local-farm\docs\benchmarks\
```

4B and 8B summary files:

```text
C:\Github\GHE\qwen-local-farm\.run\benchmarks\summarize-20260823-103024-files\
```

14B summary files:

```text
C:\Github\GHE\qwen-local-farm\.run\benchmarks\summarize-qwen14-20260823-105219-files\
```

Speed results:

| Run | Cold wall | Model load | Load share | Same-prompt warm | Kept-warm estimate for a new file | Output speed | VRAM used |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `qwen3.5:4b` GPU | 11.27s | 5.76s | 51% | 4.87s | ~5.51s | ~80 tok/s | ~3.07 GB |
| `qwen3:4b` GPU | 14.90s | 4.75s | 32% | 4.62s | ~10.15s | ~84 tok/s | ~3.12 GB |
| `qwen3:8b` GPU | 14.64s | 6.38s | 44% | 3.68s | ~8.26s | ~53 tok/s | ~5.50 GB |
| `qwen3:8b` CPU/RAM | 94.63s | 5.83s | 6% | 23.40s | ~88.80s | ~8.8 tok/s | 0 GB |
| `qwen3:14b` hybrid | 90.73s | 33.77s | 37% | 38.37s | ~56.96s | ~7.8 tok/s | ~5.82 GB |
| `qwen3:14b` CPU/RAM | 270.18s | 17.73s | 7% | 66.93s | ~252.45s | ~4.4 tok/s | 0 GB |

How to read this:

- **Cold wall** includes loading the model plus processing the file and generating the answer.
- **Model load** is the part that goes away when the model is already resident.
- **Same-prompt warm** is very optimistic because Ollama can benefit from prompt/context caching when the exact same prompt is repeated.
- **Kept-warm estimate for a new file** is usually the better planning number for batch work: `cold wall - model load`.

Quality notes from this run:

- `qwen3.5:4b` was the best reliable default. It captured the article's architecture, ingest/query/lint loop, index/log distinction, tooling, and human-vs-LLM division of labor.
- `qwen3:8b` GPU was the best practical deeper worker. Its summary was concise and faithful, but slightly less complete than `qwen3.5:4b` on tooling and framing details.
- `qwen3:8b` CPU/RAM had essentially the same quality as `qwen3:8b` GPU, because it is the same model. It is much slower because prompt ingestion and generation happen on CPU.
- `qwen3:14b` hybrid gave the strongest overall summaries in this test. It captured the RAG contrast, raw/wiki/schema split, ingest/query/lint loop, index/log files, and tooling cleanly.
- `qwen3:14b` CPU/RAM produced similar quality to 14B hybrid, but it is a walk-away-for-minutes mode.
- `qwen3:4b` is not recommended for unattended summarization yet. It emitted reasoning/planning text despite instructions not to.

Practical choice:

| Need | Use |
| --- | --- |
| Fast, reliable local worker | `default` / `qwen3.5:4b` |
| Deeper offline summary or analysis while GPU is free | `qwen8` / `qwen3:8b` |
| Preserve VRAM and let work run slowly in the background | `qwen8-cpu` / `qwen3:8b` with `num_gpu: 0` |
| Stronger slow offline worker with partial GPU help | `qwen14-hybrid` / `qwen3:14b` with `num_gpu: 24` |
| Stronger slow offline worker with no GPU memory | `qwen14-cpu` / `qwen3:14b` with `num_gpu: 0` |
| Larger overnight experiments | Try 27B-class models only if you have enough system RAM and patience |

To keep a model warm, leave Ollama running and make requests with `keep_alive` set, or keep using the same agent regularly. The gateway currently sends agent requests through Ollama; Ollama controls how long models stay resident.

## Larger Offline Models

The installed 8B and 14B options are Q4-style quantized models in Ollama (`Q4_K_M`). That is the right family of quantization for trying larger local models on an 8GB VRAM card.

Reasonable next experiments:

| Model | Expected fit |
| --- | --- |
| `qwen3:8b` | Installed; good 8B option; fits comfortably in testing at `4096` context. |
| `qwen3.5:9b` | Slightly newer/larger than 8B; worth testing if 8B behaves well. |
| `qwen3:14b` | Installed; works with partial GPU offload and CPU/RAM-only mode. |
| `qwen3.5:27b` / `qwen3.6:27b` / `qwen3.8:27b` | Possible only if you have enough system RAM and patience; expect slow CPU-heavy runs. |

For CPU/RAM fallback on any agent, add this to the agent's `options`:

```json
"num_gpu": 0
```

For hybrid VRAM plus RAM behavior, set `num_gpu` to a positive layer count instead of `0`. Ollama will offload that many layers to the GPU and leave the rest in system RAM. The current 14B hybrid profile uses:

```json
"num_gpu": 24
```

For tighter VRAM use, lower `num_gpu`, `num_ctx`, and `num_batch` before trying larger models. For more GPU use, raise `num_gpu` gradually and watch `.\qwen.ps1 status` or `nvidia-smi`.

## Useful Commands

```powershell
.\qwen.ps1 setup            # Install Ollama if needed and pull the default model
.\qwen.ps1 start            # Start Ollama, pull the model if missing, start the agent gateway
.\qwen.ps1 stop             # Stop the gateway and unload the model
.\qwen.ps1 status           # Show model, GPU, and endpoint status
.\qwen.ps1 ask "hello"      # Send one prompt to the default agent
```

Logs and process IDs live in `.run/`.

## LAN Access

By default this binds to `127.0.0.1`, which means only this machine can use it. That is the safer newbie default.

To expose the gateway to your local network for the current terminal session:

```powershell
$env:QWEN_GATEWAY_HOST = "0.0.0.0"
.\qwen.ps1 start
```

You may also need to allow the port through Windows Firewall. Only do this on a trusted private network.
