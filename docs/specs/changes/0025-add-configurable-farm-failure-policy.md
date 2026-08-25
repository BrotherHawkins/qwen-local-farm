# 0025 Add Configurable Farm Failure Policy

Status: Implemented
Type: Add

## WHY

The farm has grown from a simple per-file runner into a chunked, concurrent, artifact-rich worker. Its failure behavior is still mostly hardcoded:

- file jobs retry with the MVP default
- chunk failures make the whole file attempt fail
- a retried chunked file reruns chunks that may already have succeeded
- timeout and retry choices are not visible as first-class resolved runtime settings

That was good enough for the first MVP, but it becomes awkward as runs get larger. A single transient local model failure should not throw away successful chunk work, and power users or AI assistants should be able to choose conservative or aggressive retry behavior without editing Python.

This change combines:

- BL-0009: caller-provided retry/timeout behavior
- BL-0017: chunk retries separate from file retries

The goal is not adaptive recovery yet. The goal is a small, explicit, model-free failure policy surface that makes retries predictable, inspectable, and cheaper for chunked summarize jobs.

## Scope

This change adds a first-pass farm failure policy:

- config fields under `.sift-farm.json`
- CLI overrides for the same fields
- resolved runtime metadata for the effective policy
- status/result/timing metadata that shows attempt behavior
- independent retries for summarize chunk map calls
- independent retries for summarize reduce calls
- preservation of successful chunk artifacts during chunk-local retry
- model-free tests for failure-policy resolution and retry behavior
- docs updates for users and AI callers
- backlog lifecycle updates for BL-0009 and BL-0017

The first policy fields are:

```json
{
  "failure_policy": {
    "max_attempts": 2,
    "per_file_timeout_seconds": 600,
    "chunk_max_attempts": 2,
    "reduce_max_attempts": 2
  }
}
```

CLI overrides:

```powershell
python sift.py farm run notes --max-attempts 1
python sift.py farm run notes --per-file-timeout-seconds 900
python sift.py farm run notes --chunk-max-attempts 3 --reduce-max-attempts 1
```

## Non-Goals

This change does not add:

- dynamic scheduler backoff after failures
- automatic concurrency reduction
- automatic resource-mode retry, such as retrying GPU work on CPU
- automatic model-size upgrade or downgrade
- cross-run resume
- queue-only retry processing
- retrying only failed files from a previous run
- strict retry taxonomies for every possible Ollama/backend error
- exponential backoff, jitter, or retry delays
- whole-run timeout enforcement
- true wall-clock whole-file timeout enforcement separate from model-call timeout
- chunk-level parallelism
- partial file-level reduce over missing chunks

## Behavior

### Failure Policy Resolution

Profiles should keep the current defaults unless they explicitly override failure policy later.

The resolved runtime config should include:

```json
{
  "failure_policy": {
    "max_attempts": 2,
    "per_file_timeout_seconds": 600,
    "chunk_max_attempts": 2,
    "reduce_max_attempts": 2
  }
}
```

Resolution precedence should match existing runtime config behavior:

1. profile defaults
2. `.sift-farm.json`
3. CLI overrides

Validation:

- all four fields must be positive integers
- unknown `failure_policy` fields fail before creating a run folder
- CLI override values must be positive integers

### Timeout Semantics

`per_file_timeout_seconds` preserves the existing public concept and default, but the implementation may continue to apply it as the timeout for each local model call in the first pass.

The docs should make that first-pass behavior clear:

- single-pass jobs get one model call timeout per attempt
- chunk map calls get the same timeout per chunk attempt
- reduce calls get the same timeout per reduce attempt

True wall-clock whole-file timeout and whole-run timeout remain deferred.

### File Attempts

`max_attempts` controls the outer file-job retry loop.

Defaults remain:

```text
max_attempts: 2
per_file_timeout_seconds: 600
```

Existing behavior should remain unchanged for:

- short single-pass summarize jobs
- prompt-mode jobs
- non-chunked failures
- run status calculation

When a file attempt fails after exhausting configured attempts, the job is marked failed and the run continues with other jobs.

### Chunk Attempts

`chunk_max_attempts` controls retries for each chunk map call inside a chunked summarize job.

Expected behavior:

- each chunk gets up to `chunk_max_attempts` attempts before the file attempt fails
- a chunk retry should rerun only that chunk, not earlier successful chunks
- successful chunk artifacts should be written once the chunk succeeds
- failed chunk attempts should be represented in timing call records
- if a chunk fails all chunk attempts, the current file attempt fails
- outer file retry behavior remains available through `max_attempts`

The first implementation does not need to resume from a previous failed run. It only needs to avoid rerunning already successful chunks within the current file attempt.

### Reduce Attempts

`reduce_max_attempts` controls retries for each reduce model call inside a chunked summarize job.

Expected behavior:

- each final reduce call gets up to `reduce_max_attempts` attempts
- each intermediate batched reduce call also gets up to `reduce_max_attempts` attempts
- failed reduce attempts should be represented in timing call records
- if a reduce call fails all reduce attempts, the current file attempt fails
- chunk artifacts already written during the attempt remain inspectable

### Attempt Metadata

The farm should make retry behavior visible enough for humans and primary AIs to inspect.

Resolved config:

- `farm-config.resolved.json` includes `failure_policy`

Run status:

- `farm-status.json` includes resolved `failure_policy` under `runtime`
- failed job timing includes failed calls as it does today
- successful jobs with transient retry failures keep failed and successful model-call records in `timing.calls`

Job results:

- `jobs/job-*/result.json` includes enough timing/call metadata to see failed retry attempts before success
- chunk result JSON includes the successful attempt call timing
- final file result JSON includes all model-call timings for the job attempt

The first pass can rely on `timing.calls` as the primary attempt ledger. It does not need a separate `attempts` array unless implementation proves that clearer.

### Failure Status

The first implementation should preserve current status semantics:

- any permanently failed file job makes the run `partial` unless all jobs fail
- warning-only successful jobs make the run `complete_with_warnings`
- transient failed chunk or reduce attempts that eventually succeed do not by themselves make the job failed

If a transient retry failure should surface to users, it may appear as a warning such as `retry_attempt_failed`, but the spec does not require warning status for recovered retries.

## Acceptance Criteria

- `.sift-farm.json` accepts `failure_policy.max_attempts`.
- `.sift-farm.json` accepts `failure_policy.per_file_timeout_seconds`.
- `.sift-farm.json` accepts `failure_policy.chunk_max_attempts`.
- `.sift-farm.json` accepts `failure_policy.reduce_max_attempts`.
- Unknown `failure_policy` fields fail validation before run folder creation.
- Non-positive failure-policy values fail validation before run folder creation.
- `farm run` accepts `--max-attempts`.
- `farm run` accepts `--per-file-timeout-seconds`.
- `farm run` accepts `--chunk-max-attempts`.
- `farm run` accepts `--reduce-max-attempts`.
- CLI failure-policy overrides take precedence over `.sift-farm.json`.
- `farm-config.resolved.json` includes the effective `failure_policy`.
- `farm-status.json` and `FARM_STATUS.md` expose the effective failure policy.
- Existing default behavior remains 2 file attempts and 600 seconds without config or CLI overrides.
- Single-pass job retry behavior obeys `max_attempts`.
- Prompt-mode retry behavior obeys `max_attempts`.
- Chunked summarize jobs retry a failed chunk up to `chunk_max_attempts` before failing the file attempt.
- A recovered chunk retry does not rerun earlier successful chunks in the same file attempt.
- Reduce calls retry up to `reduce_max_attempts` before failing the file attempt.
- Timing call records include failed retry attempts and successful final attempts where practical.
- A chunked job with recovered chunk/reduce retries can still finish `complete` or `complete_with_warnings`.
- A chunked job with exhausted chunk/reduce retries fails according to existing run status rules.
- Existing `farm run`, `farm list`, `farm status`, post-run package, schema, doctor, recommend, and collect behavior remains compatible.
- Docs explain failure policy defaults, config, CLI overrides, and first-pass timeout semantics.
- BL-0009 and BL-0017 are marked planned/implemented as lifecycle advances.
- Deferred dynamic recovery items remain captured in backlog.

## Test Plan

Automated:

- runtime config tests for default failure policy
- config file tests for `failure_policy`
- CLI override tests for all failure-policy flags
- validation tests for unknown and non-positive failure-policy values
- resolved-config artifact tests for failure policy
- status Markdown/JSON rendering tests for failure policy
- single-pass retry tests with `max_attempts: 1` and `max_attempts: 2`
- prompt-mode retry tests with configured attempts
- chunk retry tests proving only the failing chunk is retried within a file attempt
- chunk retry exhaustion tests
- reduce retry success tests
- reduce retry exhaustion tests
- timing tests proving failed retry attempts are visible in `timing.calls`
- full model-free unit suite

Verification:

```powershell
python -m src.sift_spec_guard
python -m unittest discover -s tests -p "test_*.py"
python -m compileall sift.py examples src tests
git diff --check
```

Runtime smoke:

Use ignored artifacts only:

```text
.run/dogfood_0025/
```

Suggested smoke:

```powershell
python sift.py farm run .run/dogfood_0025/input --output .run/dogfood_0025/farm-results --mode summarize --max-attempts 1 --chunk-max-attempts 1 --reduce-max-attempts 1
python sift.py farm status <run-id> --json
```

If practical, include a local model smoke with a normal successful run to verify the new flags do not disturb ordinary execution.

## Deferred To Roadmap

- Whole-run timeout enforcement.
- True wall-clock whole-file timeout separate from model-call timeout.
- Retry delay, jitter, or exponential backoff.
- Dynamic scheduler backoff after memory, timeout, or backend failures.
- Runtime retry on a different resource mode after failure.
- Retry only failed files from a previous run.
- Cross-run resume of failed chunks.
- Partial reduce over missing chunks.
