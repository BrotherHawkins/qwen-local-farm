# 0011 Implement Summary Snippet Synthesis Bundles

Status: Implemented
Change Spec: [0011 Add Summary Snippet Synthesis Bundles](../changes/0011-add-summary-snippet-synthesis-bundles.md)

## WHY

Snippet packs are useful evidence, but downstream synthesis often needs summaries for orientation and snippets for grounding. 0011 packages both layers from existing summarize results into one model-free bundle that a primary or frontier model can consume without artifact hunting.

## Scope

Planned:

- `farm synthesis bundle` command for existing farm run directories
- local Markdown and JSON synthesis bundle outputs under `.run/synthesis_bundles/` by default
- per-file summary items from successful or warning-complete summarize job results
- selected verified snippets attached to their source summary items
- deterministic snippet deduplication, cross-file diversity, and caps using the 0010 packer behavior
- graceful diagnostics for missing, malformed, failed, empty, or non-summary jobs
- docs explaining bundle usage and when to prefer it over snippet-only packs
- model-free tests for summary collection, snippet attachment, caps, dedupe, rendering, diagnostics, and CLI parsing
- dogfood against the latest dogfood lite snippet run

Deferred:

- final cross-file synthesis generation from bundles
- run-ID lookup for post-run helper commands
- summary field filters and custom templates
- token or character budget planning for bundle outputs
- citation-specific export formats
- cross-run synthesis bundles
- bundle browsing UI

## Implementation Plan

### 1. Reuse 0010 Snippet Pack Primitives

Use `src/qwen_farm_snippet_packs.py` for:

- reading JSON objects where sensible
- resolving per-job `result_json` paths
- normalizing selected snippets
- duplicate normalization
- deterministic snippet sorting
- per-file and total snippet caps
- source description formatting where sensible
- safe output labels

Avoid copying 0010 logic unless the bundle schema genuinely needs a different representation.

### 2. Add Synthesis Bundle Module

Create `src/qwen_farm_synthesis_bundles.py` with pure helpers:

- read `farm-status.json`
- iterate successful and warning-complete jobs in farm-status order
- load each job `result.json`
- normalize summary fields from `result`
- identify empty or non-summary payloads
- collect selected snippets per job
- apply global snippet dedupe/caps across jobs
- reattach selected snippets to their source summary items
- build diagnostics for skipped jobs and warnings
- render Markdown grouped by source item
- write JSON and Markdown bundle artifacts

Keep this module model-free and independent from `farm run`.

### 3. Define Bundle Schema

Use schema version `1`.

Persist:

- label, run ID, run path, mode, model, created timestamp
- limits: `max_snippets`, `per_file`, snippet source
- counts: jobs seen, items, items with snippets, snippet candidates, snippets selected, duplicates dropped, jobs skipped
- items with ID, input path, job ID, status, warnings, summary, snippets
- diagnostics with skipped jobs and warnings

Summary fields:

- `title`
- `abstract`
- `bullets`
- `open_questions`
- `confidence`

Do not persist:

- raw article text
- raw model responses
- chunk intermediate payloads
- unselected snippet candidates

The bundle intentionally includes compact file-level summaries because that is the feature.

### 4. Add CLI Command

Extend `sift.py farm` with:

```powershell
python sift.py farm synthesis bundle <run-dir> --output <output-folder> --label <label> --max-snippets <n> --per-file <n>
```

Defaults:

- output: `.run/synthesis_bundles/`
- label: run ID
- max snippets: `24`
- per-file: `4`

The command should print JSON and Markdown paths plus item/snippet counts.

### 5. Add Docs

Update:

- `README.md` near snippet pack guidance
- `docs/ai-usage.md` with downstream synthesis guidance
- `docs/roadmap.md` implemented baseline when implementation lands

Keep docs concise unless the usage section becomes crowded.

### 6. Update Planning Docs

Update:

- `docs/backlog.md`
- `docs/specs/SPEC_DASHBOARD.md`
- `docs/specs/changes/0011-add-summary-snippet-synthesis-bundles.md`
- `docs/specs/plans/0011-implement-summary-snippet-synthesis-bundles.md`

When implementation is complete in the PR, mark 0011 implemented in the same PR and mark BL-0059 implemented.

### 7. Dogfood

Use:

```text
.run/dogfood_0011/
```

Create a bundle from the latest dogfood lite run:

```powershell
python sift.py farm synthesis bundle .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/dogfood_0011/synthesis-bundles --label dogfood-lite-0011
```

Inspect:

- item count and article coverage
- selected snippet count and duplicate drops
- whether summary-plus-evidence Markdown is better synthesis input than snippet-only Markdown
- whether JSON is easy for a primary AI to inspect
- skipped/no-snippet diagnostics

Write:

```text
.run/dogfood_0011/DOGFOOD_0011_REPORT.md
```

## Test Plan

Automated:

- collect summaries and snippets from fixture run artifacts
- include summary-only jobs
- tolerate missing optional summary fields
- skip failed jobs with diagnostics
- skip missing/malformed result files with diagnostics
- skip empty/non-summary payloads with diagnostics
- remove exact and normalized duplicate snippets
- apply `--max-snippets` and `--per-file` caps
- preserve deterministic item order and snippet selection
- attach selected snippets to their source summary items
- render Markdown with summaries and evidence grouped by input file
- parse CLI arguments for `farm synthesis bundle`
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
- [x] Bundle command exists.
- [x] Bundle command reads existing run artifacts without model calls.
- [x] JSON bundle output exists.
- [x] Markdown bundle output exists.
- [x] Output defaults to `.run/synthesis_bundles/`.
- [x] Label, max-snippets, and per-file options work.
- [x] Bundle schema includes run metadata, limits, counts, items, snippets, and diagnostics.
- [x] Items preserve summary fields, input/job provenance, status, warnings, and snippets when present.
- [x] Summary-only jobs are included.
- [x] Missing optional summary fields are handled gracefully.
- [x] Missing, malformed, failed, and empty/non-summary jobs are handled gracefully.
- [x] Duplicates are dropped deterministically.
- [x] File diversity is preferred before filling remaining snippet budget.
- [x] Existing farm run/status/dogfood/snippet pack behavior is unchanged.
- [x] Docs explain synthesis bundle usage.
- [x] Backlog/dashboard/spec statuses are updated.
- [x] Model-free tests pass.
- [x] Compile check passes.
- [x] Diff check passes.
- [x] Dogfood 0011 report is recorded.
