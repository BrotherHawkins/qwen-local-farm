# Roadmap

This project starts as a simple local Qwen service, but the intended direction is broader: a local worker layer that other AIs, scripts, and systems can use when work is better done offline, privately, slowly, or in parallel.

The roadmap below is intentionally lightweight. It captures the shape of the next system without pretending every interface is already designed.

## Roadmap Docs

- [AI usage and delegation](ai-usage.md): how GPT, Claude, Codex, scripts, and other callers should decide when to use the farm.
- [Chunking roadmap](chunking-roadmap.md): how the farm should eventually handle files or folders that exceed a model's context window.
- [Dogfood quality history](dogfood-quality.md): how to record and compare local summary/snippet quality across farm runs.
- [Dogfood timing history](dogfood-timing.md): how to record and compare local timing regressions across farm runs.
- [Backlog](backlog.md): durable follow-up items deferred from specs and roadmap discussions.

## Implemented Baseline

- Immediate asks through `python qwen.py ask`.
- Agent gateway for synchronous local chat.
- Filesystem-backed worker-farm MVP:
  - `python qwen.py farm run <input-folder> --mode summarize`
  - `python qwen.py farm run <input-folder> --mode prompt --instructions <text>`
  - `python qwen.py farm list`
  - `python qwen.py farm status`
  - `python qwen.py farm status <run-id>`
  - Markdown, JSON, raw response, and run status artifacts.
- Runtime profiles for local capacity tiers, config files, CLI overrides, and resolved config artifacts.
- Resource-aware runtime modes, doctor reports, recommendations, and safe recommendation config apply.
- First-pass timing metrics for runs, jobs, model calls, chunk maps, reduces, and timing summary artifacts.
- Opt-in tokenizer-aware summarize chunk sizing for supported Qwen/Ollama agents.
- Qwen remains the tested default model family; broader local model-family support should be added through explicit adapter metadata rather than interface churn.
- Opt-in verified source snippets for summarize results, including deterministic ranking and compact diagnostics.
- Tracked schema contracts and public schema validation for core and post-run JSON artifacts.
- Post-run farm collections that flatten ordinary job result artifacts into one inspectable folder.
- Post-run cross-file snippet packs for downstream synthesis.
- Post-run synthesis bundles that combine compact summaries with verified snippets.
- Local dogfood quality records and comparisons for tracking summary/snippet value.
- Local dogfood timing records and comparisons for spotting performance regressions.

## North Star

Build a local AI worker farm with two clear interaction modes:

| Mode | Purpose | Expected Feel |
| --- | --- | --- |
| Immediate ask | Ask a local model now and get an answer in the current flow. | Interactive, simple, low ceremony. |
| Worker farm | Submit offline jobs and let local models process them when resources are available. | Queue-based, durable, inspectable, resumable. |

The system should be useful to humans directly, but also easy for other AIs to invoke from tools like Codex, Claude Code, scripts, or local automations.

The main product posture is:

```text
Human -> primary AI -> local farm -> staged outputs/status -> primary AI -> human
```

The human should be able to enable or disable farm availability, but should not have to manage every delegation decision.

## Near-Term Priorities

1. Make partial failures easier to recover with failed-run retry helpers.
2. Dogfood and refine file-discovery controls now that include/exclude overrides exist.
3. Add model-family adapter seams before Qwen-specific assumptions harden into the farm core.
4. Mature post-run packages so summaries, snippets, and bundles are easier to feed into frontier-model workflows.
5. Add new modes only after the summarize/chunk/status foundation stays pleasant under dogfood pressure.

## MVP Decisions

These decisions should guide the first worker-farm implementation PR:

| Question | Decision |
| --- | --- |
| Storage | Filesystem first; consider SQLite later only if querying/history/concurrency becomes painful. |
| Farm home | Default to `.run/farm/`; allow an override such as `QWEN_FARM_HOME`. |
| Run ID | Use timestamp plus short random suffix, such as `farm-run-2026-08-23-143022-a7f3`. |
| Output destination | Optional. If omitted, write under the run folder. If provided, create a run folder inside the destination. |
| Command namespace | Use `python qwen.py farm ...` for worker-farm commands. |
| First run behavior | Process immediately by default; add `--queue-only` later for submit-without-processing. |
| First input shape | One folder, with each eligible readable text file treated as a sub-job. |
| First mode | Implement `summarize` first, with a generic custom-prompt path underneath. |
| Mode rollout | `summarize` or custom prompt, then `extract`, then `classify`, then `review`. |

The user-facing abstraction should stay files and folders. More technical storage or scheduling can be added behind that abstraction later.

## 1. Immediate Ask vs Worker Farm

Current state:

- `python qwen.py ask "..." [agent-id]` supports immediate local asks.
- The gateway exposes synchronous chat endpoints.
- `python qwen.py farm run <input-folder> --mode summarize` processes readable text files into durable farm artifacts.
- `python qwen.py farm list` and `python qwen.py farm status [run-id]` inspect farm state.
- `python qwen.py farm collect <run-id>` flattens completed job results into an inspectable post-run folder.
- `python qwen.py farm retry-failed <run-id>` reruns only failed files from a prior run as a new normal run.

Roadmap:

- Add queue-only runs for offline work with a simple first contract: "work these inputs here, put results over there."
- Continue hardening the stable run/job object and post-run helper contracts.
- Add durable failure classifications so callers can tell transient retry candidates from failures that need input, config, or resource fixes first.
- Add `python qwen.py farm scan` when drop-folder intake is ready.
- Let immediate asks remain simple and separate from queued work.
- Keep process-now as the default. Add `--queue-only` later for callers that want to stage jobs without running them yet.

Proposed output shape:

```text
results/
  farm-run-2026-08-23-143022-a7f3/
    FARM_STATUS.md
    farm-status.json
    outputs/
      article-a.summary.md
      article-a.summary.json
      notes/
        spec.summary.md
        spec.summary.json
    jobs/
      job-001/
        input.json
        raw-response.txt
        log.md
```

The caller chooses the destination area. The farm owns the run structure inside it. A later exact-output-path option can exist for special cases, but the default should work well when one input folder turns into many outputs.

Open questions:

- Should workers run only when explicitly started, or should there be a background scheduler?
- How configurable should run-folder naming and output layout be?
- Should human labels live only in metadata, or optionally become part of run folder names later?

Near-term candidates:

- Queue-only runs.
- Drop-folder scanning.

## 2. Status And Overview Artifacts

Primary reader: the calling AI. Secondary reader: the human.

Every farm run should maintain both:

```text
FARM_STATUS.md
farm-status.json
```

`farm-status.json` should be the source of truth for other AIs and scripts. `FARM_STATUS.md` should be a readable rendering for humans.

Status should let a caller decide whether to wait, collect results, inspect failures, rerun work, ask the user, or summarize final outputs.

Future fields may include:

```json
{
  "farm_run_id": "farm-run-2026-08-23-143022-a7f3",
  "status": "running",
  "total_files": 12,
  "completed_files": 7,
  "failed_files": 1,
  "current_file": "notes/spec.md",
  "caller_next_action": "wait",
  "needs_user_input": false,
  "blocking_questions": []
}
```

Timing is part of the normal status contract, not a separate benchmark-only path. Runs, jobs, chunk map calls, and reduce calls record start/finish timestamps and durations so dogfood runs can be compared over time and performance regressions can be investigated. Dogfood quality history also records compact local run comparisons and optional 1-5 quality scores so snippet and summary changes can be judged against prior runs without tracking article text.

## 3. Structured Output

Current state:

- Immediate agent responses are plain model text.
- Farm summarize outputs use a deterministic outer JSON envelope plus Markdown, raw response, timing, chunking, and snippet artifacts.
- The farm owns parsing for the current summarize contract instead of relying on strict model JSON mode.
- Tracked schema contracts exist for core farm artifacts, status JSON envelopes, doctor/recommend/apply reports, timing summaries, snippet packs, synthesis bundles, dogfood records, and farm collections.
- A public `farm schema validate` command validates known JSON artifacts against tracked schemas.

Roadmap:

- Every completed job should produce a human-readable Markdown artifact and a machine-readable JSON artifact.
- Define a small set of output contracts:
  - `text`: freeform Markdown.
  - `summary`: title, bullets, key claims, uncertainty notes.
  - `extraction`: entities, facts, dates, links, tags.
  - `review`: findings, severity, evidence, recommendations.
  - `decision`: options, tradeoffs, recommendation, confidence.
- Support both human-readable Markdown and machine-readable JSON sidecars:
  - `result.md`
  - `result.json`
- Let the farm own the deterministic outer JSON envelope.
- Ask the model for the smallest mode-specific payload that is useful, then have Python build the stable outer artifact shape.
- For future modes that need strict structured fields, define the parser/repair policy in that mode's spec instead of assuming JSON-mode model output.

Example envelope:

```json
{
  "schema_version": "0.1",
  "job_id": "job-001",
  "mode": "extract",
  "status": "complete",
  "structured_valid": true,
  "input": {
    "path": "input/article.md",
    "kind": "file"
  },
  "result": {
    "entities": [],
    "claims": [],
    "tasks": []
  },
  "artifacts": {
    "markdown": "outputs/article.extract.md",
    "raw": "jobs/job-001/raw-response.txt"
  },
  "model": {
    "agent": "qwen8",
    "model": "qwen3:8b"
  }
}
```

Open questions:

- Which output contracts should become first-class after `summarize`: `extract`, `classify`, or `review`?
- Should strict schema mode reject unknown fields once artifact contracts mature?
- Should generated schema docs come before additional mode schemas?

## 4. Chunking Larger Context

Current state:

- Summarize mode auto-chunks oversized readable text inputs.
- Character chunking uses paragraph-aware splitting with map/reduce summarization.
- Token-aware chunking is opt-in for supported Qwen/Ollama tokenizers.
- Chunk and reduce model calls have timing metrics and configurable retry limits.
- Chunked summarize jobs expose active chunk map and reduce progress in normal status artifacts.

Roadmap:

- Treat chunking as its own sub-feature with its own roadmap: [docs/chunking-roadmap.md](chunking-roadmap.md).
- Auto-chunk only for modes where chunking is naturally safe:
  - `summarize`
  - `extract`
  - `classify`
  - some forms of `transform`
- Do not blindly auto-chunk modes where whole-context reasoning matters:
  - `review`
  - `decision`
  - code architecture analysis
  - comparison across distant sections
- Fail clearly or ask for an explicit chunking strategy when a mode is not chunk-safe.

Near-term candidates:

- Failed-file or failed-chunk retry helpers.

## 5. Modes As Rails

Modes are suggestive rails, not strict prisons. A mode should provide defaults for prompt framing, model choice, output schema, chunking policy, retry/repair behavior, and artifact naming. The caller should still provide freeform instructions and optional structured knobs.

Early modes:

| Mode | ELI5 Meaning | Example Use |
| --- | --- | --- |
| `summarize` | Read this and tell me the important ideas in a shorter form. | Summarize a folder of notes. |
| `custom prompt` | Apply caller-provided instructions to each file. | "For each file, tell me what changed and what looks risky." |
| `extract` | Pull specific useful things out. | Extract tasks, dates, claims, links, or facts. |
| `classify` | Put each input into useful buckets. | Assign topic, priority, status, or routing labels. |
| `review` | Look for things that need attention. | Find bugs, risks, contradictions, gaps, or missing tests. |

Implementation order:

1. `summarize` or custom prompt.
2. `extract`.
3. `classify`.
4. `review`.

Later sub-roadmap modes:

| Mode | ELI5 Meaning | Why Later |
| --- | --- | --- |
| `compare` | Explain what is same, different, missing, or changed. | Needs pairing, alignment, and difference strategy. |
| `transform` | Rewrite the input into another shape. | Output shape can vary widely. |
| `research-pack` | Turn a pile of material into an organized bundle. | Multi-step flow: summarize, index, synthesize, gap-find. |

Near-term candidates:

- Keep `extract`, `classify`, and `review` as roadmap items until summarize/chunk recovery and status visibility feel solid.
- When a new mode starts, define its output contract, chunk-safety policy, and parser/repair behavior in the spec.

## 6. Caller Instructions

Caller instructions should support both freeform intent and structured controls.

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

Natural-language intent should be preserved, while machine-readable controls steer automation.

## 7. File Eligibility

The first farm should process any readable text file under a size limit, not just Markdown.

Default behavior:

- Process readable text files.
- Skip binary files.
- Skip generated/vendor folders such as `.git/`, `node_modules/`, `bin/`, `obj/`, `dist/`, `build/`, and `__pycache__/`.
- Skip obviously unsuitable files such as archives, images, PDFs, Office documents, and minified assets.
- Support include/exclude overrides for reproducible file discovery.
- Add `.qwenignore`, force-include escapes, and richer discovery diagnostics only if include/exclude dogfood shows the need.

Office, PDF, image, and archive handling should become explicit processing modes later.

## 8. Inbox And Drop-Folder Intake

The farm should support both active invocation and filesystem intake over time:

| Intake | Purpose |
| --- | --- |
| CLI/HTTP invoke | Start a run now with explicit parameters. |
| Drop folder | Put work somewhere and let the farm pick it up when told or scheduled. |

Start drop-folder support with manual scanning:

```bash
python qwen.py farm scan
```

First request shape:

```text
farm-inbox/
  pending/
    request-2026-08-23-001/
      farm-request.json
      input/
        article-a.md
        notes/
          article-b.md
  accepted/
  done/
  partial/
  failed/
```

`farm-request.json` should carry mode, agent, instructions, output destination, and options. After processing, request folders should move out of `pending/` so the inbox drains. Exact archive/move policy should become configurable later.

## 9. Failure And Review Policy

Implemented failure policy:

- Retry a failing file/sub-job.
- If it still fails, mark that sub-job failed.
- Continue processing remaining files.
- Mark the run `partial` if any file failed.
- Mark the run `complete_with_warnings` if outputs exist but structured repair or other non-fatal issues occurred.
- Retry failed files from a previous run as a new normal run.
- Add failure code, category, retryability, retry-after-fix guidance, and recommended action metadata to failed job artifacts.

The current farm config supports fixed retry and timeout knobs:

```json
{
  "failure_policy": {
    "max_attempts": 2,
    "per_file_timeout_seconds": 600,
    "chunk_max_attempts": 2,
    "reduce_max_attempts": 2
  }
}
```

Longer term, failure behavior can grow into policy decisions:

```json
{
  "failure_policy": {
    "on_file_failure": "continue",
    "on_schema_failure": "repair_then_warn",
    "on_run_failure": "stop"
  }
}
```

Review policy should be mode-dependent and caller-configurable. Some results may be final enough for automation, while others should be staged for human or AI review.

Near-term failure hardening:

- Dogfood failure guidance until it is reliable enough to drive stricter retry behavior.
- Keep automatic fallback and stricter retry selection deferred until failure guidance is reliable enough to drive behavior.

Possible review states:

```text
staged
review_needed
accepted
rejected
superseded
```

## 10. Human Visibility

The default product surface is a primary AI using the farm on the human's behalf. The human should be able to decide how visible farm work is without managing the farm directly.

Future visibility levels:

```json
{
  "farm_visibility": "hidden|summary|detailed|ask_before_use|disabled"
}
```

Possible meanings:

- `hidden`: primary AI uses farm quietly and brings back final synthesis.
- `summary`: primary AI mentions farm work at a high level.
- `detailed`: farm status/artifacts are surfaced for inspection.
- `ask_before_use`: primary AI asks before submitting farm jobs.
- `disabled`: farm is not available.

## 11. Scheduling, Resources, And Routing

Current state:

- Model choice is explicit through agent configs.
- Qwen is the tested/default model family.
- First-class `auto`, `gpu`, `hybrid`, and `cpu` resource modes exist in config/CLI/resolved artifacts.
- Runtime profiles now make model, summarize chunk sizing, and concurrency assumptions explicit for each run.
- Every run writes `farm-config.resolved.json`.
- File-job scheduler concurrency can use `concurrency.jobs` as a bounded worker-slot limit.
- Failure policy now exposes fixed retry and timeout knobs for whole-file, chunk, and reduce work.

Roadmap:

- Use runtime profiles as the stable configuration layer for both power users and AI-assisted setup.
- Add model-family metadata for backend, family, tokenizer support, context assumptions, and support posture before adding more local model families.
- Add model routing rules that consider speed, VRAM pressure, job type, and expected quality.
- Add a simple worker scheduler:
  - max concurrent jobs
  - only run heavy jobs when allowed
  - pause/resume
  - retry failed jobs
- Add keep-warm settings for frequently used models.
- Add user-level farm availability: enabled, disabled, ask before use.

Open questions:

- When should resource mode be allowed to switch agent ids or model sizes?
- Should heavy 14B jobs require an explicit queue/mode label?
- Should GPU use be opt-in for background jobs?
- Should advanced users manage multiple Ollama server pools themselves, or should the farm eventually provide a pool abstraction?

Near-term candidates:

- Retry failed files from a previous run before attempting dynamic routing.
- Add dynamic scheduler backoff only after failure classes are reliable enough to act on.
- Keep automatic agent/model switching explicit until quality and performance tradeoffs are better specified.

## 12. Capability Discovery And Setup Guidance

The farm should be easy for both technical and non-technical users, but the expected non-technical surface is often a primary AI such as GPT, Claude, or Codex.

Discovery paths:

- Static docs for humans.
- AI-facing docs for primary assistants.
- Machine-readable capabilities file such as `farm-capabilities.json`.
- Implemented first doctor command for local setup reports.
- Future runtime endpoint such as `GET /farm/capabilities`.

Capability discovery should report:

- OS.
- Python version.
- Ollama availability/version.
- installed models.
- RAM.
- GPU and VRAM when discoverable.
- disk space.
- available agents.
- supported modes.
- chunking support.
- tokenizer dependency and cache readiness.
- output schemas.

Implemented first command:

```bash
python qwen.py farm doctor
```

Possible outputs:

```text
.run/reports/setup-doctor.md
.run/reports/setup-doctor.json
```

The point is not just troubleshooting. The primary AI should be able to inspect the report, explain tradeoffs, choose a safe local model/profile for the user's machine, and guide tokenizer setup for token-aware chunking when useful.

## Proposed Milestones

### Milestone 1: Durable Jobs

- Implemented: filesystem-backed process-now farm run.
- Implemented: `farm run`, `farm list`, and `farm status`.
- Implemented: `FARM_STATUS.md` plus `farm-status.json`.
- Implemented: per-job Markdown, JSON, and raw response artifacts.
- Implemented: `farm collect` for post-run result collection.
- Deferred: queue-only runs.
- Deferred: long-running worker loop.

### Milestone 2: Structured Results

- Implemented: Markdown plus JSON sidecar outputs.
- Implemented: `summarize` result contract first.
- Implemented: generic custom-prompt support.
- Implemented: verified verbatim source snippets for `summarize`, with deterministic ranking and compact diagnostics.
- Implemented: first AI-facing usage doc.
- Implemented: first output schema folder and model-free validation helper.
- Implemented: public schema validation CLI.
- Implemented: post-run package schemas for timing, snippet, synthesis, and dogfood JSON artifacts.

### Milestone 2a: Early Mode Rollout

- `extract`.
- `classify`.
- `review`.

### Milestone 3: Chunked Workflows

- Implemented: paragraph-aware chunking for summarize mode.
- Implemented: map/reduce summarization for oversized summarize inputs.
- Implemented: opt-in tokenizer-aware chunk sizing for supported Qwen/Ollama agents.
- Implemented: configurable chunk/reduce retry limits.
- Implemented: Markdown heading ancestry.
- Implemented: optional chunk overlap.
- Implemented: in-progress chunk and reduce status visibility.
- Later: rerun failed chunks from prior runs.

### Milestone 4: Worker Farm

- Implemented: runtime profiles and resolved run config artifacts.
- Implemented: bounded file-job scheduler concurrency from resolved profile settings.
- Implemented: first-class resource modes with deterministic `auto` resolution and CPU enforcement.
- Implemented: fixed failure-policy retry/timeout knobs.
- Implemented: failed-file retry from prior runs.
- Later: dynamic scheduler backoff and resource fallback.
- Later: queue-only, background workers, and watch-folder workflows.

### Milestone 5: AI Skill Layer

- Tool-agnostic instructions for other AIs.
- Codex/Claude Code usage examples.
- Clear guidance for when to use local workers vs primary assistant context.
- Stable local worker contract.
- Capability discovery file and/or endpoint.

### Milestone 6: Guided Setup And Resource Fit

- Implemented: `doctor` command.
- Implemented: machine capability and readiness report.
- Implemented: benchmark-based model/profile/concurrency recommendations.
- Implemented: safe recommendation config apply.
- Next: hardware-specific model installation guidance.

## Groomed Next Decisions

These are the active product decisions after the first 31 change specs:

1. After dogfooding `include`/`exclude`, is `.qwenignore`, force-include, or richer discovery diagnostics the next useful file-discovery step?
2. How small can the model-family adapter foundation stay while making future Llama/Mistral/Gemma/Phi support straightforward?
3. Which post-run package controls matter first: field filters, fitting policy, or snippet-pack budgets?
4. Which new mode earns first-class treatment first: `extract`, `classify`, or `review`?
