# Farm MVP

Status: Draft

## WHY

The farm exists so a primary AI can delegate local, slower, offline work without making the human manage a separate system.

The first MVP should be file-and-folder based because that is legible to both non-technical users and AI callers. More technical storage can come later behind the same abstraction.

This spec protects the core product shape:

```text
Human -> primary AI -> local farm -> staged outputs/status -> primary AI -> human
```

The farm should do useful work immediately, write durable artifacts, and expose enough status for a primary AI to inspect progress and decide what to do next.

## Scope

This spec covers the first worker-farm MVP:

- filesystem-first farm state
- command shape
- folder input
- run folder creation
- readable text file discovery
- file-level sub-jobs
- process-now default
- status artifacts
- Markdown and JSON result artifacts
- first mode rollout

## Non-Goals

This spec does not require:

- SQLite or database-backed state
- long-running scheduler
- automatic drop-folder watcher
- HTTP farm endpoints
- chunking implementation
- strict JSON Schema validation
- compare/transform/research-pack modes
- PDF, Office, image, archive, or binary processing
- human-visible UI beyond files and CLI output

## Behavior

### Farm Home

Default farm state lives under:

```text
.run/farm/
```

A future override may use:

```text
QWEN_FARM_HOME
```

### Run IDs

Run IDs use timestamp plus a short random suffix:

```text
farm-run-2026-08-23-143022-a7f3
```

Run IDs must sort chronologically and avoid collisions without a shared counter.

### Command Shape

The first worker-farm command should use the farm namespace:

```bash
python qwen.py farm run input-folder --output results --mode summarize
```

Expected future sibling commands:

```bash
python qwen.py farm list
python qwen.py farm status <run-id>
python qwen.py farm collect <run-id>
python qwen.py farm scan
```

### Execution Model

The MVP `farm run` command processes immediately by default.

A future `--queue-only` option may create a run without processing it.

### Input

The first-class input is one folder.

Each eligible readable text file in the folder is treated as a sub-job.

The farm should skip:

- binary files
- generated/vendor folders such as `.git/`, `node_modules/`, `bin/`, `obj/`, `dist/`, `build/`, and `__pycache__/`
- archives
- images
- PDFs
- Office documents
- minified assets

Include/exclude override rules may come later.

### Output

If `--output` is omitted, outputs are written under the run folder in the farm home.

If `--output` is provided, the farm creates a structured run folder inside the destination.

Example:

```text
results/
  farm-run-2026-08-23-143022-a7f3/
    FARM_STATUS.md
    farm-status.json
    outputs/
      article-a.summary.md
      article-a.summary.json
    jobs/
      job-001/
        input.json
        raw-response.txt
        log.md
```

The caller chooses the destination area. The farm owns the run structure inside it.

### Status

Each run produces:

```text
FARM_STATUS.md
farm-status.json
```

`farm-status.json` is the machine-readable source of truth. `FARM_STATUS.md` is the human-readable rendering.

Status should update after each file/sub-job.

Expected statuses:

```text
queued
running
complete
complete_with_warnings
partial
failed
```

### Results

Each completed job should produce:

```text
result.md
result.json
raw-response.txt
```

The farm owns the deterministic JSON envelope. The model produces the mode-specific `result` payload.

If model JSON is invalid:

1. Retry once with a repair prompt.
2. If repair succeeds, continue.
3. If repair fails, preserve raw output, mark `structured_valid: false`, and keep any Markdown artifact that can be produced.

### Failure Policy

Default behavior:

- retry a failing file/sub-job
- if retry fails, mark that job failed
- continue remaining jobs
- mark the run `partial` if any job failed
- mark the run `complete_with_warnings` if all jobs completed but warnings exist

Caller-provided failure policy may come later.

### Mode Rollout

Initial implementation order:

1. `summarize` or custom prompt.
2. `extract`.
3. `classify`.
4. `review`.

The first implementation should provide a named `summarize` mode while keeping the internals generic enough for custom prompt-per-file behavior.

## Acceptance Criteria

- `python qwen.py farm run <input-folder> --mode summarize` creates a farm run.
- The run ID uses timestamp plus short random suffix.
- The run uses `.run/farm/` when no output destination is provided.
- When `--output <dir>` is provided, the run folder is created inside `<dir>`.
- The farm discovers eligible readable text files inside the input folder.
- The farm skips obvious binary, generated, vendor, archive, image, PDF, Office, and minified files.
- The farm creates `farm-status.json` and `FARM_STATUS.md`.
- Status updates after each file/sub-job.
- Each completed file/sub-job has Markdown and JSON result artifacts.
- Raw model output is preserved for each job.
- One failed file does not stop the whole run after retry is exhausted.
- A run with one or more failed jobs is marked `partial`.
- A clean run is marked `complete`.
- The implementation has tests or manual verification covering happy path, skipped files, one failed file, and output destination behavior.

## Open Questions

- Exact `farm-status.json` schema.
- Exact `result.json` schema for `summarize`.
- Exact job folder naming scheme.
- Exact retry count and timeout defaults.
- Whether custom prompt should be a `mode` value or an option under `summarize`.
- Whether the first implementation should include `farm list` and `farm status`, or only write artifacts.
