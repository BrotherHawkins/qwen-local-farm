# Sift

Sift runs local AI workers over folders of text and turns bulky source material into inspectable summaries, snippets, timing records, and synthesis-ready artifacts. It is meant to be runnable on Windows, macOS, and Linux with a simple Python operator script.

Planning docs: [roadmap](docs/roadmap.md), [AI usage](docs/ai-usage.md), [chunking roadmap](docs/chunking-roadmap.md), [specs](docs/specs/README.md), [CI](docs/ci.md)

Default model: `qwen3.5:4b`

That is the comfortable default for an 8GB VRAM card. The larger installed models are available for slower offline work when you want more depth.

Qwen is the tested default model family for this repo. Sift normalizes model metadata through an adapter-style shape with backend, family, support level, tokenizer strategy, and context assumptions, so other Ollama model families can be added deliberately later. Non-Qwen or unknown families should be treated as experimental until they have dogfood quality and timing evidence.

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
python sift.py setup
python sift.py start
python sift.py ask "Say hello in one sentence."
```

On some systems the Python command is `python3` instead of `python`. On Windows, `py -3 sift.py ...` also works.

Stop it when you are done:

```bash
python sift.py stop
```

Check status:

```bash
python sift.py status
```

Windows users can also use the PowerShell convenience wrapper, `.\sift.ps1`, with the same commands. Platform-specific setup notes are in [docs/platforms.md](docs/platforms.md).

## Worker Farm

Use the farm when you want local offline work staged into files instead of a single immediate answer.

Summarize every readable text file in a folder:

```bash
python sift.py farm run notes --mode summarize
```

Write the run under a chosen results folder:

```bash
python sift.py farm run notes --output results --mode summarize
```

Summarize mode automatically chunks oversized text files and reduces the chunk summaries into one file-level result. Chunk inputs and chunk summaries are written under each job folder so a caller can inspect the intermediate work.

Farm runs use a runtime profile so chunk sizes and capacity assumptions are explicit. If no profile is configured, the farm uses `local-8gb`, which preserves the original 8GB GPU dogfood default.

Use a named profile or override specific values:

```bash
python sift.py farm run notes --mode summarize --profile local-12gb
python sift.py farm run notes --mode summarize --profile local-24gb --chunk-chars 20000 --parallel-jobs 2
python sift.py farm run notes --mode summarize --resource-mode cpu
```

The default chunker uses character budgets. For fewer, larger chunks on supported Qwen models, set up exact local tokenizers and opt into token-aware chunking:

```bash
python -m pip install --user "transformers>=5.15" "tokenizers>=0.22"
python sift.py farm tokenizer setup
python sift.py farm run notes --mode summarize --chunk-strategy token
```

Tokenizer assets are cached under `.run/tokenizers/`, which is ignored by Git. Verify readiness later with:

```bash
python sift.py farm tokenizer status
```

For read-only setup guidance, run:

```bash
python sift.py farm doctor
python sift.py farm doctor --json
```

Doctor writes `.run/reports/setup-doctor.md` and `.run/reports/setup-doctor.json` for humans, scripts, and primary AIs. It inspects Python, Ollama, models, runtime config, tokenizer readiness, and recent runs without installing packages, downloading tokenizers, pulling models, starting services, or changing config.

For measured local settings guidance, run:

```bash
python sift.py farm recommend --agent default --profile local-8gb --output .run/recommendations
python sift.py farm schema validate .run/recommendations/farm-recommendation.json
```

`farm recommend` writes `.run/recommendations/farm-recommendation.json` and `.run/recommendations/FARM_RECOMMENDATION.md`. It performs a tiny user-invoked Ollama probe when the selected model is ready, then recommends a conservative profile, resource mode, `parallel_jobs`, `OLLAMA_NUM_PARALLEL`, and summarize chunk settings. It does not edit `.sift-farm.json`, start services, pull models, or change Ollama environment variables.

Preview applying those settings to farm config:

```bash
python sift.py farm recommend apply
python sift.py farm schema validate .run/recommendations/farm-config-apply.json
```

Apply requires an explicit write flag:

```bash
python sift.py farm recommend apply --write
```

`farm recommend apply` writes `.run/recommendations/farm-config-apply.json` and `.run/recommendations/FARM_CONFIG_APPLY.md`. Preview mode does not modify `.sift-farm.json`. Write mode backs up an existing config first, then writes only supported farm config fields. Resource mode is now a supported farm config field. `OLLAMA_NUM_PARALLEL` remains guidance because it is an Ollama service environment setting, not a farm config field.

Resource modes use this runtime vocabulary:

| Mode | Meaning |
| --- | --- |
| `gpu` | Prefer speed through GPU placement. Fails early if the selected agent explicitly forces CPU. |
| `hybrid` | Allow partial GPU offload or Ollama-managed fallback. Fails early if the selected agent explicitly forces CPU. |
| `cpu` | Avoid VRAM pressure and force effective agent options to include `num_gpu: 0`. |
| `auto` | Resolve deterministically before model calls from the selected profile and agent options. |

Resource mode does not silently change the selected model or switch agents. Pick a larger or CPU-specific agent explicitly when quality/model size matters.

`--parallel-jobs` controls farm worker slots: how many file jobs the farm starts at once. It does not launch extra Ollama servers or duplicate model copies. For true same-model parallel inference, Ollama must also be configured for parallel requests, such as with `OLLAMA_NUM_PARALLEL`, and the machine must have enough memory. Start with `--parallel-jobs 2` on a small folder before raising it.

Failure policy can be configured per run when you want stricter or more patient behavior:

```bash
python sift.py farm run notes --mode summarize --max-attempts 1 --chunk-max-attempts 1 --reduce-max-attempts 2
python sift.py farm run notes --mode summarize --per-file-timeout-seconds 900
```

`--max-attempts` retries the whole file job. `--chunk-max-attempts` and `--reduce-max-attempts` retry individual chunk-map and reduce model calls during chunked summarize jobs. `--per-file-timeout-seconds` preserves the public timeout knob and currently applies to each local model call.

Failed jobs include failure guidance in `result.json`, `farm-status.json`, `FARM_STATUS.md`, and `farm status <run-id> --json` when the farm can classify the failure. The fields are intentionally simple: `code`, `category`, `retryable`, `retry_after_fix`, `message`, and `recommended_action`. `retryable: true` means retrying the same job may help. `retry_after_fix: true` means fix the input, model, config, or resource setting before repeating the retry.

Power users and AI assistants can also write `.sift-farm.json` at the repo root:

```json
{
  "profile": "local-12gb",
  "resource_mode": "auto",
  "model": "qwen3.5:4b",
  "summarize": {
    "chunk_strategy": "character",
    "chunk_chars": 12000,
    "reduce_chars": 12000,
    "token_safety_margin": 0.1,
    "preserve_heading_ancestry": true,
    "chunk_overlap_chars": 0,
    "chunk_overlap_tokens": 0,
    "snippet_policy": "off",
    "snippet_count": null,
    "snippet_min_count": 2,
    "snippet_max_count": 8,
    "snippet_max_chars": 600
  },
  "concurrency": {
    "jobs": 1,
    "chunks": 1
  },
  "failure_policy": {
    "max_attempts": 2,
    "per_file_timeout_seconds": 600,
    "chunk_max_attempts": 2,
    "reduce_max_attempts": 2
  },
  "discovery": {
    "include": ["articles/*.txt", "notes/**/*.md"],
    "exclude": ["**/raw/**", "**/*.tmp"]
  }
}
```

Every run writes `farm-config.resolved.json` beside `farm-status.json` so humans, scripts, and primary AIs can inspect the effective profile, requested/effective resource mode, model, chunk sizing, heading/overlap policy, concurrency settings, failure policy, and discovery filters. Runs also write timing summaries so slow dogfood or batch runs can be inspected without a stopwatch.

Discovery filters can also be supplied per run:

```bash
python sift.py farm run notes --mode summarize --include "*.md"
python sift.py farm run notes --mode summarize --include "articles/*.txt" --exclude "**/raw/**"
```

Include patterns narrow otherwise eligible text files. Exclude patterns remove otherwise included files and win over include matches. Patterns match input-folder-relative paths using `/` separators. Built-in safety skips for binary files, archives, images, PDFs, Office documents, minified assets, and generated/vendor folders remain in force.

For machine-readable inspection, use `python sift.py farm status --json` for a run overview or `python sift.py farm status <run-id> --json` for one run. The default `farm status` output stays human-readable Markdown. While chunked summarize jobs are active, status artifacts include `job.progress` with the current phase, chunk counts, reduce batch counts, and current running model call, plus in-flight entries in `timing.calls`.

Tracked JSON Schema-compatible contracts live under `schemas/` for the main machine-readable artifacts: `farm-status.json`, job `result.json`, status JSON envelopes, doctor reports, recommendation reports, retry-failed JSON, timing summaries, snippet packs, synthesis bundles, and dogfood records/comparisons. Use `schemas/index.json` when a script or primary AI needs to discover the available contracts.

Validate a JSON artifact before handing it to a script or downstream AI workflow:

```bash
python sift.py farm schema validate .run/reports/setup-doctor.json
python sift.py farm schema validate .run/reports/setup-doctor.json --json
python sift.py farm schema validate .run/reports/setup-doctor.json --schema schemas/farm-doctor.schema.json
python sift.py farm schema validate .run/recommendations/farm-recommendation.json
python sift.py farm schema validate .run/recommendations/farm-config-apply.json
python sift.py farm schema validate <run-dir>/timing-summary.json
```

Without `--schema`, validation auto-detects the current core farm artifacts and post-run package JSON artifacts. Exit code `0` means valid, `1` means schema validation failed, and `2` means the artifact/schema could not be read or inferred.

For performance, `summarize` asks the local model for compact labeled text and the farm parses that into the stable `result.json` envelope. It does not use Ollama JSON grammar mode for the main summary call, and the default summarize call is bounded with `think: false`, `num_predict: 384`, and `num_batch: 128` unless the selected agent already overrides those options.

When a later synthesis step needs a little more source evidence, ask summarize mode for verified verbatim snippets:

```bash
python sift.py farm run notes --mode summarize --snippets auto
python sift.py farm run notes --mode summarize --snippets 3
python sift.py farm run notes --mode summarize --snippets off
```

`--snippets auto` calculates a per-file snippet count from token count, chunk count, or file size. Fixed counts are useful for reproducible runs. Snippets are copied into `result.json` and `result.md` only after the farm verifies that the passage appears exactly in the source text. The farm ranks verified candidates before final selection, keeps score metadata in JSON, and filters obvious scaffolding such as front matter, source URLs, conversion headers, bibliography lines, and generic pointer text. Auto counts are best effort: status artifacts show selected/verified/requested counts and compact drop diagnostics.

After a snippet-enabled run, collect selected source evidence across files into a synthesis-ready pack:

```bash
python sift.py farm snippets pack <run-ref> --label research-pack
```

`<run-ref>` can be either a run directory path or a known run ID from `python sift.py farm list`. Snippet packs are post-run artifacts under `.run/snippet_packs/` by default. They read existing `result.json` files, make no model calls, deduplicate and cap snippets deterministically, and write both Markdown and JSON.

When the downstream model needs summary context plus evidence, create a synthesis bundle instead:

```bash
python sift.py farm synthesis bundle <run-ref> --label research-bundle
```

Synthesis bundles are post-run artifacts under `.run/synthesis_bundles/` by default. They combine compact per-file summaries with selected verified snippets, still without making model calls. Bundle JSON includes character and estimated-token budget metadata. Use `--max-chars <n>` for an exact Markdown size cap, or `--max-estimated-tokens <n>` for a deterministic planning estimate based on `--chars-per-token` (default `4.0`).

To compare dogfood runs over time, record compact local quality history with `python sift.py farm dogfood record <run-ref>` and compare records with `python sift.py farm dogfood compare <baseline.json> <candidate.json>`. For timing regressions, use `python sift.py farm dogfood timing record <run-ref>` and `python sift.py farm dogfood timing compare <baseline.json> <candidate.json>`. See `docs/dogfood-quality.md` for the scoring rubric and `docs/dogfood-timing.md` for timing interpretation.

Token-aware chunking can also be configured in `.sift-farm.json`:

```json
{
  "summarize": {
    "chunk_strategy": "token",
    "chunk_tokens": 6500,
    "reduce_tokens": 6500,
    "token_safety_margin": 0.1,
    "preserve_heading_ancestry": true,
    "chunk_overlap_tokens": 0
  }
}
```

If token budgets are omitted, the farm derives a conservative budget from the selected agent's `num_ctx` and caps summarize chunks at 4096 tokens for local-worker summary quality. Power users can raise `chunk_tokens` and `reduce_tokens` explicitly after dogfooding their hardware/model combination.

If token-aware chunking is requested and the exact local tokenizer is missing, the farm fails before starting jobs and tells you to run `python sift.py farm tokenizer setup` or switch back to `--chunk-strategy character`.

Bundled agents declare model-family metadata such as:

```json
{
  "model": "qwen3.5:4b",
  "model_family": "qwen",
  "backend": "ollama",
  "support": "tested",
  "tokenizer": {
    "strategy": "huggingface",
    "id": "Qwen/Qwen3.5-4B",
    "exact": true
  },
  "options": {
    "num_ctx": 8192
  }
}
```

For an experimental non-Qwen Ollama model, declare the family and keep tokenizer strategy `none` until an exact adapter is available:

```json
{
  "model": "llama3.1:8b",
  "model_family": "llama",
  "backend": "ollama",
  "support": "experimental",
  "tokenizer": {
    "strategy": "none"
  },
  "options": {
    "num_ctx": 4096
  }
}
```

Character chunking can still run with experimental or unknown model families. Token-aware chunking requires exact tokenizer metadata and local tokenizer readiness.

### Adding An Experimental Ollama Model

To try another local Ollama model family without changing farm commands:

1. Pull or create the model in Ollama yourself, outside the farm.
2. Add an agent file under `agents/`, such as `agents/llama-local.json`.
3. Set `model`, `model_family`, `backend`, `support`, `tokenizer`, and `options.num_ctx`.
4. Start with `"support": "experimental"` and `"tokenizer": {"strategy": "none"}`.
5. Run `python sift.py farm doctor --agent <agent-id>`.
6. Run a tiny character-chunking smoke before a large batch:

```bash
python sift.py farm run notes --mode summarize --agent llama-local --chunk-strategy character
```

Supported first-pass metadata values:

| Field | Values |
| --- | --- |
| `backend` | `ollama` |
| `model_family` | `qwen`, `llama`, `mistral`, `gemma`, `phi`, `deepseek`, `unknown` |
| `support` | `tested`, `experimental`, `unknown` |
| `tokenizer.strategy` | `huggingface`, `none`, `unknown` |

Use `support: tested` only after the model family has local dogfood quality and timing evidence. Use `tokenizer.strategy: huggingface` only when an exact tokenizer ID is known and `python sift.py farm tokenizer status --model <model>` can verify it locally. Otherwise use character chunking.

Minimal experimental agent example:

```json
{
  "id": "llama-local",
  "name": "Experimental Llama Worker",
  "model": "llama3.1:8b",
  "model_family": "llama",
  "backend": "ollama",
  "support": "experimental",
  "tokenizer": {
    "strategy": "none"
  },
  "system_prompt": "You are a local experimental worker. Be concise, faithful, and practical.",
  "options": {
    "temperature": 0.3,
    "top_p": 0.9,
    "num_ctx": 4096
  }
}
```

For exact token-aware chunking on a new model, add exact Hugging Face tokenizer metadata to the agent and verify it with `python sift.py farm tokenizer status --model <model>`. If the model should become a bundled default or recognized alias, extend the tokenizer adapter registry in `src/sift_farm_model_metadata.py` and add model-free tests for the mapping. Until exact tokenizer metadata is present and verified, token-aware chunking should fail early with guidance rather than guessing.

Markdown heading ancestry is enabled by default for chunked summarize inputs. Chunk input artifacts include a compact `Heading context` block so a worker processing chunk 4 still knows it is inside headings such as `# Title` and `## Section`. Overlap is opt-in:

```bash
python sift.py farm run notes --mode summarize --chunk-overlap-chars 500
python sift.py farm run notes --mode summarize --chunk-strategy token --chunk-overlap-tokens 200
python sift.py farm run notes --mode summarize --no-preserve-heading-ancestry
```

Overlap adds prior source text as context for continuity, not as primary chunk coverage. It can improve boundary quality, but it spends prompt budget and may make summaries more repetitive, so the default is `0`.

To gather ordinary per-job results from an existing run into one easier-to-inspect folder:

```bash
python sift.py farm collect <run-ref> --label review-pack
```

`farm collect` writes `.run/farm_collections/<label>/FARM_COLLECTION.md`, `.run/farm_collections/<label>/farm-collection.json`, and copied `result.md` / `result.json` files under `items/`. It makes no model calls and does not copy source inputs, raw model responses, logs, or chunk artifacts by default. Use it when you want a flat review pack of existing results. Use snippet packs for evidence-only synthesis inputs, and synthesis bundles when you want compact summaries plus selected snippets.

Apply custom instructions to every readable text file:

```bash
python sift.py farm run notes --mode prompt --instructions "For each file, identify risks and next actions."
```

Use a larger or CPU/RAM-oriented agent:

```bash
python sift.py farm run notes --mode summarize --agent qwen8
python sift.py farm run notes --mode summarize --agent qwen14-cpu
```

Filter file discovery without moving files:

```bash
python sift.py farm run notes --mode summarize --include "articles/*.txt"
python sift.py farm run notes --mode summarize --include "**/*.txt" --exclude "**/raw/**"
```

Inspect runs:

```bash
python sift.py farm list
python sift.py farm status
python sift.py farm status farm-run-2026-08-23-143022-a7f3
python sift.py farm status farm-run-2026-08-23-143022-a7f3 --json
```

Retry only failed files from a previous run:

```bash
python sift.py farm retry-failed farm-run-2026-08-23-143022-a7f3
python sift.py farm retry-failed farm-run-2026-08-23-143022-a7f3 --output .run/retries
python sift.py farm retry-failed farm-run-2026-08-23-143022-a7f3 --instructions "Retry with the same synthesis-focused summary style."
python sift.py farm retry-failed farm-run-2026-08-23-143022-a7f3 --json
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

During a long chunked summarize run, `FARM_STATUS.md` includes an `Active Jobs` section and `farm-status.json` includes active `progress` metadata. Use this to tell whether a job is planning chunks, mapping a specific chunk, reducing chunk summaries, or retrying a failed model call.

`farm retry-failed` creates a new normal farm run containing only jobs that failed in the source run. The source run is not modified, and the retry run's status includes a `retry` section that links source job IDs to retry job IDs. If source failures include guidance, retry output also reports how many selected failures are retryable, non-retryable, or unknown, and warns when retrying may repeat until a recommended fix is applied.

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
python sift.py ask "Draft a tiny checklist for testing a script."
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
SIFT_MODEL="qwen3.5:9b" python sift.py start
```

If the larger model feels slow or runs out of VRAM, go back to:

```bash
SIFT_MODEL="qwen3:4b" python sift.py start
```

PowerShell uses `$env:SIFT_MODEL = "qwen3.5:9b"` before the `python sift.py start` command. See [docs/platforms.md](docs/platforms.md) for shell-specific examples.

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
python sift.py ask "Review this idea: ..." reviewer
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
python sift.py ask "Make a careful outline for this research task." qwen8
python sift.py ask "Do the same in CPU/RAM mode." qwen8-cpu
python sift.py ask "Do a deeper slow-pass analysis." qwen14-hybrid
python sift.py ask "Do this without using GPU memory." qwen14-cpu
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

For tighter VRAM use, lower `num_gpu`, `num_ctx`, and `num_batch` before trying larger models. For more GPU use, raise `num_gpu` gradually and watch `python sift.py status`, `nvidia-smi`, or the platform-specific GPU tooling for your machine.

## Useful Commands

```bash
python sift.py setup            # Check Ollama and pull the default model
python sift.py start            # Start Ollama, pull the model if missing, start the agent gateway
python sift.py stop             # Stop the gateway and unload the model
python sift.py status           # Show model, GPU, and endpoint status
python sift.py ask "hello"      # Send one prompt to the default agent
```

Logs and process IDs live in `.run/`. On Windows, `.\sift.ps1 setup`, `.\sift.ps1 start`, `.\sift.ps1 stop`, `.\sift.ps1 status`, and `.\sift.ps1 ask "hello"` are also available.

## LAN Access

By default this binds to `127.0.0.1`, which means only this machine can use it. That is the safer newbie default.

To expose the gateway to your local network for the current terminal session on macOS/Linux:

```bash
SIFT_GATEWAY_HOST="0.0.0.0" python sift.py start
```

In PowerShell:

```powershell
$env:SIFT_GATEWAY_HOST = "0.0.0.0"
python sift.py start
```

You may also need to allow the port through your OS firewall. Only do this on a trusted private network.
