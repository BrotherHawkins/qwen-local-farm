# 0005 Implement Farm Timing Metrics

Status: Implemented
Change Spec: [0005 Add Farm Timing Metrics](../changes/0005-add-farm-timing-metrics.md)

## WHY

0004 made farm concurrency observable enough to see multiple jobs running, but dogfood still could not explain where runtime went. This plan adds lightweight timing records to the existing filesystem artifacts so humans and primary AIs can inspect elapsed time by run, job, chunk map call, reduce call, and single-pass model call.

The implementation should make timing a normal part of farm runs without adding external services, hardware-specific benchmarks, or automatic tuning.

## Scope

Planned:

- run-level timing in `farm-status.json`
- job-level timing in `farm-status.json`
- per-call timing in per-job `result.json`
- chunk map and reduce timing for chunked summarize jobs
- failed job timing without masking original failures
- `timing-summary.json`
- `TIMING_SUMMARY.md`
- compact timing display in `FARM_STATUS.md`
- docs for primary-AI inspection
- backlog status update for `BL-0036`
- model-free tests

Deferred:

- cross-run timing dashboard or history store
- automatic tuning from timing metrics
- scheduled benchmarks
- token/sec metrics
- Ollama-specific eval/generation metric parsing
- hardware/resource correlation through `farm doctor`

## Implementation Plan

### 1. Add Timing Helpers

Add small helpers, likely in `src/qwen_farm.py` unless the code starts to feel crowded:

- `utc_now()` or equivalent for timezone-aware UTC `datetime`
- `format_timestamp(...)` for persisted UTC ISO-8601 strings ending in `Z`
- `duration_ms(start, end)` for integer millisecond durations
- `start_timing()` / `finish_timing(...)` or similarly simple helpers for common timing records

Use wall-clock time for persisted timestamps. Avoid adding a fake clock abstraction unless tests need it; tests can assert presence, orderability, and non-negative durations instead of exact values.

### 2. Initialize Run And Job Timing

In `make_initial_status(...)`:

- keep existing top-level `created_at` and `updated_at` for compatibility
- add `timing.created_at`
- add `timing.started_at`
- leave `timing.completed_at` and `timing.duration_ms` unset or `None` until terminal status

When job summaries are created in `run_farm(...)`:

- add `job["timing"]["queued_at"]`
- leave `started_at`, `completed_at`, `queue_wait_ms`, and `duration_ms` unset or `None`

Keep existing job fields unchanged.

### 3. Record Scheduler Job Timing

In `run_scheduled_jobs(...)`:

- when a job is marked `running`, set `timing.started_at`
- compute `queue_wait_ms` from `queued_at` to `started_at`
- write status after the start update as today
- when a worker returns, set `timing.completed_at`
- compute `duration_ms` from `started_at` to `completed_at`
- apply timing before writing completion status

Keep status writes centralized in the scheduler thread.

### 4. Capture Model Call Timing

Add a small wrapper around `model_processor(...)`, such as `timed_model_call(...)`, returning:

- `FarmModelResult`
- timing call record

For successful calls, record:

- `kind`: `single`, `chunk_map`, or `reduce`
- `file_path`
- optional `chunk_id`
- optional `reduce_generation`
- optional `reduce_batch_index`
- `started_at`
- `completed_at`
- `duration_ms`
- `status`: `complete` or `complete_with_warnings`

For failed calls, record:

- the same timing fields
- `status`: `failed`
- `error`: original exception text or type/message

Then re-raise the original exception so retry/failure behavior remains unchanged.

### 5. Thread Call Timing Through Job Execution

Change the existing job execution return path to carry timing records:

- `run_single_pass_job(...)` records single-call timing
- `run_chunked_summary_job(...)` accumulates map call timings and reduce call timings
- `reduce_summary_payloads(...)` records reduce-call timings
- `run_file_job(...)` receives a shared timing record list so failed calls survive exceptions
- `execute_job(...)` includes `timing.calls` in its update data

Keep chunk artifact writing unchanged except for adding timing to chunk result envelopes where useful.

### 6. Add Timing To Result Envelopes

Extend `result_envelope(...)` with an optional `timing` argument.

Per-job `result.json` should include:

```json
{
  "timing": {
    "duration_ms": 12345,
    "calls": []
  }
}
```

For chunk result envelopes, include the individual chunk map call timing if available. This is useful but secondary to the per-job `result.json` call list.

### 7. Write Run Timing Summary Artifacts

Add summary builders, likely in a new `src/qwen_farm_timing.py` if this keeps `qwen_farm.py` cleaner:

- `build_timing_summary(status)`
- `render_timing_summary_markdown(summary)`
- `write_timing_summary(run_dir, status)`

Write both:

- `timing-summary.json`
- `TIMING_SUMMARY.md`

The summary should include:

- run ID, status, mode, agent, model, profile
- run duration
- counts
- per-job duration rows
- call records flattened across jobs
- aggregate duration by call kind
- slowest jobs
- slowest calls

Call `write_timing_summary(...)` after terminal run status is computed. Optionally write partial/in-progress summary snapshots only if it stays simple; final-only is acceptable for 0005.

### 8. Render Compact Timing In Status Markdown

Update `render_status_markdown(...)`:

- add a short `## Timing` section with run start/completion/duration when present
- add job duration and queue wait columns to the jobs table

Keep the table readable and avoid dumping every chunk call into status Markdown.

### 9. Update Docs And Backlog

Update:

- `README.md`: mention `TIMING_SUMMARY.md` and `timing-summary.json` in farm outputs.
- `docs/ai-usage.md`: tell primary AIs to inspect timing summary artifacts when dogfooding or debugging slow runs.
- `docs/roadmap.md`: note first-pass timing metrics as implemented once implementation lands.
- `docs/backlog.md`: mark `BL-0036` implemented, keep `BL-0037` open unless a cross-run history mechanism is added.
- spec/dashboard statuses when implementation is complete in the PR.

### 10. Dogfood Verification

Use a new ignored folder:

```powershell
.run/dogfood_0005/
```

Copy the same article text files from the previous dogfood set if available, then run:

```powershell
python qwen.py farm run .run/dogfood_0005/articles-text --output .run/dogfood_0005/farm-results --mode summarize --instructions "Summarize the article for later synthesis. Capture thesis, key claims, useful examples, and open questions." --agent default --parallel-jobs 2
```

Inspect:

- `farm-status.json`
- `FARM_STATUS.md`
- `timing-summary.json`
- `TIMING_SUMMARY.md`
- several per-job `result.json` files
- at least one chunked job's chunk result JSON

Do not require full dogfood success if local Ollama is unavailable; report the blocker and rely on model-free tests.

## Test Plan

Automated tests:

- successful run includes run timing fields in status
- queued/running/terminal jobs include expected timing fields
- single-pass job includes one `single` call timing in `result.json`
- chunked summarize job includes `chunk_map` timings and `reduce` timing
- failed job records job timing and preserves original error
- timing summary JSON and Markdown artifacts are written
- status Markdown includes compact timing information
- existing concurrency tests still pass

Verification before PR:

```powershell
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

## Acceptance Checklist

- [x] Change spec exists.
- [x] Human accepted the behavior target.
- [x] Human accepted the implementation plan.
- [x] Run-level timing fields are persisted in `farm-status.json`.
- [x] Job-level timing fields are persisted in `farm-status.json`.
- [x] Single-pass call timing is persisted in per-job `result.json`.
- [x] Chunk map call timing is persisted for chunked summarize jobs.
- [x] Reduce call timing is persisted for chunked summarize jobs.
- [x] Failed jobs preserve useful timing and original errors.
- [x] `timing-summary.json` is written.
- [x] `TIMING_SUMMARY.md` is written.
- [x] `FARM_STATUS.md` shows compact timing information.
- [x] Docs explain where primary AIs should inspect timing metrics.
- [x] `BL-0036` is marked implemented.
- [x] `BL-0037` remains open unless cross-run history is implemented.
- [x] Model-free unit tests cover the timing contract.
- [x] Compile check passes.
- [x] Dogfood run or documented local blocker is recorded.
