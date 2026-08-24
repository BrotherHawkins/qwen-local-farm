# 0009 Implement Dogfood Quality History

Status: Implemented
Change Spec: [0009 Add Dogfood Quality History](../changes/0009-add-dogfood-quality-history.md)

## WHY

Snippet quality now changes enough across specs that we need a reusable yardstick. 0009 adds a local dogfood history and comparison workflow so future snippet/chunking/prompt work can be judged against comparable run metrics and explicit quality notes instead of only prose reports.

## Scope

Planned:

- `farm dogfood record` command for existing farm run directories
- `farm dogfood compare` command for two dogfood history records
- local JSON history under `.run/dogfood_history/`
- Markdown and JSON comparison output
- quality notes/rubric support without external model calls
- no raw article text, raw model responses, or full snippet text in history records
- tracked dogfood quality rubric docs
- tests for record extraction, notes merging, comparison, rendering, and no-source-text persistence
- dogfood against the final 0008 run and a new 0009 lite run

Deferred:

- automatic frontier-model grading
- tracked aggregate history files
- web dashboard or charts
- CI quality gates
- cross-machine benchmark normalization
- broader non-summarize dogfood modes

## Implementation Plan

### 1. Add Dogfood History Module

Create `src/qwen_farm_dogfood.py` with pure helpers:

- load compact farm status from a run directory
- normalize optional quality notes
- build a compact history record
- write records under `.run/dogfood_history/runs/`
- compare two records
- render comparison Markdown
- write comparison JSON/Markdown under `.run/dogfood_history/comparisons/`

### 2. Add CLI Commands

Extend `qwen.py farm` with:

```powershell
python qwen.py farm dogfood record <run-dir> --label <label> --notes <notes.json>
python qwen.py farm dogfood compare <baseline-record.json> <candidate-record.json> --output <output-folder>
```

Defaults:

- record output defaults to `.run/dogfood_history/runs`
- compare output defaults to `.run/dogfood_history/comparisons`
- `--label` defaults to run id
- notes are optional

### 3. Define Quality Notes Shape

Support a simple JSON file:

```json
{
  "quality": {
    "summary_accuracy": 4,
    "summary_usefulness": 4,
    "snippet_usefulness": 4,
    "diagnostic_clarity": 5,
    "overall": 4
  },
  "notes": ["Short run-level note."],
  "jobs": {
    "002-the-append-and-review-note-karpathy.txt": {
      "quality": {
        "summary_accuracy": 4,
        "snippet_usefulness": 5,
        "overall": 4
      },
      "notes": ["Snippet anchors were strong."]
    }
  }
}
```

Missing scores and notes should be accepted.

### 4. Keep Records Compact

Persist:

- run id, label, recorded time, commit SHA, run path, mode, model, status
- duration, runtime/config summary, total counts
- per-job status, duration, chunk count, warnings, snippet counts, drop counts
- quality scores and notes

Do not persist:

- input file contents
- raw model responses
- full snippet text
- full summary Markdown

### 5. Add Docs

Add `docs/dogfood-quality.md` with:

- scoring rubric
- how to write notes
- record command
- compare command
- privacy/non-tracking rules
- how primary AIs should use the comparison output

Update README and AI usage docs with a short pointer.

### 6. Update Planning Docs

Update:

- `docs/backlog.md`
- `docs/roadmap.md`
- `docs/specs/SPEC_DASHBOARD.md`

Mark 0009 implemented in the same PR if the implementation lands in that PR.

### 7. Dogfood

Use:

```text
.run/dogfood_0009/
.run/dogfood_history/
```

Record the final 0008 run if present:

```text
.run/dogfood_0008/lite-ranked-final/farm-results/farm-run-2026-08-24-123139-37f1
```

Run or reuse a new 0009 lite candidate, record it, compare it to 0008, and write:

```text
.run/dogfood_0009/DOGFOOD_0009_REPORT.md
```

## Test Plan

Automated:

- record extraction from fixture run status/result files
- notes merge at run and job levels
- missing snippet fields compatibility
- comparison delta calculations
- Markdown comparison rendering
- no source text/raw response/full snippet text persistence
- CLI parser tests for record and compare commands

Verification:

```powershell
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

## Acceptance Checklist

- [x] Change spec exists.
- [x] Human accepted the behavior target.
- [x] Implementation plan exists.
- [x] Human accepted the implementation plan.
- [x] Record command exists.
- [x] Compare command exists.
- [x] Records are written under `.run/dogfood_history/runs` by default.
- [x] Comparisons are written under `.run/dogfood_history/comparisons` by default.
- [x] Records include run/model/status/timing/config identifiers.
- [x] Records include per-job timing/chunk/warning/snippet metrics.
- [x] Records include snippet drop counts when present.
- [x] Records can merge optional quality notes.
- [x] Records omit source text, raw responses, and full snippet text.
- [x] Comparison JSON and Markdown are generated.
- [x] Comparison highlights runtime, warnings, snippet counts, and quality deltas.
- [x] Older/missing snippet fields are handled gracefully.
- [x] Dogfood quality docs exist.
- [x] Backlog/roadmap/dashboard are updated.
- [x] Model-free tests pass.
- [x] Compile check passes.
- [x] Diff check passes.
- [x] Dogfood 0009 report is recorded.
