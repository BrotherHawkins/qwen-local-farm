# 0013 Implement Farm Status JSON

Status: Implemented
Spec: [0013 Add Farm Status JSON](../changes/0013-add-farm-status-json.md)

## Plan

Implement `farm status --json` as a narrow machine-readable inspection layer over existing run status data:

1. Add status JSON envelope helpers in `sift_farm_status`.
   - overview envelope: `schema_version`, `scope: "overview"`, `counts.runs`, `runs`
   - single-run envelope: `schema_version`, `scope: "run"`, `run_id`, `run`
2. Add `status_json(root, run_id=None)` in `sift_farm`.
   - no run ID uses existing `load_runs(root)` ordering
   - run ID uses existing `find_run_dir(root, run_id)` semantics
3. Add `--json` to `farm status`.
   - preserve current Markdown output by default
   - print compact but readable JSON to stdout when requested
4. Update README and AI usage docs.
   - show `farm status --json`
   - explain it is for scripts and primary-AI inspection
5. Move 0013 lifecycle docs to implemented in this PR.
   - spec status
   - plan status
   - dashboard counts/table
   - BL-0019 backlog row
6. Add model-free tests.
   - status envelope rendering
   - empty overview
   - overview with runs
   - single-run JSON
   - parser support for both command shapes
   - existing Markdown behavior remains covered

## Non-Goals

This implementation will not add formal JSON Schema files, `farm list --json`, structured JSON errors, streaming status, filtering, paging, or any run artifact changes.

## Verification

Implemented with:

- `farm_overview_json(...)` and `run_status_json(...)` status envelopes
- `sift_farm.status_json(root, run_id=None)`
- `farm status --json` and `farm status <run-id> --json`
- README and AI usage docs
- model-free parser, handler, status, and integration tests

Checks:

```powershell
python -m unittest tests.test_sift_farm tests.test_sift_cli tests.test_sift_farm_status
python -m unittest discover -s tests
git diff --check
```
