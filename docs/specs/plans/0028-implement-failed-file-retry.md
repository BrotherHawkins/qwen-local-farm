# 0028 Implement Failed-File Retry

Status: Implemented

Change Spec: [0028-add-failed-file-retry.md](../changes/0028-add-failed-file-retry.md)

## Goal

Add a `farm retry-failed` command that creates a new normal farm run containing only failed files from a prior run.

## Implementation Steps

- [x] Persist additive request metadata in new `farm-status.json` files.
- [x] Add a retry planning helper that loads a source run, selects failed jobs, resolves source files, and validates missing/no-failure cases before model calls.
- [x] Add a retry execution helper that reuses the normal farm run path with a selected-file discovery result.
- [x] Attach additive retry provenance to the retry run status.
- [x] Add CLI parsing and handler support for `python sift.py farm retry-failed <run-ref>`.
- [x] Add JSON output for retry command results with a tracked schema.
- [x] Update persisted status schema for optional `request` and `retry` fields.
- [x] Update docs for human and primary-AI usage.
- [x] Add model-free unit tests for planning, execution, error cases, CLI parsing/handler behavior, and schema validation.
- [x] Mark spec, plan, dashboard, and backlog implemented in the implementation PR.

## Test Plan

Run:

```powershell
python -m src.sift_spec_guard
python -m unittest tests.test_sift_farm tests.test_sift_farm_status tests.test_sift_farm_schema tests.test_sift_cli
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

## Manual Verification

After implementation, create or reuse a failed run and run:

```powershell
python sift.py farm retry-failed <failed-run-id> --output .run/dogfood_0028/retry
python sift.py farm status <retry-run-id>
python sift.py farm status <retry-run-id> --json
```

Inspect that the source run is unchanged and the retry run contains only failed files plus retry provenance.
