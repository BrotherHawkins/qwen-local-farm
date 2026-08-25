# AI Usage And Delegation

This document is for primary AIs, scripts, and automation layers that may call the local farm on behalf of a human.

The intended relationship is:

```text
Human -> primary AI -> local farm -> staged outputs/status -> primary AI -> human
```

The human should be able to enable or disable farm availability, but the primary AI should usually decide whether a task is worth delegating.

## Core Rule

Use the farm when the work is suitable for slower, local, staged processing.

Do not use the farm just because it exists.

## Good Times To Use The Farm

Use the farm when:

- Work is slow, batchable, private, offline, or interruptible.
- The user has provided source files or folders to process.
- The task can be split into file-level or chunk-level work.
- The output can be staged for later inspection.
- An independent local model perspective is valuable.
- The primary AI wants a background worker while continuing the main conversation.
- Local processing is preferable to sending data elsewhere.
- Reasonable slowness is acceptable.

Examples:

- Summarize a folder of notes.
- Extract tasks, claims, links, names, dates, or facts from many files.
- Classify files by topic, priority, type, or review status.
- Run a slow second-pass review over code or writing.
- Process a local research folder and stage outputs for later synthesis.

## Bad Times To Use The Farm

Do not use the farm when:

- The user is actively waiting for a fast answer.
- The local model lacks necessary context or tools.
- The task requires live web/current information and the caller has not provided sources.
- The answer must be highly reliable and no review path exists.
- The work depends on precise execution in tools the farm cannot access.
- The prompt contains data that should not be written to local artifacts.
- The input obviously exceeds context and no chunk-safe mode is available.
- The local model is known to be weaker than the primary AI for the needed reasoning.

If unsure, the primary AI should either keep the work in the main conversation or ask the user before farming it out.

## Human Visibility Levels

Future integrations should let the human choose how visible farm work is.

Possible levels:

| Level | Meaning |
| --- | --- |
| `hidden` | Use farm quietly and bring back synthesized results. |
| `summary` | Mention farm work at a high level. |
| `detailed` | Surface farm status and artifacts for inspection. |
| `ask_before_use` | Ask before submitting farm jobs. |
| `disabled` | Do not use the farm. |

The default for many users may be `summary`: the primary AI can use the farm, but should not make the user manage it.

## Capability Discovery

Future callers should discover farm capabilities through all of these:

- human-readable docs
- AI-facing docs like this file
- machine-readable `farm-capabilities.json`
- runtime endpoint such as `GET /farm/capabilities`

The capability record should eventually answer:

- Is the farm available?
- Which interfaces exist: CLI, HTTP, drop folder?
- Which modes are supported?
- Which modes support chunking?
- Which models/agents are available?
- Which output schemas exist?
- What are the known machine limits?
- What should the caller do next?

Possible shape:

```json
{
  "service": "qwen-local-farm",
  "version": "0.1",
  "available": true,
  "interfaces": ["cli", "http", "drop_folder"],
  "modes": ["summarize", "extract", "classify", "review"],
  "later_modes": ["compare", "transform", "research-pack"],
  "input": {
    "default": "folder",
    "file_types": "readable_text",
    "chunking": {
      "available": false,
      "roadmap": "docs/chunking-roadmap.md"
    }
  },
  "outputs": {
    "markdown": true,
    "json": true,
    "status_json": true
  }
}
```

## Immediate Ask Interface

Use immediate ask when the caller wants a simple local answer now.

CLI:

```bash
python qwen.py ask "Summarize this idea in five bullets." qwen8
```

HTTP:

```http
POST /agents/qwen8/chat
```

Immediate ask is not the same as worker-farm processing. It is synchronous and should be used for small prompts where the caller is prepared to wait.

## Worker-Farm Interface

The worker-farm interface supports active CLI invocation now. Drop-folder intake is still future work.

Active invocation:

```bash
python qwen.py farm run input-folder --output results --mode summarize
```

In `summarize` mode, oversized text files are chunked automatically. Each chunk gets its own input and result artifacts under the job folder, then the farm reduces chunk summaries into the normal file-level `result.md` and `result.json`.

For speed, summarize calls use a compact labeled-text contract from the local model and deterministic Python parsing into the result JSON envelope. Do not assume the model itself was called in strict JSON mode; the farm owns the outer JSON artifacts. The default summarize call also disables Qwen thinking and bounds output length unless an agent explicitly supplies those Ollama options.

Runtime profile invocation:

```bash
python qwen.py farm run input-folder --mode summarize --profile local-12gb
python qwen.py farm run input-folder --mode summarize --config .qwen-farm.json
python qwen.py farm run input-folder --mode summarize --chunk-chars 18000 --parallel-jobs 2
python qwen.py farm run input-folder --mode summarize --chunk-strategy token
python qwen.py farm run input-folder --mode summarize --snippets auto
python qwen.py farm run input-folder --mode summarize --resource-mode cpu
python qwen.py farm run input-folder --mode summarize --max-attempts 1 --chunk-max-attempts 1
python qwen.py farm run input-folder --mode summarize --chunk-overlap-chars 500
```

`--parallel-jobs` and `concurrency.jobs` are farm worker slots. They control how many file jobs the farm submits at once. They do not automatically configure Ollama parallel inference.

For actual same-model parallel processing, the user's Ollama server may need external setup such as `OLLAMA_NUM_PARALLEL=2`, and memory use scales with context/KV cache. Assistants should treat this as an environment choice, not something the farm silently changes. Recommend small tests such as `--parallel-jobs 2` before increasing concurrency.

Profiles are the current bridge between power-user control and assistant-operated setup. A primary AI can create or edit `.qwen-farm.json` for the user, then the farm writes the final effective settings into every run.

Failure-policy knobs follow the same precedence path. Use `failure_policy.max_attempts` or `--max-attempts` to control whole-file retries. Use `chunk_max_attempts` and `reduce_max_attempts` for chunked summarize model-call retries. `per_file_timeout_seconds` preserves the existing public timeout setting, but currently applies to each local model call rather than enforcing a true wall-clock cap over all retries/chunks for a file.

Use character chunking when:

- tokenizer setup has not been verified
- the run needs the simplest model-free behavior
- the selected model is not one of the supported Qwen/Ollama aliases

Use token-aware chunking when:

- `python qwen.py farm tokenizer status` reports ready
- large article-like inputs are being over-split by character budgets
- the primary AI wants fewer local worker calls before frontier synthesis

When token budgets are omitted, the farm uses conservative derived budgets and caps summarize chunks at 4096 tokens. A primary AI should only raise `chunk_tokens`/`reduce_tokens` after checking warnings and summary quality on the user's machine.

Chunked summarize preserves Markdown heading ancestry by default. This means chunk input artifacts include compact context like `# Title` and `## Section` before the chunk body, helping the local worker understand where the chunk sits in the article. A request can disable it with `--no-preserve-heading-ancestry`, but leave it on for ordinary Markdown/article inputs.

Overlap is opt-in. Use `--chunk-overlap-chars <n>` for character chunking or `--chunk-overlap-tokens <n>` for token-aware chunking when dogfood shows ideas are being split awkwardly across chunk boundaries. Keep overlap small because it spends prompt budget and can increase duplication in summaries. Runtime artifacts record the effective heading/overlap settings and chunk metadata records whether a chunk received prior-source overlap.

For less technical users, prefer running `python qwen.py farm tokenizer setup` and leaving the resulting `.run/tokenizers/TOKENIZER_STATUS.md` report behind for inspection. If setup fails, explain the missing package/cache step or switch back to character chunking.

For measured local settings guidance, use the recommendation workflow:

```bash
python qwen.py farm doctor --json
python qwen.py farm recommend --agent default --profile local-8gb --output .run/recommendations
python qwen.py farm schema validate .run/recommendations/farm-recommendation.json
```

`farm doctor` stays read-only and fast. It reports whether a latest recommendation exists and points to `farm recommend` when missing. `farm recommend` writes `.run/recommendations/farm-recommendation.json` plus Markdown, runs only a tiny user-invoked Ollama probe when the selected model is ready, and never edits config or service environment variables.

Primary AIs should read the recommendation JSON before suggesting settings. Treat `parallel_jobs` as farm worker slots and `OLLAMA_NUM_PARALLEL` as a separate Ollama service setting. Resource mode is a farm runtime/config setting:

| Mode | Meaning |
| --- | --- |
| `gpu` | Prefer speed through GPU placement. Fails early if the selected agent explicitly forces CPU. |
| `hybrid` | Allow partial GPU offload or Ollama-managed fallback. Fails early if the selected agent explicitly forces CPU. |
| `cpu` | Avoid VRAM pressure and force effective agent options to include `num_gpu: 0`. |
| `auto` | Resolve deterministically before model calls from the selected profile and agent options. |

Resource mode does not silently change model size or switch agent id. If the user wants a deeper model, choose an agent such as `qwen8` or `qwen14-hybrid` explicitly.

If `status` is not `ready`, explain the warnings and next actions rather than treating the settings as measured truth. If confidence is low, run a small dogfood folder before changing `.qwen-farm.json`.

To safely turn a recommendation into project config, preview first:

```bash
python qwen.py farm recommend apply
python qwen.py farm schema validate .run/recommendations/farm-config-apply.json
```

Only apply after inspecting the preview:

```bash
python qwen.py farm recommend apply --write
```

Preview mode does not modify `.qwen-farm.json`. Write mode backs up an existing config first and writes only supported farm config fields. The apply report JSON lists exact field-level changes. `resource_mode` is applied when valid; `OLLAMA_NUM_PARALLEL` stays in `not_applied` guidance because the farm does not change Ollama service state.

Use snippets when:

- a terse summary will be fed to a frontier model for later synthesis
- the source contains useful examples, caveats, definitions, or memorable claims
- the user may want evidence without reading the full article

Snippet policy follows normal farm config precedence. Project config can make snippets the default, and a request can override it with:

```bash
python qwen.py farm run input-folder --mode summarize --snippets off
python qwen.py farm run input-folder --mode summarize --snippets auto
python qwen.py farm run input-folder --mode summarize --snippets 3
```

`--snippets auto` resolves a requested count per file/job from exact token count when available, otherwise from chunk count or file size. Fixed counts are useful for repeatable dogfood comparisons. The model suggests candidate snippets, but the farm only persists snippets that it can verify as exact source text.

The farm ranks verified candidates before final selection. `result.md` stays clean and renders only selected snippets; `result.json` keeps score metadata on selected snippets. Inspect the `snippets` object in `result.json` or `farm-status.json` for selected/verified/requested counts plus compact drop diagnostics such as `unverified`, `low_signal`, `duplicate`, and `too_long`. Auto counts are best effort, while fixed counts remain strict.

When a downstream synthesis model needs source-backed evidence across a whole run, create a post-run snippet pack:

```bash
python qwen.py farm snippets pack <run-ref> --label research-pack --max-snippets 24 --per-file 4
```

`<run-ref>` can be either a run directory path or a known run ID from `python qwen.py farm list`. Snippet packs read selected snippets from existing job `result.json` files, make no model calls, and write Markdown plus JSON under `.run/snippet_packs/` by default. Use the Markdown pack directly in a frontier-model synthesis prompt when the model needs quotes, examples, caveats, or definitions without full article text. Use the JSON pack when a primary AI needs counts, provenance, scores, and skipped-job diagnostics.

When the downstream synthesis model needs both orientation and evidence, prefer a synthesis bundle:

```bash
python qwen.py farm synthesis bundle <run-ref> --label research-bundle --max-snippets 24 --per-file 4
python qwen.py farm synthesis bundle <run-ref> --label research-bundle --max-chars 60000
python qwen.py farm synthesis bundle <run-ref> --label research-bundle --max-estimated-tokens 15000
```

Synthesis bundles read the same existing job `result.json` files, make no model calls, and write Markdown plus JSON under `.run/synthesis_bundles/` by default. Use them when summaries alone are too thin and snippet-only packs lack enough article context. They include summary-only jobs when no snippets were selected, so the downstream model can still see every successful summarize result.

Every synthesis bundle records character count and estimated tokens in its JSON `budget` object and Markdown header. Use `--max-chars` when a downstream prompt has a hard character budget. Use `--max-estimated-tokens` for rough frontier-model planning; it uses a deterministic character/token estimate, not an exact downstream tokenizer. When capped, the bundle drops optional whole snippets, open questions, bullets, and summary-only items in a stable order rather than truncating text mid-snippet.

For dogfood quality comparisons, use `python qwen.py farm dogfood record <run-dir> --label <label> --notes <notes.json>` after a run, then `python qwen.py farm dogfood compare <baseline-record.json> <candidate-record.json>`. Records live under `.run/dogfood_history/` by default and intentionally omit article text, raw responses, and full snippet text. Use `docs/dogfood-quality.md` for the 1-5 scoring rubric.

For dogfood timing comparisons, use `python qwen.py farm dogfood timing record <run-ref> --label <label>` after comparable runs, then `python qwen.py farm dogfood timing compare <baseline-timing.json> <candidate-timing.json>`. Timing records live under `.run/dogfood_timing/` by default and highlight total, per-job, queue, chunk, call, and call-kind deltas plus comparability notes. Use `docs/dogfood-timing.md` when deciding why a run got faster or slower.

Example `.qwen-farm.json`:

```json
{
  "profile": "local-8gb",
  "resource_mode": "auto",
  "model": "qwen3.5:4b",
  "summarize": {
    "chunk_strategy": "character",
    "chunk_chars": 8000,
    "reduce_chars": 8000,
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
  },
  "failure_policy": {
    "max_attempts": 2,
    "per_file_timeout_seconds": 600,
    "chunk_max_attempts": 2,
    "reduce_max_attempts": 2
  }
}
```

Built-in profiles:

```text
cpu-small
local-4gb
local-8gb
local-12gb
local-24gb
custom
```

`farm doctor` provides read-only setup and readiness guidance, including requested/effective resource mode. AI assistants should choose conservative profiles and modes, then leave visible config files and resolved run artifacts behind.

Custom prompt invocation:

```bash
python qwen.py farm run input-folder --mode prompt --instructions "For each file, identify risks and next actions."
```

Status inspection:

```bash
python qwen.py farm list
python qwen.py farm status
python qwen.py farm status <run-id>
python qwen.py farm status --json
python qwen.py farm status <run-id> --json
```

Use `farm status --json` when a script or primary AI needs a machine-readable overview of known runs. Use `farm status <run-id> --json` when it needs the full loaded status for one run without parsing Markdown.

For active chunked summarize runs, inspect each running job's `progress` object before deciding a run is stuck. It reports the current phase (`planning_chunks`, `chunk_map`, or `reduce`), chunk totals and completed counts, reduce generation/batch counters, and the current running model call. The same running call appears in `timing.calls` with `status: "running"` until it completes or fails, so a primary AI can distinguish local preprocessing, chunk mapping, reduce work, and retries.

When a completed run is `partial` or `failed`, prefer retrying failed files before rerunning the whole input folder:

```bash
python qwen.py farm retry-failed <run-id>
python qwen.py farm retry-failed <run-id> --json
```

The retry command creates a new normal run containing only source jobs with `status: "failed"`. It preserves the source run's durable mode, agent, runtime config, and stored instructions when available. Use `--instructions` when retrying an older run that lacks `request.instructions`, or when the human wants to change the retry prompt. The source run is append-only evidence and is not modified.

If `--output` is omitted, the farm writes outputs inside the run folder under `.run/farm/`. If `--output` is provided, the farm creates a structured run folder inside that destination and records it in `.run/farm/runs.json` so later status commands can find it.

The first implementation processes immediately by default. A later `--queue-only` option can let callers stage work without processing it yet.

Future HTTP equivalent:

```http
POST /farm/runs
```

Drop-folder request:

```text
farm-inbox/
  pending/
    request-001/
      farm-request.json
      input/
        notes.md
```

The drop-folder MVP should begin with manual scanning:

```bash
python qwen.py farm scan
```

Long-running watchers and scheduled polling can come later.

## Request Shape

A future farm request should preserve both natural-language intent and structured controls.

Example:

```json
{
  "mode": "review",
  "input": "src/",
  "output": "farm-results/",
  "agent": "qwen14-hybrid",
  "instructions": "Focus on race conditions, missing tests, and fragile error handling. Ignore formatting nits.",
  "options": {
    "max_attempts": 2,
    "chunking": "disabled",
    "output_schema": "review-findings-v0"
  }
}
```

`mode` provides rails. `instructions` preserves caller intent. `options` make automation reliable.

The first implementation supports `summarize` and a generic custom-prompt path. Later early modes should roll out in this order:

1. `summarize` or custom prompt.
2. `extract`.
3. `classify`.
4. `review`.

## Expected Outputs

Every completed job produces both human-readable and machine-readable outputs.

```text
result.md
result.json
raw-response.txt
```

Every farm run produces:

```text
FARM_STATUS.md
farm-status.json
farm-config.resolved.json
TIMING_SUMMARY.md
timing-summary.json
```

The JSON status and result files are the source of truth for primary AIs and scripts. Markdown files exist for human inspection and readable summaries.

Tracked JSON Schema-compatible contracts live in `schemas/`. Use `schemas/index.json` to discover the current contracts for persisted run status, job results, `farm status --json` envelopes, doctor reports, retry-failed JSON, timing summaries, snippet packs, synthesis bundles, and dogfood records/comparisons. Validation is model-free and does not require Ollama.

Use `farm schema validate` when a primary AI or script needs to confirm that an artifact matches the expected contract before consuming it:

```bash
python qwen.py farm schema validate .run/reports/setup-doctor.json --json
python qwen.py farm schema validate <run-dir>/farm-status.json
python qwen.py farm schema validate <run-dir>/jobs/job-0001/result.json
python qwen.py farm schema validate <run-dir>/timing-summary.json
python qwen.py farm schema validate .run/synthesis_bundles/<label>.json
```

Auto-detection covers the current core farm JSON artifacts and post-run package JSON artifacts. Pass `--schema <schema-path-or-id>` when validating a less obvious file or when a workflow wants an explicit contract.

When a run feels slow, inspect `timing-summary.json` first after completion. It summarizes total run duration, job durations, queue wait, aggregate time by call kind, slowest jobs, and slowest model calls. While a run is still active, inspect `farm-status.json` or `farm status <run-id> --json`; active jobs include in-progress chunk/reduce counters and the current model call. Per-job `result.json` files include the model-call timing records for successful jobs, and failed jobs keep call timing in `farm-status.json`.

## Filesystem State

The worker-farm implementation is filesystem-first.

Default farm home:

```text
.run/farm/
```

Future override:

```text
QWEN_FARM_HOME
```

Run IDs use timestamp plus a short random suffix:

```text
farm-run-2026-08-23-143022-a7f3
```

This keeps the farm legible to non-technical users and easy for primary AIs to inspect. SQLite or another index can be added later behind the same CLI/API if the filesystem layout becomes limiting.

## Status Interpretation

A primary AI should use status fields to decide what to do next.

Possible run statuses:

| Status | Meaning | Caller Action |
| --- | --- | --- |
| `queued` | Work is accepted but not running. | Wait or start worker. |
| `running` | Work is in progress. | Wait or inspect progress. |
| `complete` | All work finished cleanly. | Collect and summarize results. |
| `complete_with_warnings` | Outputs exist, but something needs attention. | Inspect warnings before using. |
| `partial` | Some jobs failed. | Use successful outputs, inspect failures, maybe rerun. |
| `failed` | The run did not meaningfully complete. | Inspect error and ask user if needed. |

Future status may include:

```json
{
  "caller_next_action": "wait|collect|inspect_failure|ask_user|rerun|done",
  "needs_user_input": false,
  "blocking_questions": [],
  "warnings": []
}
```

## Mode Guidance

Early modes:

| Mode | Use When | Caution |
| --- | --- | --- |
| `summarize` | The user wants concise understanding of many text files. | Large files may need chunking. |
| custom prompt | The caller wants to apply specific instructions to each file. | Still needs result JSON and status discipline. |
| `extract` | The user wants structured facts, tasks, links, claims, names, or dates. | Validate JSON before trusting it. |
| `classify` | The user wants files/items sorted into labels. | Labels should be provided or discoverable. |
| `review` | The user wants risks, bugs, contradictions, or gaps. | Whole-context reasoning may matter; chunk carefully. |

Later modes:

| Mode | Reason It Needs Its Own Flow |
| --- | --- |
| `compare` | Needs input pairing and alignment strategy. |
| `transform` | Output shapes vary widely. |
| `research-pack` | Multi-step synthesis, indexing, and gap analysis. |

## Setup Guidance For Non-Technical Users

The farm supports a first read-only AI-guided setup path.

Command:

```bash
python qwen.py farm doctor
python qwen.py farm doctor --json
```

Expected outputs:

```text
.run/reports/setup-doctor.md
.run/reports/setup-doctor.json
```

The doctor report should let a primary AI explain:

- whether the machine can run the farm
- which model profile is safest
- whether GPU acceleration is available
- whether CPU/RAM fallback is appropriate
- whether tokenizer-aware chunking is available locally
- whether tokenizer dependencies or cache setup are still needed
- whether more setup is needed

Doctor is read-only. It should not install packages, download tokenizers, pull models, start services, stop services, or write `.qwen-farm.json`. Use its recommendations as next-step guidance for a human or primary AI.

This keeps the experience approachable for non-technical users while still giving power users direct control.

## Delegation Principle

The farm is a worker, not the conversation owner.

The primary AI should:

1. Decide if delegation is useful.
2. Submit work with clear instructions and structured options.
3. Monitor status.
4. Retrieve results.
5. Synthesize or explain results to the human.
6. Ask the human only when farm work needs a decision, permission, or clarification.
