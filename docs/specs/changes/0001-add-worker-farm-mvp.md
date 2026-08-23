# 0001 Add Worker Farm MVP

Status: Draft
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

This change proposes adding the first worker-farm MVP behavior described in [drafts/farm-mvp.md](../drafts/farm-mvp.md).

It covers:

- `python qwen.py farm run`
- folder input
- filesystem-backed run folders
- file-level sub-jobs
- status artifacts
- result artifacts
- first `summarize` mode
- generic custom-prompt-capable internals

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

## Behavior

### Command

Add:

```bash
python qwen.py farm run input-folder --output results --mode summarize
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

### Results

Each completed sub-job writes:

```text
result.md
result.json
raw-response.txt
```

The farm owns the JSON envelope and should not rely on model prose as the only source of truth.

### Failure

If a file/sub-job fails, retry it. If it still fails, mark that sub-job failed and continue with remaining files.

The run is `partial` if at least one sub-job fails after retry.

## Acceptance Criteria

- The CLI accepts `python qwen.py farm run <input-folder> --mode summarize`.
- The CLI accepts optional `--output <dir>`.
- The farm creates a run folder with a timestamp-plus-suffix run ID.
- The default farm home is `.run/farm/`.
- The farm discovers eligible readable text files under the input folder.
- The farm skips obvious generated/vendor/binary/non-text inputs.
- The farm processes files immediately by default.
- The farm updates `farm-status.json` after each file/sub-job.
- The farm writes `FARM_STATUS.md`.
- Each completed sub-job writes Markdown, JSON, and raw-output artifacts.
- One failed file does not stop the whole run after retry is exhausted.
- The run status is `complete`, `complete_with_warnings`, `partial`, or `failed` as appropriate.
- The first mode supports summarization.
- The implementation is structured so custom prompt-per-file behavior can be added without redesigning run storage.

## Open Questions

- Exact CLI spelling for future custom prompt support.
- Exact summary JSON result shape.
- Exact status JSON shape.
- Exact skip-list defaults.
- Exact retry count and timeout behavior.
- Whether implementation should include `farm list` and `farm status` in the same PR.
