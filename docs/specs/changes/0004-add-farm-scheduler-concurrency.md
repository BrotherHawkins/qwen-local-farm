# 0004 Add Farm Scheduler Concurrency

Status: Implemented
Type: Add

## WHY

Runtime profiles now record capacity assumptions such as `parallel_jobs` and `parallel_chunks`, but the farm still processes jobs sequentially. That leaves larger local systems underused and makes the profile concurrency fields descriptive rather than operational.

The next step is to let the farm run multiple file jobs concurrently when the resolved profile permits it, while keeping the default safe for small systems.

This change favors:

- bounded scheduler concurrency over ad hoc parallel loops
- same-model parallel requests through the existing Ollama server over multiple model/server instances
- clear status for running jobs over hidden worker activity
- conservative defaults over automatic hardware guessing
- model-free tests for scheduler behavior

## Scope

This change adds the first farm scheduler concurrency behavior:

- use resolved `concurrency.jobs` to limit concurrently running file jobs
- keep default `local-8gb` behavior at one file job at a time
- allow higher-capacity profiles or CLI/config overrides to run multiple file jobs concurrently
- update status while multiple jobs are running
- keep per-job artifacts and final run status compatible with sequential runs
- document Ollama parallel-request assumptions for users and primary AIs

## Non-Goals

This change does not add:

- multiple Ollama server processes
- multiple full copies of the same model in VRAM
- automatic `OLLAMA_NUM_PARALLEL` configuration
- automatic `OLLAMA_MAX_LOADED_MODELS` configuration
- hardware probing or `farm doctor`
- dynamic concurrency increases based on live performance
- dynamic degradation after memory pressure
- cross-run scheduling
- queue-only/background worker mode
- chunk-level parallelism using `concurrency.chunks`

## Behavior

### Scheduler Limit

The farm uses the resolved runtime config field:

```json
{
  "concurrency": {
    "jobs": 2,
    "chunks": 1
  }
}
```

For `farm run`, `concurrency.jobs` controls how many file jobs may be in `running` state at the same time.

If `concurrency.jobs` is `1`, behavior remains effectively sequential.

If `concurrency.jobs` is greater than `1`, the farm schedules up to that many file jobs concurrently and starts additional queued jobs as running jobs finish.

### Ollama Assumption

This scheduler is designed around one Ollama server receiving multiple parallel requests for the same or selected model, not around launching multiple local model-server instances.

Users who want actual parallel inference must still configure Ollama appropriately outside this spec, such as through `OLLAMA_NUM_PARALLEL`, when their machine has enough memory.

The farm must not silently start extra Ollama servers or duplicate model processes.

### Status Updates

While a concurrent run is active:

- multiple jobs may appear as `running`
- counts reflect queued, running, complete, warning, and failed jobs
- `farm-status.json` and `FARM_STATUS.md` continue to update as jobs start and finish
- completed job artifacts are written as soon as each job completes

Final run status semantics remain unchanged:

- `complete` if all jobs complete cleanly
- `complete_with_warnings` if any job completed with warnings
- `partial` if some jobs failed and some completed
- `failed` if all jobs failed

### Artifact Compatibility

Concurrent scheduling does not change the run folder layout:

```text
farm-status.json
farm-config.resolved.json
FARM_STATUS.md
jobs/job-0001/
jobs/job-0002/
```

Job numbering stays deterministic by input discovery order, regardless of completion order.

### Failure Behavior

Each file job keeps the existing retry behavior.

A failing job must not stop unrelated running or queued jobs unless the run itself encounters an unrecoverable scheduler error.

If a job fails after retries, the scheduler records that job failure and continues scheduling remaining queued jobs.

### Concurrency Validation

The existing profile/config validation still requires positive integer concurrency values.

This change does not define a hard upper bound beyond positive integers, but docs should warn that values above local Ollama/memory capacity may queue inside Ollama, slow down, or fail.

### User And AI Guidance

Docs explain the difference between:

- farm worker slots: how many file jobs the farm starts
- Ollama parallel requests: how many requests a loaded model can process at once
- loaded model count: how many different models Ollama may keep resident
- true multi-instance servers: advanced manual setup, out of scope

The guidance should recommend testing `parallel_jobs: 2` with a small input folder before raising it further.

## Acceptance Criteria

- `concurrency.jobs: 1` preserves existing sequential behavior.
- `concurrency.jobs > 1` allows multiple file jobs to be running at once.
- The scheduler never runs more file jobs concurrently than resolved `concurrency.jobs`.
- Job IDs and job folders remain deterministic by input discovery order.
- Completed jobs write normal `result.md`, `result.json`, and `raw-response.txt` artifacts.
- Failed jobs write normal failure logs and do not prevent unrelated queued jobs from running.
- `farm-status.json` can show multiple jobs as `running` during a concurrent run.
- `FARM_STATUS.md` renders running and completed jobs clearly during a concurrent run.
- Final run status uses the existing complete/warning/partial/failed semantics.
- Default no-config farm runs remain effectively sequential.
- Runtime profile metadata remains present in run status and resolved config artifacts.
- Unit tests cover scheduler limits, completion ordering, failure continuation, status counts, and sequential compatibility without requiring Ollama.
- Docs explain farm worker slots versus Ollama parallel requests and defer multiple server/model instances.

## Deferred To Roadmap

- `farm doctor` recommendation for safe `parallel_jobs` and `OLLAMA_NUM_PARALLEL`.
- CLI helpers for starting Ollama with recommended concurrency environment variables.
- Dynamic scheduler backoff after memory or timeout failures.
- Cross-run scheduling and background workers.
- Chunk-level parallelism using `concurrency.chunks`.
- Multiple Ollama server pools.
- Per-agent or per-model routing across loaded models.
