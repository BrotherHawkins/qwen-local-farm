# 0027 Implement In-Progress Chunk And Reduce Status

Status: Implemented

Change Spec: [0027-add-in-progress-chunk-and-reduce-status.md](../changes/0027-add-in-progress-chunk-and-reduce-status.md)

## Goal

Make active chunked summarize jobs inspectable from the normal farm status artifacts while the job is still running.

## Implementation Steps

- [x] Add a small progress writer path from worker execution back to shared run status.
- [x] Record running model-call entries in `timing.calls` when calls start, then update them on completion or failure.
- [x] Surface chunk planning, chunk map, and reduce phases in `job.progress`.
- [x] Update `chunking` metadata as soon as chunk planning completes.
- [x] Render concise active progress in `FARM_STATUS.md`.
- [x] Preserve final result/status compatibility with additive fields only.
- [x] Update affected JSON schemas for optional progress fields and running call status.
- [x] Update docs for humans and primary AIs.
- [x] Add model-free tests for active chunk progress, active reduce progress, retry visibility, Markdown rendering, JSON status output, and schema validation.
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

After the PR is opened, run dogfood lite in a fresh output folder and inspect:

- `farm-status.json` while the run is active
- `FARM_STATUS.md` while the run is active
- final `farm-status.json`
- final job result artifacts

The runtime lite run should happen after the PR is available for review.

## Lifecycle

When implementation is complete in this PR:

- mark the change spec `Implemented`
- mark this plan `Implemented`
- update `SPEC_DASHBOARD.md`
- mark BL-0038 implemented in `docs/backlog.md`
