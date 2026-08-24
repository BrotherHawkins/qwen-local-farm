# 0010 Add Cross-File Snippet Packs

Status: Implemented
Type: Add

## WHY

0007 and 0008 made per-article source snippets useful, and 0009 gave us a way to compare their quality over time. The next downstream need is synthesis: a primary or frontier model should be able to consume a compact, source-backed quote pack across many farm results without opening every `jobs/job-*/result.json` by hand.

The farm should provide a deterministic way to collect already verified snippets across a run, preserve provenance, cap the output to a useful budget, and make the pack easy to feed into a later synthesis prompt.

This change favors:

- post-run collection over extra model calls
- source-backed evidence for later frontier-model synthesis
- compact Markdown plus machine-readable JSON
- deterministic ranking and deduplication
- local ignored artifacts under `.run/` by default
- preserving per-file provenance without tracking article text

## Scope

This change adds cross-file snippet packs for summarize runs:

- add a command that reads an existing farm run directory
- collect selected verified snippets from per-job `result.json` files
- preserve source file, job ID, line/character provenance when present, rank metadata when present, and model-provided snippet reason when present
- deduplicate exact or near-identical snippet text across files
- rank snippets deterministically using existing snippet score metadata when available, with a stable fallback when not
- support configurable pack size and per-file cap
- write a Markdown pack for direct synthesis use
- write a JSON pack for scripts and primary-AI inspection
- record skipped/missing result files and no-snippet jobs as diagnostics instead of failing the whole pack
- update BL-0045 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- embedding-assisted or semantic snippet selection
- new snippet extraction behavior during `farm run`
- additional model calls to rerank snippets
- cross-file synthesis or final article generation
- quote/citation export formats beyond the first Markdown/JSON pack
- review states such as accepted/rejected snippets
- a UI for curating packs
- tracked snippet pack artifacts

## Behavior

### CLI Shape

The first implementation should prefer a reproducible post-run command:

```powershell
python qwen.py farm snippets pack <run-dir> --output .run/snippet_packs --label dogfood-lite --max-snippets 24 --per-file 4
```

Exact command names can be refined during planning. If nesting under `farm snippets` makes the parser awkward, `farm collect snippets` or `farm dogfood snippets` is acceptable, but the command should clearly read an existing run rather than starting a new farm run.

Defaults:

- output folder: `.run/snippet_packs/`
- label: run ID
- max snippets: a conservative synthesis-friendly default such as `24`
- per-file cap: a conservative default such as `4`
- include only selected snippets by default

### Input

The command accepts a farm run directory containing:

```text
farm-status.json
jobs/job-*/result.json
```

It should use `farm-status.json` as the run index and read only successful or warning-complete jobs with `result_json` paths. Missing, failed, or malformed result files should be recorded in pack diagnostics and skipped.

The first version should collect selected snippets already emitted by summarize mode. It should not re-open the original source article text unless implementation needs a cheap verification guard; if it does, it must not copy more than selected snippet text into the pack.

### Output

For a label `dogfood-lite`, write:

```text
.run/snippet_packs/dogfood-lite.json
.run/snippet_packs/dogfood-lite.md
```

JSON shape:

```json
{
  "schema_version": 1,
  "created_at": "2026-08-24T17:00:00Z",
  "label": "dogfood-lite",
  "run_id": "farm-run-...",
  "run_path": ".run/dogfood_lite/...",
  "mode": "summarize",
  "model": "qwen3.5:4b",
  "limits": {
    "max_snippets": 24,
    "per_file": 4,
    "source": "selected"
  },
  "counts": {
    "jobs_seen": 4,
    "jobs_with_snippets": 4,
    "candidates": 10,
    "selected": 10,
    "duplicates_dropped": 0,
    "jobs_skipped": 0
  },
  "snippets": [
    {
      "id": "snippet-0001",
      "input_path": "articles/009-qmd-query-markup-documents.txt",
      "job_id": "job-0004",
      "text": "Exact verified snippet text.",
      "reason": "Why this passage matters.",
      "score": 12,
      "score_reasons": ["definition", "mechanism"],
      "start_line": 42,
      "end_line": 45,
      "start_char": 2310,
      "end_char": 2578
    }
  ],
  "diagnostics": {
    "skipped_jobs": [],
    "warnings": []
  }
}
```

Markdown shape should be concise and synthesis-friendly:

```markdown
# Snippet Pack dogfood-lite

Run: farm-run-...
Model: qwen3.5:4b
Selected snippets: 10

## 009-qmd-query-markup-documents.txt

1. "Exact verified snippet text."
   Source: job-0004, lines 42-45
   Why it matters: Why this passage matters.
```

The Markdown should group snippets by input file so a downstream model can see source context without needing full article text.

### Selection And Ranking

The pack command should prefer:

- snippets already selected by the per-file summarization result
- higher `score` values when present
- diverse input files before filling remaining budget
- stable ordering by source file, job ID, and source position when scores tie

The pack should not invent new snippet text. Every packed snippet must come from a selected snippet in a result artifact.

Deduplication should remove exact duplicate text. Near-duplicate handling can be simple normalization such as lowercasing, whitespace collapsing, and stripping punctuation at the edges.

### Diagnostics

The JSON output should record:

- jobs seen
- jobs skipped and reasons
- malformed result files
- jobs without selected snippets
- duplicate snippets dropped
- total candidates before caps
- selected count after caps

Markdown output may include a short diagnostics section only when there are warnings or skipped jobs.

## Acceptance Criteria

- A reproducible command can create a cross-file snippet pack from an existing farm run directory.
- The command reads `farm-status.json` and per-job `result.json` files rather than rerunning summaries.
- The command writes Markdown and JSON outputs under `.run/snippet_packs/` by default.
- The output label is configurable and defaults to the run ID.
- The output includes run ID, model, mode, run path, limits, counts, snippets, and diagnostics.
- The output preserves snippet text, reason, input path, job ID, line/character provenance when present, and score metadata when present.
- The command supports configurable `--max-snippets` and `--per-file` caps.
- Exact duplicate and simple near-duplicate snippets are not packed twice.
- Selection is deterministic across repeated runs with the same inputs and options.
- File diversity is preferred before filling remaining snippet budget.
- Missing, failed, malformed, or no-snippet jobs are skipped with diagnostics instead of crashing the whole pack.
- Runs with no selected snippets produce an empty pack with clear diagnostics.
- The pack command does not perform model calls.
- Existing `farm run`, `farm list`, `farm status`, dogfood history, and snippet extraction behavior remain unchanged.
- Docs explain when to use snippet packs and how to feed them to a downstream synthesis model.
- BL-0045 is marked planned/implemented as appropriate.
- Deferred related items remain in backlog.
- Model-free tests cover collection, ranking, caps, deduplication, malformed/missing result handling, empty packs, Markdown rendering, JSON shape, and CLI parsing.

## Test Plan

Automated:

- unit tests for collecting snippets from fixture farm run artifacts
- unit tests for exact and normalized duplicate removal
- unit tests for max-snippet and per-file caps
- unit tests for deterministic ranking and file diversity
- unit tests for missing/malformed/no-snippet jobs
- unit tests for empty pack diagnostics
- unit tests for Markdown rendering
- CLI parser tests for the new pack command
- full model-free test suite

Verification:

```powershell
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

Dogfood:

Use a new ignored folder:

```text
.run/dogfood_0010/
```

Create a snippet pack from the latest dogfood lite run with snippets:

```powershell
python qwen.py farm snippets pack .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/dogfood_0010/snippet-packs --label dogfood-lite-0010
```

Inspect:

- whether all four lite articles contribute useful evidence when budget allows
- whether article 004 and 009 dominate only when their scores justify it
- whether snippets remain exact and source-backed
- whether Markdown is easy to paste into a frontier-model synthesis prompt
- whether JSON is easy for a primary AI to inspect
- whether skipped/no-snippet diagnostics are clear

Write:

```text
.run/dogfood_0010/DOGFOOD_0010_REPORT.md
```

## Deferred To Roadmap

- Embedding-assisted or semantic snippet selection.
- Cross-file synthesis that consumes snippet packs and summaries.
- Quote and citation export formats beyond Markdown/JSON.
- Snippet review states such as accepted/rejected/superseded.
- Cross-run snippet packs that merge evidence across separate farm runs.
- UI or dashboard support for browsing snippet packs.
- Run-ID lookup for post-run helper commands.
- Optional synthesis bundles that include compact summaries alongside snippets.
