# 0019 Add Dogfood Timing History

Status: Implemented
Type: Add

## WHY

The farm now records useful timing data inside each run, and dogfood quality records can compare summary/snippet quality across runs. That still leaves a practical gap: when a dogfood run feels slower, the timing evidence is scattered across individual run folders and comparisons are partly manual.

We need a lightweight local timing history workflow that makes dogfood runs comparable over time, so regressions in run duration, per-job duration, chunk counts, call counts, queue wait, and reduce/map behavior are easier to notice before they become folklore.

This change favors:

- comparable timing records over stopwatch notes
- local `.run/` artifacts over tracked benchmark data
- deterministic summaries from existing run artifacts over new model calls
- model-free tests and CI assumptions
- machine-readable JSON plus readable Markdown
- a small timing-specific workflow that can later feed doctor/profile recommendations

## Scope

This change adds a dogfood timing history workflow for existing farm runs:

- record compact timing history from an existing run's `farm-status.json` and `timing-summary.json`
- store generated local records under `.run/dogfood_timing/`
- compare a baseline timing record to a candidate timing record
- highlight run, job, queue, chunk, model-call, map, and reduce timing deltas
- preserve enough config/runtime identifiers to explain whether two runs are comparable
- produce JSON and Markdown comparison artifacts for primary AIs and humans
- update docs so future dogfood runs have a repeatable timing capture path
- update BL-0037 from open to planned/implemented as lifecycle progresses

This should integrate with the existing dogfood family of commands if practical, but it should stay timing-focused and should not require quality scores.

## Non-Goals

This change does not add:

- automatic performance tuning
- benchmark scheduling
- tracked aggregate benchmark history
- web dashboards or charts
- statistical pass/fail gates
- hardware normalization across machines
- frontier-model or local-model grading
- model calls, Ollama calls, tokenizer downloads, or network access
- new timing fields inside active farm runs unless a small bug is discovered
- automatic profile recommendation changes in `farm doctor`
- chunk-level parallelism or scheduling changes

## Behavior

### Timing Record

The workflow should summarize an existing farm run into a compact timing record.

Suggested command shape:

```powershell
python qwen.py farm dogfood timing record <run-ref> --label 0019-lite-baseline
```

Suggested default output:

```text
.run/dogfood_timing/runs/<label-or-run-id>.json
```

Record shape should be close to:

```json
{
  "schema_version": 1,
  "recorded_at": "2026-08-24T16:30:00Z",
  "label": "0019-lite-baseline",
  "commit": "abc1234",
  "run_id": "farm-run-...",
  "run_path": ".run/dogfood_0019/...",
  "status": "complete",
  "mode": "summarize",
  "agent": "default",
  "model": "qwen3.5:4b",
  "profile": "default",
  "runtime": {
    "concurrency": {
      "jobs": 1
    },
    "summarize": {
      "chunk_strategy": "token",
      "chunk_tokens": 4096,
      "reduce_tokens": 4096,
      "snippet_policy": "auto"
    }
  },
  "totals": {
    "duration_ms": 71894,
    "jobs": 4,
    "chunks": 13,
    "calls": 17,
    "queue_wait_ms": 0,
    "call_duration_ms": 70300,
    "by_call_kind": {
      "single": {
        "count": 1,
        "duration_ms": 4600
      },
      "chunk_map": {
        "count": 13,
        "duration_ms": 52200
      },
      "reduce": {
        "count": 3,
        "duration_ms": 13500
      }
    }
  },
  "slowest_jobs": [],
  "slowest_calls": [],
  "jobs": []
}
```

The exact shape can be refined during planning, but it should avoid copying article text, raw responses, full summaries, or full snippets.

### Per-Job Timing

Each record should include per-job rows useful for comparison:

- `job_id`
- input filename or relative path
- status
- duration
- queue wait
- chunk count
- call count
- call duration
- call counts and duration by kind
- warning count

The record may include input paths because current dogfood records already include paths, but it should not include source text.

### Comparison

The workflow should compare two timing records:

```powershell
python qwen.py farm dogfood timing compare <baseline-timing.json> <candidate-timing.json>
```

Suggested default output:

```text
.run/dogfood_timing/comparisons/<baseline>--<candidate>.json
.run/dogfood_timing/comparisons/<baseline>--<candidate>.md
```

Comparison should highlight:

- total run duration delta
- per-job duration deltas
- queue wait deltas
- chunk count deltas
- call count and call-duration deltas
- aggregate deltas by call kind
- slowest jobs/calls in the candidate
- comparability notes when model, profile, commit, chunk strategy, or concurrency differ

The first implementation does not need a pass/fail threshold. It should expose enough data for a human or primary AI to say "this got slower because chunks increased," "reduce dominated," or "these runs are not comparable because the profile changed."

### Relationship To Existing Dogfood Quality

Existing `farm dogfood record` and `farm dogfood compare` remain quality-oriented and include compact timing fields. This spec adds a more timing-focused record and comparison path so performance analysis does not have to piggyback on manual quality scores.

If planning finds that extending existing dogfood records is simpler than adding a nested `timing` subcommand, that is acceptable only if the resulting workflow is still obvious from the CLI and docs.

### Privacy And Tracked Files

Generated timing history stays under `.run/` by default and should remain ignored.

Tracked docs may explain the workflow, but should not include raw dogfood timing records unless a future tracked aggregate-history decision is made explicitly.

## Acceptance Criteria

- A reproducible command or script records timing history from an existing farm run.
- The timing record reads existing `farm-status.json` and uses `timing-summary.json` when present.
- The record captures run ID, label, status, mode, agent, model, profile, commit SHA when available, and compact runtime settings.
- The record captures total duration, total jobs, total chunks, total calls, queue wait, aggregate call duration, and aggregate duration by call kind.
- The record captures per-job duration, queue wait, chunk count, call count, call duration, call-kind aggregates, warning count, and status.
- The record includes slowest job and slowest call summaries.
- The record does not store raw article text, raw model responses, full summary Markdown, or full snippet text.
- A reproducible command or script compares two timing records.
- Comparison output includes JSON and Markdown.
- Comparison output highlights total, per-job, queue, chunk, call, and call-kind deltas.
- Comparison output includes comparability notes when runtime/model/profile/concurrency/chunk settings differ.
- Missing optional timing fields are handled gracefully for older run artifacts.
- Docs explain when to record timing history, how to compare runs, and how a primary AI should interpret the result.
- Model-free tests cover timing record extraction, missing-field compatibility, comparison deltas, comparability notes, Markdown rendering, and privacy guards.
- Existing dogfood quality history behavior remains unchanged.
- Existing schema validation behavior remains unchanged unless package schemas are intentionally extended in the implementation plan.
- No tests require Ollama, installed local models, tokenizer downloads, model calls, or network access.
- BL-0037 is marked planned/implemented as appropriate.

## Test Plan

Automated:

- fixture-based timing record extraction from `farm-status.json`
- fixture-based timing record extraction when `timing-summary.json` exists
- compatibility test for missing optional timing fields
- comparison delta calculations for totals, jobs, and call kinds
- comparability note generation when model/profile/concurrency/chunk settings differ
- Markdown comparison rendering
- guard test that source text, raw responses, full summaries, and full snippets are not copied into timing history
- regression tests for existing dogfood quality commands if parser paths are touched

Verification:

```powershell
python -m unittest tests.test_qwen_farm_timing tests.test_qwen_farm_dogfood
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

Dogfood:

Use a small local dogfood set, likely `dogfood_lite`, to record at least two comparable timing records under:

```text
.run/dogfood_0019/
.run/dogfood_timing/
```

Compare baseline and candidate timing records, then save a short local report:

```text
.run/dogfood_0019/DOGFOOD_TIMING_0019_REPORT.md
```

The dogfood report should answer:

- Did the timing record explain where run time went?
- Did the comparison make regressions or improvements obvious?
- Were non-comparable settings called out clearly?
- Did the artifact stay compact enough for a primary AI to inspect?

## Deferred To Roadmap

- Tracked aggregate timing history files.
- Dogfood timing dashboard or charts.
- Statistical thresholds or CI regression gates.
- Cross-machine benchmark normalization.
- Benchmark-based profile recommendations in `farm doctor`.
- Automatic config/profile tuning from timing history.
- Token-per-second metrics from backend eval/generation metadata.
- Scheduled benchmark checks on known hardware.
