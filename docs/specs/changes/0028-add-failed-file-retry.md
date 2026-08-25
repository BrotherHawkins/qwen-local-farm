# 0028 Add Failed-File Retry

Status: Implemented
Type: Add

## WHY

Farm runs can now process multi-file and chunked article batches with retries, timing, snippets, and live progress. When one or two files fail late in a run, the user currently has to rerun the whole input folder or manually rebuild a smaller input folder.

That wastes local model time, makes dogfood comparisons noisy, and creates awkward primary-AI behavior: the AI can see exactly which jobs failed, but it cannot ask the farm to retry just those files.

This change implements:

- BL-0087: retry failed files from a previous run

The product principle is: a failed job should be easy to recover without throwing away the successful work or requiring the user to move files around.

## Scope

Add a post-run command that creates a new farm run containing only failed file jobs from a prior run:

```powershell
python qwen.py farm retry-failed <run-ref>
python qwen.py farm retry-failed <run-ref> --output .run/retries
python qwen.py farm retry-failed <run-ref> --instructions "Use the same synthesis-focused summary style."
python qwen.py farm retry-failed <run-ref> --json
```

`<run-ref>` follows the existing run-reference convention: a known run ID from `farm list` or a run directory path.

The retry run should:

- read the source run's `farm-status.json`
- select jobs with `status: "failed"`
- resolve their source files from the source run input folder and job `input_path`
- create a new normal farm run containing only those failed files
- preserve the source run's mode, agent, resolved runtime config, and instructions where available
- allow explicit CLI instructions to fill or override missing prior instructions
- write normal farm artifacts for the retry run
- add additive retry provenance to the retry run status
- leave the source run untouched
- fail clearly before model calls if there are no failed jobs or if retry source files are missing

## Retry Provenance

The retry run's `farm-status.json` should include an additive `retry` object:

```json
{
  "retry": {
    "source_run_id": "farm-run-2026-08-24-111111-abcd",
    "source_run_path": ".run/farm/farm-run-2026-08-24-111111-abcd",
    "selected_statuses": ["failed"],
    "source_failed_count": 2,
    "retried_count": 2,
    "jobs": [
      {
        "source_job_id": "job-0004",
        "retry_job_id": "job-0001",
        "input_path": "articles/long.md",
        "source_error": "timed out"
      }
    ]
  }
}
```

This provenance is for inspection and automation only. The retry run should still behave like any other farm run for `farm status`, `farm collect`, dogfood records, timing records, snippet packs, and synthesis bundles.

## Request Persistence

Accurate retry needs the prior request intent. New farm runs should persist an additive `request` object in `farm-status.json`:

```json
{
  "request": {
    "mode": "summarize",
    "instructions": "Summarize the article for later synthesis.",
    "agent": "default"
  }
}
```

For older runs that do not have `request.instructions`:

- `summarize` retries may proceed with `instructions: null` unless `--instructions` is supplied
- `prompt` retries must fail clearly unless `--instructions` is supplied
- the CLI output should tell the user when prior instructions were unavailable

## CLI Behavior

Default behavior:

- `farm retry-failed <run-ref>` uses the original run's input folder, mode, agent, resolved runtime config, and stored instructions
- the retry run is written under the normal default farm output behavior unless `--output` is provided
- stdout prints the retry run ID, source run ID, retried file count, final status, and output path

Override behavior:

- `--instructions` overrides stored prior instructions
- `--agent`, `--config`, `--profile`, `--resource-mode`, `--model`, chunk sizing, snippet, concurrency, and failure-policy flags may mirror `farm run` where practical
- omitted override flags should preserve source-run settings where durable, then fall back to current defaults

JSON behavior:

- `--json` prints a machine-readable wrapper with source run, selected failed jobs, retry run ID, retry run path, final status, counts, warnings, and errors
- JSON output must have a tracked schema if the command emits a new wrapper artifact or stable printed contract

## Non-Goals

This change does not add:

- retrying completed jobs
- retrying warning-only jobs
- retrying selected individual files by glob
- retrying failed chunks inside an otherwise failed chunked job by reusing successful chunk artifacts
- cross-run chunk resume
- partial reduce over only successful chunks
- queue-only retry runs
- background worker orchestration
- stale/interrupted run repair
- automatic resource-mode fallback after failure
- automatic retry delays or exponential backoff
- a UI or watch mode

## Acceptance Criteria

- `python qwen.py farm retry-failed <run-ref>` accepts both known run IDs and run directory paths.
- If the source run has no failed jobs, the command exits nonzero with a clear message and does not create a model-calling retry run.
- If any failed job's original input file cannot be found under the source run input folder, the command exits nonzero before model calls and lists the missing paths.
- A retry run contains only the failed source jobs, with stable relative `input_path` values matching the original failed files.
- The source run is not modified.
- The retry run writes the normal `farm-status.json`, `FARM_STATUS.md`, `farm-config.resolved.json`, `timing-summary.json`, job `result.md`, job `result.json`, and raw response artifacts.
- The retry run status includes additive `retry` provenance linking source jobs to retry jobs.
- New normal farm runs persist additive `request` metadata needed for future retry commands.
- Retry uses prior run mode, agent, resolved runtime settings, and persisted instructions by default.
- Explicit `--instructions` overrides missing or stored prior instructions.
- For older `prompt` runs without persisted instructions, retry fails clearly unless `--instructions` is supplied.
- `farm status <retry-run-id> --json` exposes the retry provenance without special parsing.
- The affected persisted JSON artifacts validate against tracked schemas.
- Docs explain when to use retry versus rerunning the whole folder.

## Tests

Add model-free tests for:

- parsing the new CLI command and key override flags
- selecting only failed jobs from a synthetic source run
- creating a retry run without modifying the source run
- preserving source relative paths and mapping source job IDs to retry job IDs
- failing when there are no failed jobs
- failing when a failed source file is missing
- preserving or overriding instructions
- rejecting older prompt retries without instructions
- validating retry status JSON against schema updates
- preserving compatibility for existing non-retry status artifacts

Run:

```powershell
python -m src.qwen_spec_guard
python -m unittest tests.test_qwen_farm tests.test_qwen_farm_status tests.test_qwen_farm_schema tests.test_qwen_cli
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

## Manual Verification

Create a small local failed run with a fake or intentionally failing processor in tests, and optionally run a real local smoke by forcing one file to fail with an unrealistically low timeout.

Then run:

```powershell
python qwen.py farm retry-failed <failed-run-id> --output .run/dogfood_0028/retry
python qwen.py farm status <retry-run-id>
python qwen.py farm status <retry-run-id> --json
```

Inspect:

- source run remains unchanged
- retry run contains only failed files
- retry provenance links source jobs to retry jobs
- final retry status is understandable to a human and a primary AI

## Deferred To Backlog

- BL-0088: cross-run chunk resume
- BL-0089: partial reduce over missing chunks
- BL-0075: runtime retry on a different resource mode after failure
- BL-0086: retry delay and backoff policy
- BL-0097: stale/interrupted run detection and repair

## Lifecycle

When this spec is accepted:

- mark this spec `Accepted`
- add an implementation plan under `docs/specs/plans/`
- update `SPEC_DASHBOARD.md`
- mark BL-0087 planned in `docs/backlog.md`

When implementation is complete in the PR:

- mark this spec `Implemented`
- mark the plan `Implemented`
- update `SPEC_DASHBOARD.md`
- mark BL-0087 implemented in `docs/backlog.md`
