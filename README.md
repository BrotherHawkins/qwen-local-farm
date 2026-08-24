# Local Qwen Worker

This folder sets up a local Qwen LLM service using Ollama. It is meant to be runnable on Windows, macOS, and Linux with a simple Python operator script.

Planning docs: [roadmap](docs/roadmap.md), [AI usage](docs/ai-usage.md), [chunking roadmap](docs/chunking-roadmap.md), [specs](docs/specs/README.md), [CI](docs/ci.md)

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

Install Python 3.10+ and Ollama, then open a terminal in this folder:

```bash
python qwen.py setup
python qwen.py start
python qwen.py ask "Say hello in one sentence."
```

On some systems the Python command is `python3` instead of `python`. On Windows, `py -3 qwen.py ...` also works.

Stop it when you are done:

```bash
python qwen.py stop
```

Check status:

```bash
python qwen.py status
```

Windows users can also use the PowerShell convenience wrapper, `.\qwen.ps1`, with the same commands. Platform-specific setup notes are in [docs/platforms.md](docs/platforms.md).

## Worker Farm

Use the farm when you want local offline work staged into files instead of a single immediate answer.

Summarize every readable text file in a folder:

```bash
python qwen.py farm run notes --mode summarize
```

Write the run under a chosen results folder:

```bash
python qwen.py farm run notes --output results --mode summarize
```

Summarize mode automatically chunks oversized text files and reduces the chunk summaries into one file-level result. Chunk inputs and chunk summaries are written under each job folder so a caller can inspect the intermediate work.

Farm runs use a runtime profile so chunk sizes and capacity assumptions are explicit. If no profile is configured, the farm uses `local-8gb`, which preserves the original 8GB GPU dogfood default.

Use a named profile or override specific values:

```bash
python qwen.py farm run notes --mode summarize --profile local-12gb
python qwen.py farm run notes --mode summarize --profile local-24gb --chunk-chars 20000 --parallel-jobs 2
```

The default chunker uses character budgets. For fewer, larger chunks on supported Qwen models, set up exact local tokenizers and opt into token-aware chunking:

```bash
python -m pip install --user "transformers>=5.15" "tokenizers>=0.22"
python qwen.py farm tokenizer setup
python qwen.py farm run notes --mode summarize --chunk-strategy token
```

Tokenizer assets are cached under `.run/tokenizers/`, which is ignored by Git. Verify readiness later with:

```bash
python qwen.py farm tokenizer status
```

For read-only setup guidance, run:

```bash
python qwen.py farm doctor
python qwen.py farm doctor --json
```

Doctor writes `.run/reports/setup-doctor.md` and `.run/reports/setup-doctor.json` for humans, scripts, and primary AIs. It inspects Python, Ollama, models, runtime config, tokenizer readiness, and recent runs without installing packages, downloading tokenizers, pulling models, starting services, or changing config.

`--parallel-jobs` controls farm worker slots: how many file jobs the farm starts at once. It does not launch extra Ollama servers or duplicate model copies. For true same-model parallel inference, Ollama must also be configured for parallel requests, such as with `OLLAMA_NUM_PARALLEL`, and the machine must have enough memory. Start with `--parallel-jobs 2` on a small folder before raising it.

Power users and AI assistants can also write `.qwen-farm.json` at the repo root:

```json
{
  "profile": "local-12gb",
  "model": "qwen3.5:4b",
  "summarize": {
    "chunk_strategy": "character",
    "chunk_chars": 12000,
    "reduce_chars": 12000,
    "token_safety_margin": 0.1,
    "snippet_policy": "off",
    "snippet_count": null,
    "snippet_min_count": 2,
    "snippet_max_count": 8,
    "snippet_max_chars": 600
  },
  "concurrency": {
    "jobs": 1,
    "chunks": 1
  }
}
```

Every run writes `farm-config.resolved.json` beside `farm-status.json` so humans, scripts, and primary AIs can inspect the effective profile, model, chunk sizing, and concurrency settings. Runs also write timing summaries so slow dogfood or batch runs can be inspected without a stopwatch.

For machine-readable inspection, use `python qwen.py farm status --json` for a run overview or `python qwen.py farm status <run-id> --json` for one run. The default `farm status` output stays human-readable Markdown.

Tracked JSON Schema-compatible contracts live under `schemas/` for the main machine-readable artifacts: `farm-status.json`, job `result.json`, status JSON envelopes, and doctor reports. Use `schemas/index.json` when a script or primary AI needs to discover the available contracts.

Validate a JSON artifact before handing it to a script or downstream AI workflow:

```bash
python qwen.py farm schema validate .run/reports/setup-doctor.json
python qwen.py farm schema validate .run/reports/setup-doctor.json --json
python qwen.py farm schema validate .run/reports/setup-doctor.json --schema schemas/farm-doctor.schema.json
```

Without `--schema`, validation auto-detects the current core farm artifacts. Exit code `0` means valid, `1` means schema validation failed, and `2` means the artifact/schema could not be read or inferred.

For performance, `summarize` asks the local model for compact labeled text and the farm parses that into the stable `result.json` envelope. It does not use Ollama JSON grammar mode for the main summary call, and the default summarize call is bounded with `think: false`, `num_predict: 384`, and `num_batch: 128` unless the selected agent already overrides those options.

When a later synthesis step needs a little more source evidence, ask summarize mode for verified verbatim snippets:

```bash
python qwen.py farm run notes --mode summarize --snippets auto
python qwen.py farm run notes --mode summarize --snippets 3
python qwen.py farm run notes --mode summarize --snippets off
```

`--snippets auto` calculates a per-file snippet count from token count, chunk count, or file size. Fixed counts are useful for reproducible runs. Snippets are copied into `result.json` and `result.md` only after the farm verifies that the passage appears exactly in the source text. The farm ranks verified candidates before final selection, keeps score metadata in JSON, and filters obvious scaffolding such as front matter, source URLs, conversion headers, bibliography lines, and generic pointer text. Auto counts are best effort: status artifacts show selected/verified/requested counts and compact drop diagnostics.

After a snippet-enabled run, collect selected source evidence across files into a synthesis-ready pack:

```bash
python qwen.py farm snippets pack <run-ref> --label research-pack
```

`<run-ref>` can be either a run directory path or a known run ID from `python qwen.py farm list`. Snippet packs are post-run artifacts under `.run/snippet_packs/` by default. They read existing `result.json` files, make no model calls, deduplicate and cap snippets deterministically, and write both Markdown and JSON.

When the downstream model needs summary context plus evidence, create a synthesis bundle instead:

```bash
python qwen.py farm synthesis bundle <run-ref> --label research-bundle
```

Synthesis bundles are post-run artifacts under `.run/synthesis_bundles/` by default. They combine compact per-file summaries with selected verified snippets, still without making model calls. Bundle JSON includes character and estimated-token budget metadata. Use `--max-chars <n>` for an exact Markdown size cap, or `--max-estimated-tokens <n>` for a deterministic planning estimate based on `--chars-per-token` (default `4.0`).

To compare dogfood runs over time, record compact local quality history with `python qwen.py farm dogfood record <run-ref>` and compare records with `python qwen.py farm dogfood compare <baseline.json> <candidate.json>`. See `docs/dogfood-quality.md` for the scoring rubric and privacy rules.

Token-aware chunking can also be configured in `.qwen-farm.json`:

```json
{
  "summarize": {
    "chunk_strategy": "token",
    "chunk_tokens": 6500,
    "reduce_tokens": 6500,
    "token_safety_margin": 0.1
  }
}
```

If token budgets are omitted, the farm derives a conservative budget from the selected agent's `num_ctx` and caps summarize chunks at 4096 tokens for local-worker summary quality. Power users can raise `chunk_tokens` and `reduce_tokens` explicitly after dogfooding their hardware/model combination.

If token-aware chunking is requested and the exact local tokenizer is missing, the farm fails before starting jobs and tells you to run `python qwen.py farm tokenizer setup` or switch back to `--chunk-strategy character`.

Apply custom instructions to every readable text file:

```bash
python qwen.py farm run notes --mode prompt --instructions "For each file, identify risks and next actions."
```

Use a larger or CPU/RAM-oriented agent:

```bash
python qwen.py farm run notes --mode summarize --agent qwen8
python qwen.py farm run notes --mode summarize --agent qwen14-cpu
```

Inspect runs:

```bash
python qwen.py farm list
python qwen.py farm status
python qwen.py farm status farm-run-2026-08-23-143022-a7f3
```

Each run writes:

```text
farm-status.json
farm-config.resolved.json
timing-summary.json
FARM_STATUS.md
TIMING_SUMMARY.md
jobs/job-0001/input.json
jobs/job-0001/result.md
jobs/job-0001/result.json
jobs/job-0001/raw-response.txt
```

If `--output` is omitted, runs are written under `.run/farm/`. If `--output` is provided, the farm creates a run folder inside that destination and records it in `.run/farm/runs.json` so `farm list` and `farm status` can still find it.

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

```bash
curl http://127.0.0.1:8765/agents
```

Chat with the default agent:

```bash
python qwen.py ask "Draft a tiny checklist for testing a script."
```

OpenAI-style call through the gateway:

```bash
curl http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.5:4b","messages":[{"role":"user","content":"Give me a JSON object with status=ok."}]}'
```

## Changing Model Size

For the current terminal session:

```bash
QWEN_MODEL="qwen3.5:9b" python qwen.py start
```

If the larger model feels slow or runs out of VRAM, go back to:

```bash
QWEN_MODEL="qwen3:4b" python qwen.py start
```

PowerShell uses `$env:QWEN_MODEL = "qwen3.5:9b"` before the `python qwen.py start` command. See [docs/platforms.md](docs/platforms.md) for shell-specific examples.

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

```bash
python qwen.py ask "Review this idea: ..." reviewer
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

```bash
python qwen.py ask "Make a careful outline for this research task." qwen8
python qwen.py ask "Do the same in CPU/RAM mode." qwen8-cpu
python qwen.py ask "Do a deeper slow-pass analysis." qwen14-hybrid
python qwen.py ask "Do this without using GPU memory." qwen14-cpu
```

## Benchmarks

Benchmark input on the original Windows test machine:

```text
A local Markdown copy of a Karpathy llm-wiki gist/article.
```

Task: summarize the Markdown article in exactly 8 bullets using a `4096` token context and `384` max output tokens.

Local benchmark runs are saved under:

```text
.run/benchmarks/
```

Committed benchmark records are archived under:

```text
docs/benchmarks/
```

4B and 8B summary files:

```text
docs/benchmarks/summarize-20260823-103024-files/
```

14B summary files:

```text
docs/benchmarks/summarize-qwen14-20260823-105219-files/
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

For tighter VRAM use, lower `num_gpu`, `num_ctx`, and `num_batch` before trying larger models. For more GPU use, raise `num_gpu` gradually and watch `python qwen.py status`, `nvidia-smi`, or the platform-specific GPU tooling for your machine.

## Useful Commands

```bash
python qwen.py setup            # Check Ollama and pull the default model
python qwen.py start            # Start Ollama, pull the model if missing, start the agent gateway
python qwen.py stop             # Stop the gateway and unload the model
python qwen.py status           # Show model, GPU, and endpoint status
python qwen.py ask "hello"      # Send one prompt to the default agent
```

Logs and process IDs live in `.run/`. On Windows, `.\qwen.ps1 setup`, `.\qwen.ps1 start`, `.\qwen.ps1 stop`, `.\qwen.ps1 status`, and `.\qwen.ps1 ask "hello"` are also available.

## LAN Access

By default this binds to `127.0.0.1`, which means only this machine can use it. That is the safer newbie default.

To expose the gateway to your local network for the current terminal session on macOS/Linux:

```bash
QWEN_GATEWAY_HOST="0.0.0.0" python qwen.py start
```

In PowerShell:

```powershell
$env:QWEN_GATEWAY_HOST = "0.0.0.0"
python qwen.py start
```

You may also need to allow the port through your OS firewall. Only do this on a trusted private network.
