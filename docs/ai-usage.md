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

Custom prompt invocation:

```bash
python qwen.py farm run input-folder --mode prompt --instructions "For each file, identify risks and next actions."
```

Status inspection:

```bash
python qwen.py farm list
python qwen.py farm status
python qwen.py farm status <run-id>
```

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
```

The JSON status and result files are the source of truth for primary AIs and scripts. Markdown files exist for human inspection and readable summaries.

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

The farm should eventually support an AI-guided setup path.

Future command:

```bash
python qwen.py doctor
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
- whether more setup is needed

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
