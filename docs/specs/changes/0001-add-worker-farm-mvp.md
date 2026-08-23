# 0001 Add Worker Farm MVP

Status: Accepted
Type: Add

## WHY

The existing project supports immediate local asks, but the intended next step is offline delegated work: a primary AI should be able to say "work these files here and put results there" without the human supervising each step.

This change adds the first behavior contract for that worker-farm capability while keeping the experience file-and-folder based for non-technical users.

The design favors:

- filesystem visibility over database-first internals
- process-now behavior over mysterious queued-only behavior
- AI-readable status over human-only logs
- Markdown plus JSON outputs over model prose alone

## Scope

This change proposes adding the first worker-farm MVP behavior described in [accepted/farm-mvp.md](../accepted/farm-mvp.md).

It covers:

- `python qwen.py farm run`
- `python qwen.py farm list`
- `python qwen.py farm status`
- `python qwen.py farm status <run-id>`
- folder input
- filesystem-backed run folders
- file-level sub-jobs
- status artifacts
- result artifacts
- `summarize` mode
- `prompt` mode

## Non-Goals

This change does not add:

- scheduler/daemon behavior
- drop-folder scanning
- queue-only runs
- chunking
- HTTP farm endpoints
- SQLite
- capability endpoint
- `doctor`
- non-text file processing
- `farm collect`

## Behavior

### Command

Add:

```bash
python qwen.py farm run input-folder --output results --mode summarize
python qwen.py farm run input-folder --mode prompt --instructions "Apply this instruction to each file."
python qwen.py farm list
python qwen.py farm status
python qwen.py farm status <run-id>
```

`--output` is optional.

If omitted, output is written under `.run/farm/`.

If provided, the farm creates a run folder under the provided destination.

### Run Storage

Use filesystem-backed run folders.

Default farm home:

```text
.run/farm/
```

Run ID format:

```text
farm-run-YYYY-MM-DD-HHMMSS-xxxx
```

where `xxxx` is a short random suffix.

### Job Storage

Job folders use stable numeric sequence names:

```text
jobs/job-0001/
jobs/job-0002/
```

Input paths are recorded in JSON, not encoded into job folder names.

### Processing

The command processes immediately by default.

The input is one folder. Each eligible readable text file becomes a sub-job.

### Status

Each run writes:

```text
FARM_STATUS.md
farm-status.json
```

Status updates after each file/sub-job.

`farm-status.json` uses a flat run-level envelope with embedded job summaries.

### Results

Each completed sub-job writes:

```text
result.md
result.json
raw-response.txt
```

The farm owns the JSON envelope and should not rely on model prose as the only source of truth.

The `summarize` result payload includes:

```json
{
  "title": "Short title",
  "abstract": "One compact paragraph summarizing the file.",
  "bullets": ["...", "..."],
  "open_questions": [],
  "confidence": "low|medium|high"
}
```

### Failure

Default failure behavior:

- `max_attempts`: 2 total attempts
- `per_file_timeout_seconds`: 600
- `run_timeout_seconds`: null
- retry each failed file/sub-job once
- continue with remaining files if retry fails
- mark the run `partial` if any sub-job fails after retry

## Acceptance Criteria

- The CLI accepts `python qwen.py farm run <input-folder> --mode summarize`.
- The CLI accepts `python qwen.py farm run <input-folder> --mode prompt --instructions <text>`.
- The CLI accepts optional `--output <dir>`.
- The CLI supports `python qwen.py farm list`.
- The CLI supports `python qwen.py farm status`.
- The CLI supports `python qwen.py farm status <run-id>`.
- The farm creates a run folder with a timestamp-plus-suffix run ID.
- The default farm home is `.run/farm/`.
- The farm creates job folders using `job-0001`, `job-0002`, and so on.
- The farm discovers eligible readable text files under the input folder.
- The farm skips obvious generated/vendor/binary/non-text inputs.
- The farm processes files immediately by default.
- The farm updates `farm-status.json` after each file/sub-job.
- The farm writes `FARM_STATUS.md`.
- `farm-status.json` includes run fields, counts, and embedded job summaries.
- Each completed sub-job writes Markdown, JSON, and raw-output artifacts.
- `summarize` result JSON uses `abstract` for the compact machine-readable paragraph.
- One failed file does not stop the whole run after retry is exhausted.
- The run status is `complete`, `complete_with_warnings`, `partial`, or `failed` as appropriate.

## Deferred To Roadmap

- CLI spelling for future non-MVP modes.
- Full schema files for status/result validation.
- Skip-list overrides.
- Caller-provided retry/timeout behavior.
- `farm collect`.
- Queue-only execution.
- Drop-folder scanning.
- Chunking.
