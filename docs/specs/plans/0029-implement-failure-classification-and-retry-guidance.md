# 0029 Implement Failure Classification And Retry Guidance

Status: Implemented

Change Spec: [0029-add-failure-classification-and-retry-guidance.md](../changes/0029-add-failure-classification-and-retry-guidance.md)

## Goal

Add durable failure classification and retry guidance to failed farm job artifacts so humans and primary AI callers can decide whether retrying as-is is useful.

## Implementation Steps

- [x] Add a small failure-classification helper with stable code/category/retryability/recommended-action fields.
- [x] Attach failure metadata to failed job `result.json` artifacts for single-pass and chunked summarize failures.
- [x] Propagate failure metadata into failed job entries in `farm-status.json`.
- [x] Render compact failure guidance in `FARM_STATUS.md`.
- [x] Surface retryable/non-retryable selected counts and selected job failure details in `farm retry-failed --json`.
- [x] Warn in human `farm retry-failed` output when selected jobs include non-retryable failures.
- [x] Update schemas for job results, run status, status JSON wrappers, and retry-failed JSON output.
- [x] Update docs for humans and AI callers.
- [x] Add model-free unit tests for classification, artifact propagation, status rendering, retry JSON, and schema validation.
- [x] Mark spec, plan, dashboard, and backlog implemented in the implementation PR.

## Test Plan

Run:

```powershell
python -m src.qwen_spec_guard
python -m unittest tests.test_qwen_farm tests.test_qwen_farm_status tests.test_qwen_farm_schema tests.test_qwen_cli
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

## Manual Verification

Use ignored artifacts only:

```powershell
python sift.py farm status <failed-run-id> --json
python sift.py farm retry-failed <failed-run-id> --json
```

Inspect failed job `result.json`, `farm-status.json`, `FARM_STATUS.md`, and retry JSON output to verify a primary AI can see which failures are retryable and which need a fix first.
