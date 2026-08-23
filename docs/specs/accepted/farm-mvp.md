# Farm MVP

Status: Accepted

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
- `summarize` and `prompt` modes
- default retry and timeout behavior

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
- queue-only runs
- `farm collect`

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

The first worker-farm commands use the farm namespace:

```bash
python qwen.py farm run input-folder --output results --mode summarize
python qwen.py farm list
python qwen.py farm status
python qwen.py farm status <run-id>
```

`farm status` with no run ID shows a farm overview.

`farm status <run-id>` shows one run.

### Execution Model

The MVP `farm run` command processes immediately by default.

`--queue-only` is deferred.

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

Include/exclude override rules are deferred.

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
      job-0001/
        input.json
        raw-response.txt
        log.md
```

The caller chooses the destination area. The farm owns the run structure inside it.

### Job Folder Naming

Job folders use stable numeric sequence names:

```text
jobs/
  job-0001/
  job-0002/
  job-0003/
```

Job folder names do not encode input paths. Input identity is stored in JSON.

### Status

Each run produces:

```text
FARM_STATUS.md
farm-status.json
```

`farm-status.json` is the machine-readable source of truth. `FARM_STATUS.md` is the human-readable rendering.

Status updates after each file/sub-job.

Expected run statuses:

```text
queued
running
complete
complete_with_warnings
partial
failed
```

MVP `farm-status.json` uses a run-level envelope with embedded job summaries:

```json
{
  "schema_version": "0.1",
  "run_id": "farm-run-2026-08-23-143022-a7f3",
  "status": "running",
  "mode": "summarize",
  "agent": "qwen8",
  "model": "qwen3:8b",
  "input": {
    "path": "input-folder",
    "kind": "folder"
  },
  "output": {
    "path": "results/farm-run-2026-08-23-143022-a7f3"
  },
  "counts": {
    "total": 10,
    "queued": 2,
    "running": 1,
    "complete": 6,
    "complete_with_warnings": 0,
    "failed": 1,
    "skipped": 0
  },
  "jobs": [
    {
      "job_id": "job-0001",
      "status": "complete",
      "input_path": "notes/a.md",
      "result_json": "outputs/notes/a.summary.json",
      "result_md": "outputs/notes/a.summary.md",
      "raw_response": "jobs/job-0001/raw-response.txt",
      "error": null
    }
  ],
  "created_at": "2026-08-23T14:30:22Z",
  "updated_at": "2026-08-23T14:31:10Z"
}
```

The schema should remain flat and readable for MVP.

### Results

Each completed job should produce:

```text
result.md
result.json
raw-response.txt
```

The farm owns the deterministic JSON envelope. The model produces the mode-specific `result` payload.

The `summarize` mode result shape is:

```json
{
  "schema_version": "0.1",
  "job_id": "job-0001",
  "mode": "summarize",
  "status": "complete",
  "structured_valid": true,
  "input": {
    "path": "notes/a.md"
  },
  "result": {
    "title": "Short title",
    "abstract": "One compact paragraph summarizing the file.",
    "bullets": ["...", "..."],
    "open_questions": [],
    "confidence": "low|medium|high"
  },
  "artifacts": {
    "markdown": "outputs/notes/a.summary.md",
    "raw_response": "jobs/job-0001/raw-response.txt"
  },
  "model": {
    "agent": "qwen8",
    "model": "qwen3:8b"
  },
  "warnings": []
}
```

`result.abstract` is the compact machine-readable paragraph. `result.md` is the fuller human-readable rendering.

If model JSON is invalid:

1. Retry once with a repair prompt.
2. If repair succeeds, continue.
3. If repair fails, preserve raw output, mark `structured_valid: false`, and keep any Markdown artifact that can be produced.

### Failure Policy

Default behavior:

- `max_attempts`: 2 total attempts
- `per_file_timeout_seconds`: 600
- `run_timeout_seconds`: null
- retry a failing file/sub-job
- if retry fails, mark that job failed
- continue remaining jobs
- mark the run `partial` if any job failed
- mark the run `complete_with_warnings` if all jobs completed but warnings exist

Caller-provided failure policy is deferred.

### Modes

MVP modes:

1. `summarize`
2. `prompt`

`summarize` supports optional caller instructions:

```bash
python qwen.py farm run notes/ --mode summarize --instructions "Focus on risks and next actions."
```

`prompt` is the generic custom mode:

```bash
python qwen.py farm run notes/ --mode prompt --instructions "For each file, identify what changed and what looks risky."
```

Future mode rollout:

1. `extract`
2. `classify`
3. `review`

## Acceptance Criteria

- `python qwen.py farm run <input-folder> --mode summarize` creates a farm run.
- `python qwen.py farm run <input-folder> --mode prompt --instructions <text>` creates a farm run.
- `python qwen.py farm list` lists known farm runs.
- `python qwen.py farm status` shows farm overview.
- `python qwen.py farm status <run-id>` shows one run.
- The run ID uses timestamp plus short random suffix.
- The run uses `.run/farm/` when no output destination is provided.
- When `--output <dir>` is provided, the run folder is created inside `<dir>`.
- Job folders are named `job-0001`, `job-0002`, and so on.
- The farm discovers eligible readable text files inside the input folder.
- The farm skips obvious binary, generated, vendor, archive, image, PDF, Office, and minified files.
- The farm creates `farm-status.json` and `FARM_STATUS.md`.
- `farm-status.json` uses a run-level envelope with embedded job summaries.
- Status updates after each file/sub-job.
- Each completed file/sub-job has Markdown and JSON result artifacts.
- `summarize` result JSON includes `title`, `abstract`, `bullets`, `open_questions`, and `confidence`.
- Raw model output is preserved for each job.
- Each file/sub-job gets at most two total attempts by default.
- Per-file timeout defaults to 600 seconds.
- There is no whole-run timeout by default.
- One failed file does not stop the whole run after retry is exhausted.
- A run with one or more failed jobs is marked `partial`.
- A clean run is marked `complete`.
- The implementation has tests or manual verification covering happy path, skipped files, one failed file, output destination behavior, `farm list`, farm overview status, and one-run status.

## Deferred To Roadmap

- SQLite or database-backed state.
- Queue-only runs.
- `farm collect`.
- Drop-folder scanning.
- HTTP farm endpoints.
- Chunking.
- Include/exclude overrides.
- Caller-provided failure policies.
- `extract`, `classify`, and `review` modes.
- Strict schema tooling.
