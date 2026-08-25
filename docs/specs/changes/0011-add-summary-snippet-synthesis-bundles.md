# 0011 Add Summary Snippet Synthesis Bundles

Status: Implemented
Type: Add

## WHY

0010 made source snippet packs easy to hand to a downstream synthesis model, but snippets alone are only half of the useful context. A frontier or primary model usually benefits from two layers at once: a compact per-file summary to understand the argument, and a small set of verified snippets to ground the synthesis in source evidence.

Today that means a caller has to inspect each job's `result.json` or combine a snippet pack with separate summaries by hand. The farm should be able to package both layers into one local artifact that is ready to paste into a synthesis prompt or consume from JSON.

This change favors:

- post-run packaging over new local model calls
- synthesis-ready context over final synthesis generation
- compact summaries plus source-backed snippets
- deterministic, inspectable outputs
- local ignored artifacts under `.run/` by default
- preserving provenance without copying raw article text or raw model responses

## Scope

This change adds summary-plus-snippet synthesis bundles for summarize runs:

- add a command that reads an existing farm run directory
- collect compact summary fields from per-job `result.json` files
- collect selected verified snippets using the same deterministic cap/dedupe behavior as 0010
- include jobs with usable summaries even when they have no snippets
- preserve source file, job ID, status, warnings, summary fields, confidence, snippet provenance, and snippet score metadata when present
- write a Markdown bundle for direct downstream synthesis prompts
- write a JSON bundle for scripts and primary-AI inspection
- support configurable snippet budget and per-file snippet cap
- record skipped/missing/malformed jobs in diagnostics
- update BL-0059 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- a model call that performs the final cross-file synthesis
- semantic snippet selection
- new summary or snippet extraction behavior during `farm run`
- citation-specific export formats
- tracked synthesis bundle artifacts
- run-ID lookup for post-run helper commands
- UI for reviewing or editing bundles
- multi-run bundle merging

## Behavior

### CLI Shape

The first implementation should prefer a reproducible post-run command:

```powershell
python sift.py farm synthesis bundle <run-dir> --output .run/synthesis_bundles --label dogfood-lite --max-snippets 24 --per-file 4
```

Exact command names can be refined during planning. The command should clearly read existing run artifacts and must not start a new farm run or call a model.

Defaults:

- output folder: `.run/synthesis_bundles/`
- label: run ID
- max snippets: `24`
- per-file snippet cap: `4`
- include selected snippets only
- include all successful or warning-complete summarize jobs with usable summary payloads

### Input

The command accepts a farm run directory containing:

```text
farm-status.json
jobs/job-*/result.json
```

It should use `farm-status.json` as the run index. For each successful or warning-complete job with a readable `result_json`, read the summary payload from `result`.

Expected summary fields:

- `title`
- `abstract`
- `bullets`
- `open_questions`
- `confidence`
- optional `snippets`

Missing optional fields should be handled gracefully. Jobs with no selected snippets should still be included when they have any useful summary text.

Failed jobs, missing result paths, malformed result files, and empty/non-summary payloads should be recorded in diagnostics and skipped.

### Output

For a label `dogfood-lite`, write:

```text
.run/synthesis_bundles/dogfood-lite.json
.run/synthesis_bundles/dogfood-lite.md
```

JSON shape:

```json
{
  "schema_version": 1,
  "created_at": "2026-08-24T18:00:00Z",
  "label": "dogfood-lite",
  "run_id": "farm-run-...",
  "run_path": ".run/dogfood_lite/...",
  "mode": "summarize",
  "model": "qwen3.5:4b",
  "limits": {
    "max_snippets": 24,
    "per_file": 4,
    "snippet_source": "selected"
  },
  "counts": {
    "jobs_seen": 4,
    "items": 4,
    "items_with_snippets": 4,
    "snippet_candidates": 10,
    "snippets_selected": 10,
    "duplicates_dropped": 0,
    "jobs_skipped": 0
  },
  "items": [
    {
      "id": "item-0001",
      "input_path": "articles/009-qmd-query-markup-documents.txt",
      "job_id": "job-0004",
      "status": "complete",
      "warnings": [],
      "summary": {
        "title": "QMD Query Markup Documents",
        "abstract": "Compact summary text.",
        "bullets": ["Key claim."],
        "open_questions": ["Open question."],
        "confidence": "medium"
      },
      "snippets": [
        {
          "id": "snippet-0001",
          "text": "Exact verified snippet text.",
          "reason": "Why this passage matters.",
          "score": 12,
          "score_reasons": ["definition", "mechanism"],
          "start_line": 42,
          "end_line": 45
        }
      ]
    }
  ],
  "diagnostics": {
    "skipped_jobs": [],
    "warnings": []
  }
}
```

Markdown shape should be optimized for downstream synthesis:

```markdown
# Synthesis Bundle dogfood-lite

Run: farm-run-...
Model: qwen3.5:4b
Items: 4
Selected snippets: 10

## 009-qmd-query-markup-documents.txt

Summary: Compact summary text.

Key points:
- Key claim.

Open questions:
- Open question.

Evidence:
1. "Exact verified snippet text."
   Source: job-0004, lines 42-45
   Why it matters: Why this passage matters.
```

The Markdown should group by input file and keep each item compact enough to paste into a frontier-model prompt without reintroducing full article length.

### Selection And Ordering

The bundle should:

- keep items ordered deterministically by source path or farm job order
- use the same selected verified snippets as the 0010 pack command
- deduplicate snippets across files using the 0010 normalization behavior
- prefer file diversity before filling the remaining snippet budget
- keep each selected snippet attached to its source item

The bundle should not invent summary or snippet text. It should only repackage existing farm result artifacts.

### Diagnostics

The JSON output should record:

- jobs seen
- items included
- items with snippets
- skipped jobs and reasons
- malformed result files
- empty/non-summary payloads
- duplicate snippets dropped
- total snippet candidates before caps
- selected snippet count after caps

Markdown output may include diagnostics only when warnings or skipped jobs exist.

## Acceptance Criteria

- A reproducible command can create a summary-plus-snippet synthesis bundle from an existing farm run directory.
- The command reads `farm-status.json` and per-job `result.json` files rather than rerunning summaries.
- The command writes Markdown and JSON outputs under `.run/synthesis_bundles/` by default.
- The output label is configurable and defaults to the run ID.
- The output includes run ID, model, mode, run path, limits, counts, items, snippets, and diagnostics.
- Each included item preserves input path, job ID, status, warnings, summary fields, confidence, and selected snippets when present.
- Jobs with useful summaries but no snippets are included.
- Missing optional summary fields are handled gracefully.
- Failed, missing, malformed, or empty/non-summary jobs are skipped with diagnostics instead of crashing the whole bundle.
- Snippet `--max-snippets` and `--per-file` caps are configurable.
- Snippet deduplication and file-diverse selection are deterministic.
- The command does not perform model calls.
- Existing `farm run`, `farm list`, `farm status`, dogfood history, and snippet pack behavior remain unchanged.
- Docs explain when to use synthesis bundles instead of snippet-only packs.
- BL-0059 is marked planned/implemented as appropriate.
- Deferred related items remain in backlog.
- Model-free tests cover summary collection, snippet attachment, caps, deduplication, missing fields, no-snippet summaries, malformed/missing jobs, empty bundles, Markdown rendering, JSON shape, and CLI parsing.

## Test Plan

Automated:

- unit tests for collecting summaries and snippets from fixture farm run artifacts
- unit tests for including summary-only jobs
- unit tests for missing optional summary fields
- unit tests for exact and normalized duplicate snippet removal
- unit tests for max-snippet and per-file caps
- unit tests for deterministic snippet selection and item ordering
- unit tests for missing/malformed/failed/empty jobs
- unit tests for empty bundle diagnostics
- unit tests for Markdown rendering
- CLI parser tests for the new bundle command
- full model-free test suite

Verification:

```powershell
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Dogfood:

Use a new ignored folder:

```text
.run/dogfood_0011/
```

Create a synthesis bundle from the latest dogfood lite run with snippets:

```powershell
python sift.py farm synthesis bundle .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/dogfood_0011/synthesis-bundles --label dogfood-lite-0011
```

Inspect:

- whether all four lite articles contribute compact summary context
- whether snippets remain useful and source-backed
- whether the Markdown is better synthesis input than the snippet-only pack
- whether JSON is easy for a primary AI to inspect
- whether no-snippet and skipped-job diagnostics are clear

Write:

```text
.run/dogfood_0011/DOGFOOD_0011_REPORT.md
```

## Deferred To Roadmap

- Final cross-file synthesis generation from bundles.
- Run-ID lookup for post-run helper commands.
- Summary field filtering or custom bundle templates.
- Token or character budget planning for bundle outputs.
- Citation-specific export formats.
- Cross-run synthesis bundles.
- UI or dashboard support for browsing bundles.
