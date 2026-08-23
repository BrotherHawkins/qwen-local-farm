# Roadmap

This project starts as a simple local Qwen service, but the intended direction is broader: a local worker layer that other AIs, scripts, and systems can use when work is better done offline, privately, slowly, or in parallel.

The roadmap below is intentionally lightweight. It captures the shape of the next system without pretending every interface is already designed.

## North Star

Build a local AI worker farm with two clear interaction modes:

| Mode | Purpose | Expected Feel |
| --- | --- | --- |
| Immediate ask | Ask a local model now and get an answer in the current flow. | Interactive, simple, low ceremony. |
| Worker farm | Submit offline jobs and let local models process them when resources are available. | Queue-based, durable, inspectable, resumable. |

The system should be useful to humans directly, but also easy for other AIs to invoke from tools like Codex, Claude Code, scripts, or local automations.

## Near-Term Priorities

1. Define the worker-farm job model.
2. Add structured output conventions.
3. Add chunking and map/reduce workflows for large inputs.
4. Add AI-facing usage docs and skills.
5. Explore processing modes beyond plain chat/summarization.
6. Add observability for job status, model routing, failures, and output review.

## 1. Immediate Ask vs Worker Farm

Current state:

- `python qwen.py ask "..." [agent-id]` supports immediate local asks.
- The gateway exposes synchronous chat endpoints.

Roadmap:

- Add a job queue for offline work.
- Add a stable job object with `id`, `status`, `agent`, `model`, `input`, `output`, `created_at`, `started_at`, `finished_at`, and `error`.
- Store job inputs and outputs under `.run/jobs/` by default.
- Add commands:
  - `python qwen.py submit <file-or-folder> --agent qwen14-hybrid`
  - `python qwen.py jobs`
  - `python qwen.py job <id>`
  - `python qwen.py collect <id>`
- Let immediate asks remain simple and separate from queued work.

Open questions:

- Should queued jobs be plain filesystem records first, SQLite later, or SQLite from the start?
- Should workers run only when explicitly started, or should there be a background scheduler?
- Should job outputs be staged as Markdown, JSON, or both?

Likely next PR:

- Add a minimal filesystem-backed job queue with submit/list/show commands and one worker loop.

## 2. Structured Output

Current state:

- Agent responses are plain model text.
- Some benchmark scripts write JSON records, but normal agent outputs are not schema-driven yet.

Roadmap:

- Define a small set of output contracts:
  - `text`: freeform Markdown.
  - `summary`: title, bullets, key claims, uncertainty notes.
  - `extraction`: entities, facts, dates, links, tags.
  - `review`: findings, severity, evidence, recommendations.
  - `decision`: options, tradeoffs, recommendation, confidence.
- Add optional JSON-schema-like output definitions to agent configs.
- Support both human-readable Markdown and machine-readable JSON sidecars.
- Validate structured outputs before marking a job complete.

Open questions:

- Should structured output use strict JSON Schema, Pydantic-style examples, or lightweight repo-native schemas?
- Should invalid JSON trigger automatic repair retries?
- Which output contracts should be first-class, and which should stay prompt-level conventions?

Likely next PR:

- Add `schemas/` with a few simple JSON output contracts and document how agents can request them.

## 3. Chunking Larger Context

Current state:

- Current scripts assume the input fits inside the selected model context.
- 8B and 14B tests used a `4096` token context.

Roadmap:

- Add chunking support for files and folders.
- Start with conservative Markdown-aware chunking:
  - split by headings first
  - preserve frontmatter and path metadata
  - keep chunks under a target token/character budget
  - include neighboring heading context
- Add map/reduce workflows:
  - map: process each chunk independently
  - reduce: combine chunk outputs into a final answer
  - refine: optionally run a second pass over the aggregate
- Track provenance so final outputs know which source files/chunks contributed.

Open questions:

- Should chunking be character-based first, or add tokenizer support early?
- Should chunk outputs be visible review artifacts, or hidden intermediates?
- How should a user approve, reject, or rerun individual chunks?

Likely next PR:

- Add a Markdown chunker and a summarization map/reduce benchmark path.

## 4. AI-Agnostic Skills And Usage Patterns

Current state:

- Humans can call the service through CLI or HTTP.
- Other AIs can call the Ollama/OpenAI-compatible endpoint or the gateway if instructed.

Roadmap:

- Add AI-facing docs that explain when to farm work out and when not to.
- Keep instructions tool-agnostic enough for Codex, Claude Code, local scripts, and future agents.
- Define a small "local worker contract":
  - service discovery
  - available agents
  - how to submit immediate asks
  - how to submit offline jobs
  - how to retrieve outputs
  - expected failure handling
- Add copy-pasteable agent instructions under `docs/ai-usage.md`.

Good times to farm work out:

- Long summarization or extraction tasks.
- Private/offline document processing.
- Batch transformations.
- Slow background analysis where latency is not important.
- Independent review passes using a different model.

Bad times to farm work out:

- User is actively waiting and the local model is much slower than the primary assistant.
- The task requires tools/files the local worker cannot access.
- The answer must be highly reliable and no review loop is available.
- The prompt includes sensitive data that should not be written to local job artifacts.

Likely next PR:

- Add `docs/ai-usage.md` with invocation patterns for immediate asks and queued jobs.

## 5. Alternate Processing Modes

Current state:

- The project supports chat-style prompts and summarization benchmarks.

Candidate modes:

| Mode | Example Use |
| --- | --- |
| Summarize | Turn long notes/articles into concise summaries. |
| Extract | Pull entities, dates, claims, tasks, links, or citations from documents. |
| Classify | Assign tags, priority, risk, topic, or routing labels. |
| Compare | Compare two files, summaries, versions, or proposals. |
| Review | Produce findings with severity and evidence. |
| Transform | Convert input to another format, such as Markdown, JSON, tasks, or outline. |
| Research pack | Process a folder into staged notes, index files, and follow-up questions. |
| Watch folder | Process new files dropped into an inbox directory. |

Open questions:

- Which modes deserve first-class commands?
- Which modes should just be agent presets?
- Should modes have different default models, temperatures, and output schemas?

Likely next PR:

- Add a few mode templates as agent configs and document how to choose between them.

## 6. Scheduling, Resources, And Routing

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

Open questions:

- Should the worker farm run one model at a time to avoid memory contention?
- Should heavy 14B jobs require an explicit queue/mode label?
- Should GPU use be opt-in for background jobs?

Likely next PR:

- Add a resource policy doc and a basic `workers.json` configuration sketch.

## Proposed Milestones

### Milestone 1: Durable Jobs

- Filesystem-backed job queue.
- Submit/list/show/collect commands.
- Job outputs written to `.run/jobs/`.
- One local worker loop.

### Milestone 2: Structured Results

- Output schema folder.
- Markdown plus JSON sidecar outputs.
- Validation and repair retry for JSON results.
- First AI-facing usage doc.

### Milestone 3: Chunked Workflows

- Markdown-aware chunking.
- Map/reduce summarization.
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

## Immediate Next Decisions

These are the decisions to make before implementation gets too deep:

1. Job storage: filesystem first or SQLite first?
2. Output format: Markdown primary with JSON sidecars, or JSON primary with Markdown renderings?
3. Chunking strategy: Markdown heading chunks first, tokenizer-aware chunks later?
4. Worker behavior: manually run workers only, or background scheduler?
5. AI integration: docs-only first, or generate reusable skill/instruction files immediately?
