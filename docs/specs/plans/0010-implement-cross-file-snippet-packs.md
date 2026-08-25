# 0010 Implement Cross-File Snippet Packs

Status: Implemented
Change Spec: [0010 Add Cross-File Snippet Packs](../changes/0010-add-cross-file-snippet-packs.md)

## WHY

The farm can now produce useful per-file summaries with verified source snippets, but downstream synthesis still requires a primary AI to hunt through every job artifact. 0010 adds a deterministic post-run packaging step so selected snippets can be gathered into one compact, source-backed pack for frontier-model synthesis.

## Scope

Planned:

- `farm snippets pack` command for existing farm run directories
- local Markdown and JSON snippet pack outputs under `.run/snippet_packs/` by default
- compact run metadata, limits, counts, diagnostics, and packed snippets
- deterministic cross-file ranking, caps, and deduplication
- graceful diagnostics for missing, malformed, failed, or no-snippet jobs
- docs for using snippet packs in downstream synthesis prompts
- model-free tests for collection, ranking, caps, dedupe, rendering, diagnostics, and CLI parsing
- dogfood against the latest dogfood lite snippet run

Deferred:

- semantic or embedding-assisted snippet selection
- cross-file synthesis that consumes snippet packs
- citation export formats beyond Markdown/JSON
- snippet review states
- cross-run snippet packs
- snippet pack browsing UI
- run-ID lookup for post-run helper commands
- synthesis bundles that include summaries alongside snippets

## Implementation Plan

### 1. Add Snippet Pack Module

Create `src/sift_farm_snippet_packs.py` with pure helpers:

- read `farm-status.json`
- resolve job `result_json` paths relative to the run directory
- collect selected snippets from successful or warning-complete jobs
- normalize snippet records into a pack schema
- normalize text for exact/simple near-duplicate detection
- rank snippets deterministically
- apply per-file and total caps with file diversity
- build diagnostics for skipped/no-snippet/malformed jobs
- write JSON and Markdown pack artifacts

Keep this module model-free and independent from `farm run`.

### 2. Define Pack Schema

Use schema version `1`.

Persist:

- label, run ID, run path, mode, model, created timestamp
- limits: `max_snippets`, `per_file`, source mode
- counts: jobs seen, jobs with snippets, candidates, selected, duplicates dropped, jobs skipped
- snippets with ID, input path, job ID, text, reason, score, score reasons, source location fields when present
- diagnostics with skipped jobs and warnings

Do not persist:

- full article text
- raw model responses
- full summaries
- unselected snippet candidates

### 3. Add CLI Command

Extend `sift.py farm` with:

```powershell
python sift.py farm snippets pack <run-dir> --output <output-folder> --label <label> --max-snippets <n> --per-file <n>
```

Defaults:

- output: `.run/snippet_packs/`
- label: run ID
- max snippets: `24`
- per-file: `4`

The command should print the JSON and Markdown paths.

### 4. Add Docs

Update:

- `README.md` with a short mention near snippet usage
- `docs/ai-usage.md` with commands and downstream synthesis guidance

Add a focused doc only if the README/AI usage sections become too dense.

### 5. Update Planning Docs

Update:

- `docs/backlog.md`
- `docs/roadmap.md` if a short roadmap note helps
- `docs/specs/SPEC_DASHBOARD.md`
- `docs/specs/changes/0010-add-cross-file-snippet-packs.md`

When implementation is complete in the PR, mark 0010 implemented in the same PR and mark BL-0045 implemented.

### 6. Dogfood

Use:

```text
.run/dogfood_0010/
```

Create a pack from the latest dogfood lite run:

```powershell
python sift.py farm snippets pack .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/dogfood_0010/snippet-packs --label dogfood-lite-0010
```

Inspect:

- article coverage
- selected count and duplicate drops
- whether Markdown is synthesis-ready
- whether JSON is primary-AI friendly
- skipped/no-snippet diagnostics

Write:

```text
.run/dogfood_0010/DOGFOOD_0010_REPORT.md
```

## Test Plan

Automated:

- collect snippets from fixture run artifacts
- omit failed jobs and record diagnostics
- omit missing/malformed result files and record diagnostics
- produce empty packs with useful diagnostics
- remove exact and normalized duplicate snippets
- apply `--max-snippets` and `--per-file` caps
- prefer file diversity before filling remaining budget
- preserve score/provenance/reason fields when present
- render Markdown grouped by input file
- parse CLI arguments for `farm snippets pack`
- full model-free test suite

Verification:

```powershell
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

## Acceptance Checklist

- [x] Change spec is accepted.
- [x] Implementation plan is accepted.
- [x] Pack command exists.
- [x] Pack command reads existing run artifacts without model calls.
- [x] JSON pack output exists.
- [x] Markdown pack output exists.
- [x] Output defaults to `.run/snippet_packs/`.
- [x] Label, max-snippets, and per-file options work.
- [x] Pack schema includes run metadata, limits, counts, snippets, and diagnostics.
- [x] Snippet records preserve text, reason, input/job provenance, source location, score, and score reasons when present.
- [x] Duplicates are dropped deterministically.
- [x] File diversity is preferred before filling remaining budget.
- [x] Missing, malformed, failed, and no-snippet jobs are handled gracefully.
- [x] Empty packs are clear and non-crashing.
- [x] Existing farm run/status/dogfood/snippet behavior is unchanged.
- [x] Docs explain snippet pack usage.
- [x] Backlog/roadmap/dashboard are updated.
- [x] Model-free tests pass.
- [x] Compile check passes.
- [x] Diff check passes.
- [x] Dogfood 0010 report is recorded.
