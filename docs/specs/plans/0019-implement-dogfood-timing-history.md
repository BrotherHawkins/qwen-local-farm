# 0019 Implement Dogfood Timing History

Status: Implemented
Spec: [0019 Add Dogfood Timing History](../changes/0019-add-dogfood-timing-history.md)

## Plan

Implement a timing-focused dogfood history workflow that records compact, comparable performance data from existing farm runs and compares baseline/candidate timing records without model calls.

1. Add a timing history module.
   - create a focused helper module, likely `src/qwen_farm_dogfood_timing.py`
   - read an existing run's `farm-status.json`
   - use `timing-summary.json` when present for slowest jobs, slowest calls, and aggregate call-kind data
   - gracefully fall back to `farm-status.json` job timing when `timing-summary.json` is missing
   - capture compact run identity, commit, status, mode, agent, model, profile, runtime settings, totals, job rows, slowest jobs, and slowest calls
   - avoid copying article text, raw model responses, full summaries, or full snippets
2. Add comparison helpers.
   - compare two timing records
   - compute total duration, queue wait, chunk, call count, call duration, and call-kind deltas
   - compare per-job timing rows by input path or job ID
   - include candidate slowest jobs/calls
   - emit comparability notes when model, profile, commit, concurrency, chunk strategy, chunk size, reduce size, or snippet policy differ
   - render both JSON and Markdown comparison artifacts
3. Wire CLI commands.
   - add `python sift.py farm dogfood timing record <run-ref>`
   - add `python sift.py farm dogfood timing compare <baseline-timing.json> <candidate-timing.json>`
   - support `--label` and `--output`
   - default record output to `.run/dogfood_timing/runs/`
   - default comparison output to `.run/dogfood_timing/comparisons/`
   - reuse existing run-reference lookup behavior for `<run-ref>`
4. Add model-free tests.
   - fixture-based timing record extraction with `timing-summary.json`
   - fallback extraction without `timing-summary.json`
   - missing optional timing compatibility
   - total/job/call-kind delta calculations
   - comparability note generation for changed settings
   - Markdown rendering
   - privacy guard that source text, raw responses, full summaries, and snippet text are not copied
   - CLI parser and handler coverage if parser paths are touched
   - regression coverage that existing dogfood quality commands still parse and dispatch
5. Update docs.
   - add a focused timing history doc or extend existing dogfood docs with a timing section
   - update README and AI usage docs with record/compare examples
   - explain how a primary AI should interpret timing deltas and comparability notes
   - keep generated timing history local under `.run/`
6. Run dogfood timing smoke.
   - use a small local dogfood set, likely `dogfood_lite`, under `.run/dogfood_0019/`
   - record at least two comparable timing records under `.run/dogfood_timing/`
   - compare them
   - write `.run/dogfood_0019/DOGFOOD_TIMING_0019_REPORT.md`
7. Update lifecycle records in the implementation PR.
   - mark BL-0037 implemented when code/docs/tests land
   - mark spec and this plan implemented
   - update spec dashboard counts/status
   - keep deferred timing dashboard, thresholds, normalization, doctor recommendation, and tuning work open

## CLI Shape

Preferred command shape:

```powershell
python sift.py farm dogfood timing record <run-ref> --label 0019-lite-baseline
python sift.py farm dogfood timing compare .run/dogfood_timing/runs/0019-lite-baseline.json .run/dogfood_timing/runs/0019-lite-candidate.json
```

Expected defaults:

```text
.run/dogfood_timing/runs/
.run/dogfood_timing/comparisons/
```

If parser nesting becomes awkward, keep the user-facing command obvious and document the exact shape before implementation proceeds too far.

## Record Shape

The first implementation should keep records compact and script-friendly:

- `schema_version`
- `recorded_at`
- `label`
- `commit`
- `run_id`
- `run_path`
- `status`
- `mode`
- `agent`
- `model`
- `profile`
- compact `runtime`
- `totals`
- `slowest_jobs`
- `slowest_calls`
- `jobs`

Totals should include:

- `duration_ms`
- `jobs`
- `chunks`
- `calls`
- `queue_wait_ms`
- `call_duration_ms`
- `by_call_kind`

Job rows should include:

- `job_id`
- `input_path`
- `status`
- `duration_ms`
- `queue_wait_ms`
- `chunk_count`
- `call_count`
- `call_duration_ms`
- `by_call_kind`
- `warning_count`

## Comparison Shape

Comparison JSON should include:

- `schema_version`
- `compared_at`
- `baseline`
- `candidate`
- `comparability`
- `totals`
- `by_call_kind`
- `jobs`
- `candidate_slowest_jobs`
- `candidate_slowest_calls`

Markdown should be short enough to scan:

- run identity and comparability notes
- total timing deltas
- call-kind timing deltas
- slowest candidate jobs/calls
- per-job deltas

## Privacy Guard

Timing history must not persist:

- article/source body text
- raw model responses
- full summary Markdown
- full source snippets
- snippet pack contents

Input paths and filenames are acceptable because existing status and dogfood records already expose them.

## Non-Goals

This implementation will not add automatic tuning, benchmark scheduling, tracked aggregate timing history, dashboards, charts, CI performance gates, cross-machine normalization, `farm doctor` recommendation changes, token-per-second backend metrics, model calls, Ollama calls, tokenizer downloads, network access, or scheduler/chunking behavior changes.

## Verification

Completed checks:

```powershell
python -m unittest tests.test_qwen_farm_dogfood_timing tests.test_qwen_farm_dogfood tests.test_qwen_cli
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Completed manual smoke:

```powershell
python sift.py farm dogfood timing record .run/dogfood_0008/lite-ranked-final/farm-results/farm-run-2026-08-24-123139-37f1 --label 0019-lite-baseline --output .run/dogfood_timing/runs
python sift.py farm dogfood timing record .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --label 0019-lite-candidate --output .run/dogfood_timing/runs
python sift.py farm dogfood timing compare .run/dogfood_timing/runs/0019-lite-baseline.json .run/dogfood_timing/runs/0019-lite-candidate.json --output .run/dogfood_timing/comparisons
```

Dogfood report:

```text
.run/dogfood_0019/DOGFOOD_TIMING_0019_REPORT.md
```

## Implementation Checklist

- [x] Add timing history module.
- [x] Add timing record builder and writer.
- [x] Add timing comparison builder and writer.
- [x] Add Markdown rendering for comparisons.
- [x] Wire `farm dogfood timing record`.
- [x] Wire `farm dogfood timing compare`.
- [x] Add parser/handler tests.
- [x] Add record extraction tests with timing summary present.
- [x] Add fallback/missing-field compatibility tests.
- [x] Add comparison delta tests.
- [x] Add comparability note tests.
- [x] Add privacy guard tests.
- [x] Update README, AI usage docs, and dogfood docs.
- [x] Run model-free verification.
- [x] Run local dogfood timing smoke and write the local report.
- [x] Update lifecycle records in the implementation PR.
