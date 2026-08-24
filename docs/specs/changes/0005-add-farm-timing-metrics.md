# 0005 Add Farm Timing Metrics

Status: Accepted
Type: Add

## WHY

Dogfood runs are now large enough that "it felt slower" is not good enough feedback. After 0004 added bounded file-job concurrency, we could see overlapping jobs in status, but we could not easily answer where wall-clock time went:

- waiting in the queue
- reading/writing artifacts
- chunk map calls
- reduce calls
- single-pass model calls
- retries or failures
- backend contention when multiple jobs run at once

The farm should record lightweight timing metrics as normal run artifacts so humans and primary AIs can compare dogfood runs over time and spot performance regressions after implementation changes.

This change favors:

- simple timestamps and durations over a full tracing system
- run-local artifacts over external services
- model-free tests over hardware-specific benchmarks
- comparable dogfood summaries over manual stopwatch notes
- preserving existing status/result shapes while adding timing fields

## Scope

This change adds first-pass timing observability for farm runs:

- record run-level created, started, completed, and duration fields
- record job-level queued, started, completed, queue wait, and duration fields
- record model-call-level timing for single-pass summarize/prompt calls
- record chunk map-call timing for chunked summarize jobs
- record reduce-call timing for chunked summarize jobs
- include timing fields in `farm-status.json`
- include concise timing fields in `FARM_STATUS.md`
- include timing details in per-job `result.json`
- write a run-level timing summary artifact for quick dogfood comparison
- update docs so primary AIs know where to inspect timings

## Non-Goals

This change does not add:

- automatic performance tuning
- benchmark scheduling
- historical trend dashboards outside a run folder
- hardware probing or `farm doctor`
- Ollama environment management
- token counting beyond fields already returned by the backend
- provider-specific tracing integrations
- chunk-level parallelism
- changes to summary quality criteria

## Behavior

### Time Format

All persisted timestamps use UTC ISO-8601 strings.

Durations are persisted as integer milliseconds.

Example:

```json
{
  "started_at": "2026-08-24T12:34:56.789Z",
  "completed_at": "2026-08-24T12:35:01.234Z",
  "duration_ms": 4445
}
```

### Run Timing

`farm-status.json` includes run timing metadata:

```json
{
  "timing": {
    "created_at": "...",
    "started_at": "...",
    "completed_at": "...",
    "duration_ms": 123456
  }
}
```

`created_at` is when the run folder/status is created. `started_at` is when executable farm work begins. `completed_at` is set when the run reaches a terminal status.

### Job Timing

Each job in `farm-status.json` includes:

```json
{
  "timing": {
    "queued_at": "...",
    "started_at": "...",
    "completed_at": "...",
    "queue_wait_ms": 1000,
    "duration_ms": 42000
  }
}
```

`queued_at` is set when the job summary is created. `started_at` is set when the scheduler marks the job `running`. `completed_at` is set when the job reaches a terminal job status.

For skipped files, timing may be absent or limited to discovery metadata. Skipped timing is not required in this first pass.

### Model Call Timing

Per-job `result.json` includes a `timing.calls` list describing farm-visible model calls.

For a single-pass job:

```json
{
  "timing": {
    "duration_ms": 42000,
    "calls": [
      {
        "kind": "single",
        "started_at": "...",
        "completed_at": "...",
        "duration_ms": 42000
      }
    ]
  }
}
```

For a chunked summarize job:

```json
{
  "timing": {
    "duration_ms": 120000,
    "calls": [
      {
        "kind": "chunk_map",
        "chunk_id": "chunk-0001",
        "started_at": "...",
        "completed_at": "...",
        "duration_ms": 30000
      },
      {
        "kind": "reduce",
        "started_at": "...",
        "completed_at": "...",
        "duration_ms": 45000
      }
    ]
  }
}
```

The farm records wall-clock time around its own model processor calls. If a backend later exposes token eval/generation metrics, those can be added without blocking this spec.

### Timing Summary Artifact

Each run writes:

```text
timing-summary.json
TIMING_SUMMARY.md
```

The JSON artifact is meant for scripts and primary AIs. It includes:

- run ID, mode, agent, model, profile
- run status
- total duration
- total jobs and terminal counts
- per-job duration table
- per-call duration table
- aggregate durations by call kind
- slowest jobs
- slowest calls

The Markdown artifact is a concise human-readable rendering of the same summary.

### Dogfood Comparison

This spec does not require a cross-run dashboard, but the timing summary shape should be stable enough that future dogfood reports can copy or compare the same fields across runs.

The first implementation should document a simple manual comparison path, such as saving the run-level `timing-summary.json` path in each dogfood report.

### Failure Behavior

Failed jobs still record job timing through the final failure.

If a model call fails, the failed attempt should be represented in timing data when practical, including duration and error text or error type. Full retry-level accounting can be minimal in this first pass as long as total job duration remains correct.

Timing collection must not mask the original job error.

## Acceptance Criteria

- Each new farm run records run-level `created_at`, `started_at`, `completed_at`, and `duration_ms` timing fields in `farm-status.json`.
- Each queued job records `queued_at`; running jobs record `started_at`; terminal jobs record `completed_at`, `queue_wait_ms`, and `duration_ms`.
- `FARM_STATUS.md` shows concise timing information for the run and jobs.
- Single-pass jobs include one model-call timing record in `result.json`.
- Chunked summarize jobs include timing records for each map call and the reduce call in `result.json`.
- Failed jobs preserve useful job timing and still surface the original error.
- The run writes `timing-summary.json` and `TIMING_SUMMARY.md`.
- Timing summary artifacts include slowest jobs and aggregate durations by call kind.
- Existing result/status consumers remain compatible with added fields.
- Timing metrics use UTC ISO timestamps and millisecond durations.
- Unit tests cover run timing, job timing, single-pass call timing, chunked map/reduce call timing, failure timing, and summary artifact creation without requiring Ollama.
- Docs explain where primary AIs should inspect timing metrics.
- Backlog marks `BL-0036` implemented when this spec is implemented.
- Backlog keeps `BL-0037` open unless a cross-run dogfood history mechanism is also implemented.

## Deferred To Roadmap

- Automatic performance tuning from timing metrics.
- Cross-run timing history dashboards.
- Built-in dogfood benchmark comparison commands.
- Tokenizer-aware token/sec metrics.
- Backend-specific Ollama eval/generation metric capture.
- Hardware/resource correlation through `farm doctor`.
