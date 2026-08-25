# 0027 Add In-Progress Chunk And Reduce Status

Status: Implemented
Type: Add

## WHY

Dogfood runs now have enough chunking, retries, token-aware planning, and reduce work that a run can be healthy while still looking stuck.

During 0026 dogfood, chunk input files and chunk result files appeared while a job was running, but `farm-status.json` still showed the job as a generic `running` job with placeholder single-pass chunking and no model-call records until the whole file finished. That made it harder for a primary AI or human to answer basic questions:

- Which chunk is running now?
- How many chunks are done?
- Has reduce started?
- Is the current model call actually long, or is the farm doing local preprocessing?
- Did a retry happen while the job was still active?

The farm already has durable timing data after completion. This change makes the same status path useful while work is in progress, without adding streaming tokens, a UI, or a separate watcher.

This change implements:

- BL-0038: in-progress chunk and reduce timing/status visibility

The product principle is: if the farm is meant to be delegated to by a primary AI, the primary AI should be able to inspect progress from stable artifacts instead of guessing from partial files.

## Scope

This change adds additive in-progress progress metadata to existing farm run status artifacts:

- update `farm-status.json` while a chunked summarize job progresses through planning, chunk map calls, and reduce calls
- update `FARM_STATUS.md` with concise active phase, chunk counts, reduce counts, and current call information
- expose the same data naturally through existing `python sift.py farm status <run-id>` and `python sift.py farm status <run-id> --json`
- persist active and completed model-call records in job timing while the job is still running
- make planned chunk counts visible shortly after chunk planning completes
- make completed, running, failed, and queued chunk counts visible during chunk map work
- make reduce generation and batch progress visible during reduce work
- keep completed run and result artifact shapes compatible except for additive fields
- update tracked schemas for affected persisted JSON shapes
- add model-free tests using fake processors and controlled long-running hooks or status writer seams
- update docs for users and AI callers
- update BL-0038 lifecycle as the spec moves through acceptance and implementation

The first implementation should prefer simple status rewrites at phase boundaries and model-call start/completion over high-frequency updates.

## Non-Goals

This change does not add:

- token streaming
- live progress bars
- `farm status --watch`
- a TUI or web dashboard
- pause, cancel, or resume controls
- queue-only runs
- background worker management
- cross-run chunk resume
- retrying failed files from a previous run
- stale/interrupted process detection or repair for old runs
- whole-run timeout enforcement
- true wall-clock whole-file timeout enforcement
- token-per-second backend metrics
- chunk-level parallelism
- model calls in CI

## Behavior

### Status Shape

Each job in `farm-status.json` may include a `progress` object while it is running. The object remains useful after completion, but terminal job status and existing timing fields stay authoritative for completed jobs.

Example for a chunk map phase:

```json
{
  "job_id": "job-0002",
  "status": "running",
  "input_path": "004-tags-guide-obsidian-claude-code-karpathy-pkm-llm.txt",
  "chunking": {
    "enabled": true,
    "strategy": "paragraph-token",
    "chunk_count": 6,
    "coverage": "full",
    "tokenizer": "Qwen/Qwen3.5-4B",
    "counts_are_estimated": false
  },
  "progress": {
    "phase": "chunk_map",
    "message": "Summarizing chunk 3 of 6.",
    "updated_at": "2026-08-24T23:21:42.123Z",
    "chunks": {
      "total": 6,
      "queued": 3,
      "running": 1,
      "complete": 2,
      "failed": 0,
      "current": "chunk-0003"
    },
    "reduce": {
      "generation": null,
      "batch_index": null,
      "batch_total": null,
      "complete": 0
    },
    "current_call": {
      "kind": "chunk_map",
      "file_path": "004-tags-guide-obsidian-claude-code-karpathy-pkm-llm.txt#chunk-0003",
      "chunk_id": "chunk-0003",
      "attempt": 1,
      "max_attempts": 1,
      "started_at": "2026-08-24T23:21:42.120Z",
      "duration_ms": null,
      "status": "running"
    }
  }
}
```

Example for reduce:

```json
{
  "progress": {
    "phase": "reduce",
    "message": "Reducing chunk summaries.",
    "updated_at": "2026-08-24T23:22:12.456Z",
    "chunks": {
      "total": 6,
      "queued": 0,
      "running": 0,
      "complete": 6,
      "failed": 0,
      "current": null
    },
    "reduce": {
      "generation": 1,
      "batch_index": 1,
      "batch_total": 1,
      "complete": 0
    },
    "current_call": {
      "kind": "reduce",
      "file_path": "004-tags-guide-obsidian-claude-code-karpathy-pkm-llm.txt",
      "attempt": 1,
      "max_attempts": 1,
      "started_at": "2026-08-24T23:22:12.450Z",
      "duration_ms": null,
      "status": "running"
    }
  }
}
```

Allowed first-pass phases:

- `queued`
- `starting`
- `single`
- `planning_chunks`
- `chunk_map`
- `reduce`
- `complete`
- `failed`
- `skipped`

If implementation finds fewer phases clearer, it may use a smaller stable subset as long as the acceptance criteria remain satisfied.

### Call Timing While Running

`timing.calls` should become useful before the job reaches a terminal state.

When a model call starts, the status artifact should include a call record with:

- `kind`
- `file_path`
- `started_at`
- `completed_at: null`
- `duration_ms: null`
- `attempt`
- `max_attempts`
- `status: "running"`
- `chunk_id` for chunk map calls
- reduce generation or batch fields for reduce calls when known

When the call completes or fails, the same status path should be updated with:

- `completed_at`
- `duration_ms`
- `status: "complete"` or `"failed"`
- `error` for failed calls when available

This does not require preserving object identity in memory; it only requires the persisted status to read as a coherent call ledger.

### Chunk Planning Visibility

For chunked summarize jobs, once chunk planning completes and before the first chunk map call starts, status should show:

- `chunking.enabled: true`
- chunk strategy
- chunk count
- tokenizer and exact/estimated count metadata when available
- progress phase `chunk_map` or `planning_chunks`
- chunk counters with total and queued counts

This fixes the misleading placeholder where a chunked job still appears as `single-pass` while already producing chunk artifacts.

### Reduce Visibility

During reduce work, status should show:

- phase `reduce`
- all chunk map work complete, unless a failure prevents reduce
- reduce generation when known
- batch index and total when a multi-batch reduce is active
- current reduce call attempt metadata

The first implementation does not need to predict the number of future reduce generations. It only needs to describe the reduce batch currently being attempted and how many batches are known for that generation.

### Markdown Status

`FARM_STATUS.md` should stay concise.

The job table may add compact progress text, or a small active jobs section may be added below the table. It should answer, for running jobs:

- active phase
- chunk count summary, such as `2/6 chunks complete, chunk-0003 running`
- reduce summary, such as `reduce generation 1 batch 1/2`
- current call elapsed time if available from timestamps or persisted duration

It should not dump every completed chunk call into the Markdown status table.

### JSON Status CLI

No new CLI flag is required.

Existing commands should benefit automatically because they already read status artifacts:

```powershell
python sift.py farm status farm-run-...
python sift.py farm status farm-run-... --json
```

The JSON output should include the same additive `progress` and in-progress `timing.calls` data found in `farm-status.json`.

### Write Frequency

The farm should update status at meaningful boundaries:

- job starts
- chunk planning starts, if practical
- chunk planning completes
- each model call starts
- each model call completes or fails
- reduce generation or batch starts
- job completes or fails

The first implementation should not update status on every generated token, every second, or every filesystem artifact write.

### Compatibility And Schemas

This change is additive to existing status/result artifacts.

Implementation should update tracked schemas for affected shapes, especially:

- `schemas/farm-status.schema.json`
- `schemas/farm-status-run.schema.json`
- `schemas/farm-job-result.schema.json` if result timing or progress fields are persisted there

Existing artifacts that omit `progress` should remain valid.

### Failure Behavior

If a chunk or reduce call fails and is retried, status should show the failed call record and the current retry attempt while the retry is running.

If the job ultimately fails, terminal status remains `failed`, existing `error` fields remain visible, and progress should not hide the original error.

Timing/progress collection must not mask or replace the original failure.

## Acceptance Criteria

- Running chunked summarize jobs update `farm-status.json` after chunk planning so `chunking.enabled`, strategy, and chunk count are visible before job completion.
- Running chunked summarize jobs expose a `progress` object with an active phase.
- During chunk map work, `progress.chunks` reports total, queued, running, complete, failed, and current chunk values.
- During chunk map work, `progress.current_call` identifies the active chunk map call and attempt.
- During reduce work, `progress.phase` is `reduce`.
- During reduce work, `progress.reduce` reports current generation and batch information when known.
- During reduce work, `progress.current_call` identifies the active reduce call and attempt.
- `timing.calls` in `farm-status.json` includes running call records before those calls complete.
- Completed and failed call records in `farm-status.json` include completed timestamps and durations while the job is still running.
- Recovered retry attempts remain visible in `timing.calls`.
- `FARM_STATUS.md` gives a concise active-job progress summary without dumping every completed call.
- `python sift.py farm status <run-id> --json` exposes the same progress fields for a running run.
- Existing completed run status remains compatible when `progress` is absent or terminal.
- Tracked schemas are updated so existing status artifacts without `progress` remain valid and new artifacts with `progress` validate.
- Model-free tests cover running chunk map progress, running reduce progress, failed/retried call visibility, Markdown rendering, JSON status rendering, and schema validation.
- Docs explain how a primary AI should inspect active chunk/reduce progress.
- BL-0038 is marked implemented as lifecycle advances.

## Deferred To Roadmap

- `farm status --watch` or live polling helpers.
- Stale/interrupted run detection and repair for runs left `running` after process termination.
- Whole-run timeout enforcement.
- True wall-clock whole-file timeout enforcement.
- Token-per-second or backend eval/generation metrics.
- Chunk-level parallel progress for future `concurrency.chunks`.
- UI or dashboard visualization for chunk boundaries and reduce flow.
