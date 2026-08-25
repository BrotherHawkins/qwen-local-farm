# 0029 Add Failure Classification And Retry Guidance

Status: Implemented
Type: Add

## WHY

The farm can now retry failed files from a prior run, but a failed job is not always worth retrying as-is. Some failures are probably transient, such as a local model timeout. Others need a human or primary AI to fix the input, config, model availability, or resource profile before another attempt makes sense.

Without explicit failure guidance, `retry-failed` and AI callers have to infer too much from raw error text. That wastes local compute and makes recovery decisions less trustworthy.

This change introduces:

- BL-0098: failure classification and retry guidance

The product principle is: every durable failure should tell the caller what happened, whether the same retry is sensible, and what to do next.

## Scope

Add an additive failure object to failed farm job artifacts and run status:

```json
{
  "failure": {
    "code": "context_overflow",
    "category": "resource",
    "retryable": false,
    "retry_after_fix": true,
    "message": "The input exceeded the effective model context window.",
    "recommended_action": "Enable chunking or reduce the configured chunk size."
  }
}
```

The first pass should classify common farm failures without trying to perfectly identify every backend error:

| Code | Category | Retryable | Retry After Fix | Intended Meaning |
| --- | --- | --- | --- | --- |
| `model_timeout` | `transient` | `true` | `false` | A model call exceeded the configured timeout. |
| `model_unavailable` | `configuration` | `false` | `true` | The selected model or Ollama service was unavailable. |
| `context_overflow` | `resource` | `false` | `true` | The request appears too large for the configured model/context. |
| `input_missing` | `input` | `false` | `true` | A required source input file no longer exists. |
| `input_unreadable` | `input` | `false` | `true` | The farm could not read/decode the source input. |
| `input_empty` | `input` | `false` | `true` | The source input contains no usable text. |
| `model_output_invalid` | `model_output` | `true` | `false` | The model returned unusable or unparsable output. |
| `internal_error` | `internal` | `true` | `false` | The farm hit an unexpected exception or uncategorized failure. |

The exact classifier may be conservative. If uncertain, it should prefer `internal_error` with the original error preserved in `message` rather than guessing a precise code.

## Artifact Behavior

Job `result.json` for failed jobs should include:

- `status: "failed"`
- `error` or existing raw error text for backward compatibility
- additive `failure`

Run `farm-status.json` should include each failed job's `failure` object in the corresponding job entry.

`FARM_STATUS.md` should render a compact failure hint for failed jobs, such as:

```text
Failure: context_overflow (resource, retryable: no, retry after fix: yes)
Next: Enable chunking or reduce the configured chunk size.
```

`farm status <run-id> --json` should expose the same failure objects without special parsing.

Tracked schemas should be updated so the additive fields validate in:

- `farm-status.json`
- job `result.json`
- any existing status or retry wrapper schema that surfaces job failure summaries

No new JSON artifact is required unless implementation discovers a stable new wrapper contract.

## Retry-Failed Behavior

`farm retry-failed` should remain a failed-file retry helper, but it should surface retry guidance from the source run when available.

Minimum first-pass behavior:

- default retry selection remains failed jobs, preserving existing behavior
- human output warns when a selected failed job is marked `retryable: false`
- `--json` output includes counts for retryable and non-retryable selected jobs
- `--json` output includes the selected jobs' failure guidance when available

This spec does not require `retry-failed` to skip non-retryable jobs by default. That policy can become stricter later once failure classification has been dogfooded.

## Non-Goals

This change does not add:

- automatic resource-mode fallback
- automatic agent/model switching
- automatic retry delays, jitter, or backoff
- dynamic scheduler backoff
- cross-run chunk resume
- partial reduce over successful chunks only
- perfect parsing of all Ollama or backend errors
- strict failure taxonomy for future modes
- a new queue state machine
- a UI or watch mode

## Acceptance Criteria

- Failed single-pass jobs include a `failure` object in `jobs/job-*/result.json`.
- Failed chunked summarize jobs include a `failure` object in the failed file-level `result.json`.
- Failed job entries in `farm-status.json` include the same failure guidance.
- `FARM_STATUS.md` renders compact failure code, category, retryability, and recommended next action for failed jobs.
- `farm status <run-id> --json` exposes failure guidance for failed jobs.
- Failure objects include `code`, `category`, `retryable`, `retry_after_fix`, `message`, and `recommended_action`.
- Common timeout failures classify as `model_timeout` and `retryable: true`.
- Missing input failures classify as `input_missing` and `retryable: false`.
- Context-size failures classify as `context_overflow` and `retryable: false`.
- Unrecognized exceptions classify conservatively as `internal_error`.
- Existing `error` fields or raw error text remain available for backward compatibility.
- `farm retry-failed <run-ref>` human output warns when selected failed jobs include known non-retryable failures.
- `farm retry-failed <run-ref> --json` includes retryable and non-retryable selected job counts.
- Existing successful result artifacts remain schema-compatible.
- Existing failed result artifacts without `failure` remain readable where backward compatibility is practical.
- Tracked schemas validate the new additive failure fields.
- Docs explain how humans and AI callers should interpret `retryable` and `retry_after_fix`.
- BL-0098 is marked planned/implemented as lifecycle advances.

## Tests

Add model-free tests for:

- failure-object construction for known error categories
- single-pass failed job result JSON failure metadata
- chunked summarize failed job result JSON failure metadata
- status JSON rendering of failed job failure metadata
- Markdown status rendering of retry guidance
- `farm status --json` compatibility
- `farm retry-failed --json` retryable/non-retryable selected counts
- schema validation for status and result artifacts with failure objects
- backward compatibility for older failed artifacts that lack `failure`

Run:

```powershell
python -m src.sift_spec_guard
python -m unittest tests.test_sift_farm tests.test_sift_farm_status tests.test_sift_farm_schema tests.test_sift_cli
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

## Manual Verification

Use ignored artifacts only:

```text
.run/dogfood_0029/
```

Suggested smoke:

1. Create a small synthetic or model-free failed run with one retryable failure and one non-retryable failure.
2. Inspect `farm-status.json`, `FARM_STATUS.md`, and failed job `result.json` artifacts.
3. Run:

```powershell
python sift.py farm status <run-id> --json
python sift.py farm retry-failed <run-id> --json
```

Verify that a primary AI can tell:

- which jobs failed
- why they failed
- whether repeating the same retry is likely useful
- what fix should happen first when retry is not useful

## Deferred To Backlog

- BL-0075: runtime retry on a different resource mode after failure
- BL-0086: retry delay and backoff policy
- BL-0097: stale/interrupted run detection and repair
- BL-0099: default `retry-failed` policy that skips non-retryable jobs unless explicitly overridden

## Lifecycle

When this spec is accepted:

- mark this spec `Accepted`
- add an implementation plan under `docs/specs/plans/`
- update `SPEC_DASHBOARD.md`
- mark BL-0098 planned in `docs/backlog.md`
- add BL-0099 as an open deferred follow-up if still out of scope

When implementation is complete in the PR:

- mark this spec `Implemented`
- mark the plan `Implemented`
- update `SPEC_DASHBOARD.md`
- mark BL-0098 implemented in `docs/backlog.md`
