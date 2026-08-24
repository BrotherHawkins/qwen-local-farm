# Roadmap

This project starts as a simple local Qwen service, but the intended direction is broader: a local worker layer that other AIs, scripts, and systems can use when work is better done offline, privately, slowly, or in parallel.

The roadmap below is intentionally lightweight. It captures the shape of the next system without pretending every interface is already designed.

## Roadmap Docs

- [AI usage and delegation](ai-usage.md): how GPT, Claude, Codex, scripts, and other callers should decide when to use the farm.
- [Chunking roadmap](chunking-roadmap.md): how the farm should eventually handle files or folders that exceed a model's context window.

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

1. Harden the worker-farm MVP after real use.
2. Add chunking and map/reduce workflows for large inputs.
3. Add stricter structured output conventions and schema helpers.
4. Add AI-facing usage docs and skills.
5. Explore processing modes beyond plain chat/summarization.
6. Add observability for job status, model routing, failures, and output review.
7. Add capability discovery and guided setup reports.

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

Roadmap:

- Add queue-only runs for offline work with a simple first contract: "work these inputs here, put results over there."
- Add a stable run/job object with `id`, `status`, `agent`, `model`, `input`, `output`, `created_at`, `started_at`, `finished_at`, and `error`.
- Add commands:
  - `python qwen.py farm collect <run-id>`
  - `python qwen.py farm scan`
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

Likely next PR:

- Add chunking or schema hardening based on the first real farm usage.

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

## 3. Structured Output

Current state:

- Agent responses are plain model text.
- Some benchmark scripts write JSON records, but normal agent outputs are not schema-driven yet.

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
- Ask the model only for the mode-specific `result` payload.
- If the model returns invalid JSON, retry once with a repair prompt.
- If repair still fails, preserve raw output, mark `structured_valid: false`, and keep whatever Markdown artifact can be produced.

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

- Should structured output use strict JSON Schema, Pydantic-style examples, or lightweight repo-native schemas?
- Which output contracts should be first-class, and which should stay prompt-level conventions?

Likely next PR:

- Add `schemas/` with a few simple JSON output contracts and document how agents can request them.

## 4. Chunking Larger Context

Current state:

- Current scripts assume the input fits inside the selected model context.
- 8B and 14B tests used a `4096` token context.

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

Likely next PR:

- Add `docs/chunking-roadmap.md` first, then a Markdown chunker and summarization map/reduce benchmark path.

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

Likely next PR:

- Add a few mode templates as agent configs and document how to choose between them.

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
- Add include/exclude overrides later.

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

Default failure policy:

- Retry a failing file/sub-job.
- If it still fails, mark that sub-job failed.
- Continue processing remaining files.
- Mark the run `partial` if any file failed.
- Mark the run `complete_with_warnings` if outputs exist but structured repair or other non-fatal issues occurred.

Longer term, failure behavior should be caller-provided:

```json
{
  "failure_policy": {
    "max_attempts": 2,
    "on_file_failure": "continue",
    "on_schema_failure": "repair_then_warn",
    "on_run_failure": "stop"
  }
}
```

Review policy should be mode-dependent and caller-configurable. Some results may be final enough for automation, while others should be staged for human or AI review.

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
- Hybrid and CPU/RAM modes are manually selected.

Roadmap:

- Add model routing rules that consider speed, VRAM pressure, job type, and expected quality.
- Add a simple worker scheduler:
  - max concurrent jobs
  - only run heavy jobs when allowed
  - pause/resume
  - retry failed jobs
- Add keep-warm settings for frequently used models.
- Add user-level farm availability: enabled, disabled, ask before use.

Open questions:

- Should the worker farm run one model at a time to avoid memory contention?
- Should heavy 14B jobs require an explicit queue/mode label?
- Should GPU use be opt-in for background jobs?

Likely next PR:

- Add a resource policy doc and a basic `workers.json` configuration sketch.

## 12. Capability Discovery And Setup Guidance

The farm should be easy for both technical and non-technical users, but the expected non-technical surface is often a primary AI such as GPT, Claude, or Codex.

Future discovery paths:

- Static docs for humans.
- AI-facing docs for primary assistants.
- Machine-readable capabilities file such as `farm-capabilities.json`.
- Runtime endpoint such as `GET /farm/capabilities`.

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
- output schemas.

Likely future command:

```bash
python qwen.py doctor
```

Possible outputs:

```text
.run/reports/setup-doctor.md
.run/reports/setup-doctor.json
```

The point is not just troubleshooting. The primary AI should be able to inspect the report, explain tradeoffs, and choose a safe local model/profile for the user's machine.

## Proposed Milestones

### Milestone 1: Durable Jobs

- Implemented: filesystem-backed process-now farm run.
- Implemented: `farm run`, `farm list`, and `farm status`.
- Implemented: `FARM_STATUS.md` plus `farm-status.json`.
- Implemented: per-job Markdown, JSON, and raw response artifacts.
- Deferred: `farm collect`.
- Deferred: queue-only runs.
- Deferred: long-running worker loop.

### Milestone 2: Structured Results

- Implemented: Markdown plus JSON sidecar outputs.
- Implemented: `summarize` result contract first.
- Implemented: generic custom-prompt support.
- Implemented: first AI-facing usage doc.
- Next: output schema folder.
- Next: stricter validation helpers.

### Milestone 2a: Early Mode Rollout

- `extract`.
- `classify`.
- `review`.

### Milestone 3: Chunked Workflows

- Implemented: paragraph-aware chunking for summarize mode.
- Implemented: map/reduce summarization for oversized summarize inputs.
- Markdown heading-aware chunking.
- Provenance tracking.
- Rerun failed chunks.

### Milestone 4: Worker Farm

- Worker configuration.
- Resource-aware routing.
- Multiple processing modes.
- Watch-folder or batch-folder workflows.

### Milestone 5: AI Skill Layer

- Tool-agnostic instructions for other AIs.
- Codex/Claude Code usage examples.
- Clear guidance for when to use local workers vs primary assistant context.
- Stable local worker contract.
- Capability discovery file and/or endpoint.

### Milestone 6: Guided Setup And Resource Fit

- `doctor` command.
- Machine capability report.
- Model/profile recommendations.
- Human-readable and AI-readable setup reports.

## Immediate Next Decisions

These are the decisions to make before implementation gets too deep:

1. Job storage layout: exact folder/file names under `.run/farm/`.
2. Output schema: first `summarize` JSON result shape.
3. Custom prompt contract: how much structure is required when mode is prompt-driven.
4. Chunking strategy: Markdown heading chunks first, tokenizer-aware chunks later?
5. Worker behavior beyond MVP: manually run workers only, or background scheduler?
6. AI integration: docs-only first, or generate reusable skill/instruction files immediately?
7. Capability discovery: static JSON first, runtime endpoint first, or both together?
