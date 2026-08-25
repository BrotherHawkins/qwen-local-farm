# 0004 Implement Farm Scheduler Concurrency

Status: Implemented
Change Spec: [0004 Add Farm Scheduler Concurrency](../changes/0004-add-farm-scheduler-concurrency.md)

## WHY

Runtime profiles now carry concurrency settings, but the farm still processes file jobs one at a time. This plan makes `concurrency.jobs` operational so larger local systems can use bounded parallel farm work while smaller/default systems remain conservative.

The implementation should preserve the current filesystem contract and status semantics while replacing the sequential file loop with a simple, testable scheduler.

## Scope

Planned:

- file-job concurrency bounded by resolved `runtime_config["concurrency"]["jobs"]`
- sequential behavior when the bound is `1`
- deterministic job IDs and job folders from discovery order
- status updates when jobs start and finish
- failure continuation across unrelated jobs
- existing retry behavior inside each job
- compatible result artifacts and final status semantics
- docs explaining farm worker slots versus Ollama parallel requests
- model-free scheduler tests

## Non-Goals

Deferred:

- chunk-level parallelism
- queue-only/background worker mode
- cross-run scheduling
- automatic Ollama env var management
- multiple Ollama server pools
- dynamic backoff after memory pressure
- hardware probing or `farm doctor`

## Implementation Plan

### 1. Extract Per-Job Execution

Refactor the body of the current per-file processing loop into a helper that can run one job from start to finish.

The helper should:

- read the input file
- run retries using existing `max_attempts`
- call `run_file_job`
- write result artifacts on success
- write failure log on final failure
- return the mutated job summary or enough data for the scheduler to update it

Keep per-job artifact paths unchanged.

### 2. Add Scheduler Helper

Add a bounded scheduler helper, likely inside `src/sift_farm.py` for this first version.

The helper should:

- accept job/item pairs in discovery order
- accept `max_workers`
- start at most `max_workers` jobs concurrently
- preserve deterministic job IDs and folders
- update shared job summaries as each job starts and finishes
- call `write_status` after starts and completions
- continue scheduling queued jobs after failures

Use Python stdlib concurrency only. A `ThreadPoolExecutor` is acceptable because farm jobs spend most of their time waiting on local HTTP/model calls and filesystem writes.

### 3. Keep Status Writes Simple

Status writes are shared mutable state. Keep updates centralized in the scheduler thread:

- mark a job `running` before submitting it
- write status after each job is marked `running`
- worker returns final job fields
- scheduler applies final fields
- write status after each completion

This avoids concurrent writes to `farm-status.json` and `FARM_STATUS.md`.

### 4. Preserve Sequential Compatibility

When `concurrency.jobs` resolves to `1`, behavior should stay effectively sequential.

The implementation may still use the same scheduler path with `max_workers=1`, as long as status/artifacts remain compatible.

### 5. Preserve Failure Behavior

Keep the existing per-file retry policy:

- retry each failed file up to `max_attempts`
- after final failure, mark only that job failed
- continue remaining queued jobs
- final run status remains `partial` if some jobs succeeded and some failed

### 6. Do Not Parallelize Chunks Yet

Chunked summarize jobs remain internally sequential in this spec.

If two different files are chunked, those file jobs may run concurrently when `concurrency.jobs > 1`, but chunks within a single file are still processed one at a time.

### 7. Update Docs

Update README and AI usage docs with:

- `parallel_jobs` / `--parallel-jobs` as farm worker slots
- reminder that Ollama must be configured separately for true parallel inference
- `OLLAMA_NUM_PARALLEL` mentioned as external setup, not farm-managed behavior
- recommendation to try `--parallel-jobs 2` on a small folder before raising it

Update roadmap/backlog if implementation changes any deferred item status.

### 8. Test Plan

Automated tests:

- default/no-config run remains sequential from the caller's perspective
- `parallel_jobs=2` runs at most two jobs concurrently
- scheduler can show multiple jobs as `running` in intermediate status snapshots
- job IDs/folders remain deterministic by discovery order
- completion order may differ from discovery order without breaking final status
- one failed job does not prevent unrelated queued jobs from running
- final run status is `complete`, `complete_with_warnings`, `partial`, or `failed` as before
- status JSON and Markdown remain readable with running/completed jobs

Testing approach:

- use model-free fake processors
- use thread coordination primitives in tests to block workers until status can be inspected
- avoid sleeps where possible; use events/barriers

Manual verification:

```bash
python -m unittest discover -s tests
python -m compileall sift.py src tests
python sift.py farm run <small-folder> --output .run/manual-concurrency --mode summarize --parallel-jobs 2
python sift.py farm status <run-id>
```

## Verification Plan

Before PR:

```bash
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Optional live smoke test:

```bash
python sift.py farm run .run/dogfood3/articles-text --output .run/manual-concurrency-dogfood --mode summarize --agent default --parallel-jobs 2
```

The live smoke test should be optional because CI must remain model-free and because local Ollama parallel request behavior depends on user environment settings.

## Acceptance Checklist

- [x] Change spec exists.
- [x] Human accepted the behavior target.
- [x] Human accepted the implementation plan.
- [x] `concurrency.jobs: 1` preserves sequential behavior.
- [x] `concurrency.jobs > 1` runs multiple file jobs concurrently.
- [x] Scheduler never exceeds resolved `concurrency.jobs`.
- [x] Job IDs and folders remain deterministic by discovery order.
- [x] Completed jobs write normal result artifacts.
- [x] Failed jobs write normal failure logs.
- [x] Failed jobs do not prevent unrelated queued jobs from running.
- [x] Status JSON can show multiple running jobs during a concurrent run.
- [x] Markdown status remains readable during concurrent runs.
- [x] Final run status semantics are unchanged.
- [x] Runtime profile metadata remains present.
- [x] Docs explain farm worker slots versus Ollama parallel requests.
- [x] Backlog remains updated for deferred items.
- [x] Unit tests pass.
- [x] Compile check passes.
