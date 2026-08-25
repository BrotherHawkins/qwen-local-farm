# 0009 Add Dogfood Quality History

Status: Implemented
Type: Add

## WHY

After 0007 and 0008, snippet work is starting to produce visible quality improvements, but comparison is still mostly manual: inspect a run, write a report, remember whether the next run feels better. That is good enough for early dogfood, but it is a weak tool for deciding whether future snippet, chunking, prompt, or model changes improved value or merely moved the rough edges around.

The farm needs a lightweight dogfood history path that records comparable metrics and quality judgments across runs without committing raw article text or full source snippets.

This change favors:

- repeatable quality comparison over one-off dogfood impressions
- local-first history under `.run/`
- optional tracked docs/rubric without tracked article text
- metrics that help future primary AIs inspect a run quickly
- small scripts/commands over a full benchmark platform
- human-readable Markdown plus machine-readable JSON/JSONL

## Scope

This change adds a dogfood quality history workflow for summarize/snippet runs:

- define a compact quality rubric for article summary and snippet usefulness
- add a helper that records run-level and job-level dogfood metrics from an existing farm run directory
- store local history under `.run/dogfood_history/`
- support comparing a candidate run against a baseline run
- capture timing, chunking, snippet counts, warnings, model/config identifiers, and quality scores
- allow human or primary-AI-provided qualitative notes/scores
- generate a Markdown comparison report and machine-readable JSON summary
- keep source article text, raw responses, and full snippet text out of tracked files
- update BL-0049 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- automatic semantic grading by a frontier model
- network calls to an external eval service
- tracked raw article text
- tracked full source snippets or raw responses
- a web dashboard
- a statistical benchmark suite
- model installation or hardware benchmarking
- changes to snippet extraction/ranking behavior
- pass/fail gates based on subjective quality scores

## Behavior

### Quality Record

The history workflow should be able to summarize a farm run into a compact record:

```json
{
  "schema_version": 1,
  "recorded_at": "2026-08-24T16:30:00Z",
  "label": "0009-lite-candidate",
  "commit": "abc1234",
  "run_id": "farm-run-...",
  "run_path": ".run/dogfood_0009/...",
  "mode": "summarize",
  "model": "qwen3.5:4b",
  "status": "complete",
  "duration_ms": 71894,
  "totals": {
    "jobs": 4,
    "chunks": 13,
    "warnings": 0,
    "requested_snippets": 15,
    "verified_snippets": 9,
    "selected_snippets": 9,
    "dropped": {
      "unverified": 1,
      "low_signal": 0,
      "duplicate": 0,
      "too_long": 0
    }
  },
  "quality": {
    "summary_accuracy": 4,
    "summary_usefulness": 4,
    "snippet_usefulness": 4,
    "diagnostic_clarity": 5,
    "overall": 4
  },
  "notes": [
    "Article 004 snippets improved.",
    "Article 009 selected fewer but cleaner snippets."
  ]
}
```

The first implementation can keep quality fields manually supplied through a small JSON notes file, CLI flags, or a generated template. It does not need to judge quality automatically.

### Per-Job Metrics

The record should include per-job metrics useful for comparison:

- input filename
- status
- duration
- chunk count
- warning count and warning names
- requested/verified/selected snippet counts
- drop reason counts when present
- optional human/AI scores for summary accuracy, summary usefulness, snippet usefulness, and notes

The record should avoid storing full article text, raw model output, and full snippet text.

### Comparison

Given two recorded runs, the workflow should generate a comparison that highlights:

- total duration delta
- per-job duration deltas
- snippet selected/verified/requested deltas
- warning deltas
- score deltas
- notable regressions or improvements from supplied notes

Comparison output should include:

- machine-readable JSON
- human-readable Markdown

### Storage

Local generated history should live under:

```text
.run/dogfood_history/
```

Suggested files:

```text
.run/dogfood_history/runs/<label-or-run-id>.json
.run/dogfood_history/comparisons/<baseline>--<candidate>.json
.run/dogfood_history/comparisons/<baseline>--<candidate>.md
```

Tracked docs should be limited to reusable process/rubric guidance, for example:

```text
docs/dogfood-quality.md
```

If a future project wants tracked aggregate history, that should be a separate explicit decision because even aggregate dogfood history can become noisy.

### CLI Shape

The first implementation should prefer simple commands. Exact names can be refined during planning, but the shape should be close to:

```powershell
python sift.py farm dogfood record <run-dir> --label 0009-lite-candidate --notes .run/dogfood_0009/quality-notes.json
python sift.py farm dogfood compare <baseline-record.json> <candidate-record.json> --output .run/dogfood_history/comparisons
```

If nesting under `farm dogfood` makes the parser awkward, a small script under `scripts/` is acceptable for the first implementation as long as it is reproducible and documented.

### Rubric

Use a 1-5 scale:

- `1`: unusable or materially wrong
- `2`: partially useful but important gaps or noise
- `3`: acceptable with clear caveats
- `4`: good and worth using downstream
- `5`: excellent, compact, accurate, and easy to trust

Score dimensions:

- `summary_accuracy`
- `summary_usefulness`
- `snippet_usefulness`
- `diagnostic_clarity`
- `overall`

The rubric should encourage short notes explaining score changes so future comparisons are not just numbers.

## Acceptance Criteria

- A dogfood quality rubric exists in tracked docs.
- A reproducible command or script can record an existing farm run into a local JSON history record.
- The record captures run ID, status, model, mode, runtime config identifiers, commit SHA when available, total duration, and total warning count.
- The record captures per-job status, duration, chunk count, warning names, and snippet selected/verified/requested counts.
- The record captures snippet drop counts when present.
- The record can include human/AI quality scores and notes from a simple notes file or flags.
- The record does not store raw article text, raw model responses, or full snippet text.
- A reproducible command or script can compare two records.
- Comparison output includes JSON and Markdown.
- Comparison output highlights runtime, warning, snippet-count, and quality-score deltas.
- Missing optional fields are handled gracefully so older 0007/0008 runs can still be recorded.
- Docs explain how to record a run, score it, and compare it to a baseline.
- BL-0049 is marked planned/implemented as appropriate.
- Model-free tests cover record extraction, notes merging, missing-field compatibility, comparison deltas, and no-source-text persistence.
- Dogfood records the final 0008 run and at least one new 0009 candidate run or synthetic fixture, then compares them.

## Test Plan

Automated:

- record extraction from a fixture `farm-status.json`
- fixture run status with per-job result files present for privacy guard coverage
- missing snippet diagnostics compatibility for older runs
- quality notes merge
- comparison delta calculations
- Markdown comparison rendering
- guard test that full snippet text/raw response/article text are not copied into history records

Verification:

```powershell
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Dogfood:

Use:

```text
.run/dogfood_0009/
.run/dogfood_history/
```

Record the final 0008 run if it exists locally:

```text
.run/dogfood_0008/lite-ranked-final/farm-results/farm-run-2026-08-24-123139-37f1
```

Run or reuse a 0009 lite candidate, record it, compare it to the 0008 record, and write:

```text
.run/dogfood_0009/DOGFOOD_0009_REPORT.md
```

## Deferred To Roadmap

- Automatic frontier-model grading.
- Tracked aggregate history files.
- Web dashboard or charts.
- Statistical thresholds or CI quality gates.
- Cross-machine benchmark normalization.
- Broader mode support beyond summarize/snippet dogfood.
