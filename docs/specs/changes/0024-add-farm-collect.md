# 0024 Add Farm Collect

Status: Implemented
Type: Add

## WHY

The farm already writes durable per-job artifacts, status files, snippet packs, synthesis bundles, dogfood records, and timing records. Those artifacts are useful, but a primary AI or human still has to understand the run folder layout before they can gather the ordinary file-level outputs from a completed run.

BL-0010 originally deferred `farm collect` from the worker-farm MVP. The missing behavior is not another synthesis tool. It is a simple post-run collection helper that says: "take this run and gather the outputs I am most likely to inspect next."

This protects a small product principle:

- the farm can remain filesystem-first without making callers crawl `jobs/job-*`
- post-run helpers should be reproducible and model-free
- collection should preserve provenance and existing artifacts instead of rewriting results
- richer packages such as snippet packs and synthesis bundles should stay available for specialized downstream workflows

## Scope

This change adds a first-pass `farm collect` command that:

- accepts an existing farm run reference
- resolves either a run directory path or a known run ID, matching other post-run helpers
- writes a local ignored collection folder under `.run/` by default
- flattens successful and warning-complete job result artifacts into stable, safe filenames
- writes a machine-readable collection manifest
- writes a human-readable Markdown collection index
- records skipped, failed, missing, malformed, and incomplete jobs in diagnostics
- never calls a model
- never copies source input files or raw model responses by default
- adds a tracked JSON schema for the collection manifest
- updates docs and backlog lifecycle records for BL-0010

The intended first command shape is:

```powershell
python sift.py farm collect <run-ref> --output .run/farm_collections --label dogfood-lite
```

`<run-ref>` can be either:

- a run directory path
- a known run ID from `python sift.py farm list`

## Non-Goals

This change does not add:

- new farm-run processing behavior
- model calls
- final cross-file synthesis
- snippet selection or ranking changes
- bundle budget fitting
- queue or scheduler behavior
- copying source input files
- copying raw model responses by default
- zip/archive export
- cross-run collection
- interactive review UI
- changing existing `farm snippets pack`, `farm synthesis bundle`, dogfood, timing, status, or schema-validation behavior

## Behavior

### CLI Shape

Add:

```powershell
python sift.py farm collect <run-ref>
python sift.py farm collect <run-ref> --output .run/farm_collections --label my-run
```

Defaults:

- output folder: `.run/farm_collections/`
- label: run ID
- collected job statuses: `complete`, `complete_with_warnings`
- copied artifacts: available `result.md` and `result.json`
- skipped jobs: all other job statuses or jobs with missing/malformed result artifacts

The command should print the created collection manifest and Markdown index paths.

The command must fail clearly when `<run-ref>` cannot be resolved.

### Output Layout

For label `dogfood-lite`, write:

```text
.run/farm_collections/
  dogfood-lite/
    FARM_COLLECTION.md
    farm-collection.json
    items/
      item-0001-article-title.md
      item-0001-article-title.json
      item-0002-notes.md
      item-0002-notes.json
```

Item filenames should be stable and safe:

- prefix with `item-0001`, `item-0002`, and so on in farm-status job order
- include a short slug from the input filename when possible
- avoid encoding full source paths into filenames
- avoid collisions within the collection folder

### Collection Manifest

`farm-collection.json` should use a tracked schema and this general shape:

```json
{
  "schema_version": 1,
  "created_at": "2026-08-24T18:00:00Z",
  "label": "dogfood-lite",
  "run_id": "farm-run-...",
  "run_path": ".run/dogfood_lite/farm-results/farm-run-...",
  "mode": "summarize",
  "agent": "default",
  "model": "qwen3.5:4b",
  "counts": {
    "jobs_seen": 4,
    "items_collected": 4,
    "markdown_files": 4,
    "json_files": 4,
    "jobs_skipped": 0
  },
  "artifacts": {
    "markdown_index": "FARM_COLLECTION.md",
    "manifest": "farm-collection.json",
    "items_dir": "items"
  },
  "items": [
    {
      "id": "item-0001",
      "job_id": "job-0001",
      "input_path": "articles/005-karpathy-llm-wiki-starter-vault.txt",
      "status": "complete",
      "warnings": [],
      "source_artifacts": {
        "result_md": "jobs/job-0001/result.md",
        "result_json": "jobs/job-0001/result.json"
      },
      "collected_artifacts": {
        "result_md": "items/item-0001-karpathy-llm-wiki-starter-vault.md",
        "result_json": "items/item-0001-karpathy-llm-wiki-starter-vault.json"
      },
      "summary": {
        "title": "LLM Wiki Starter Vault",
        "abstract": "Compact abstract when available.",
        "confidence": "medium"
      }
    }
  ],
  "diagnostics": {
    "skipped_jobs": [],
    "warnings": []
  }
}
```

The `summary` object is a compact manifest convenience extracted from existing `result.json` when available. It should not invent content and should be omitted or partial when fields are missing.

Paths inside `source_artifacts` are relative to the run directory. Paths inside `collected_artifacts` are relative to the collection directory.

### Markdown Index

`FARM_COLLECTION.md` should be optimized for quick inspection:

```markdown
# Farm Collection dogfood-lite

Run: farm-run-...
Mode: summarize
Model: qwen3.5:4b
Items collected: 4

## Items

| Item | Job | Input | Status | Markdown | JSON |
| --- | --- | --- | --- | --- | --- |
| item-0001 | job-0001 | articles/005-karpathy-llm-wiki-starter-vault.txt | complete | items/item-0001-karpathy-llm-wiki-starter-vault.md | items/item-0001-karpathy-llm-wiki-starter-vault.json |

## Summaries

### item-0001 - 005-karpathy-llm-wiki-starter-vault.txt

Title: LLM Wiki Starter Vault
Confidence: medium

Compact abstract when available.
```

Markdown diagnostics should appear only when warnings or skipped jobs exist.

### Job Selection

The collector should:

- read `farm-status.json` as the run index
- preserve farm-status job order
- collect jobs with status `complete` or `complete_with_warnings`
- skip failed, queued, running, or unknown-status jobs with diagnostics
- skip jobs whose declared `result.md` or `result.json` artifacts are missing or unreadable
- still collect whichever result artifact exists if one of Markdown or JSON is available
- record malformed JSON in diagnostics rather than crashing the whole collection

If no items can be collected, the command should still write a manifest and Markdown index with diagnostics, then exit successfully unless the run reference itself is invalid.

### Artifact Semantics

Collected `result.md` and `result.json` files should be copies of existing job artifacts. The collector should not mutate the job result payloads, rewrite summaries, or normalize model output.

The manifest may parse `result.json` only to extract compact metadata for indexing:

- title
- abstract
- confidence
- warnings when present

The collector should avoid copying:

- source input files
- `raw-response.txt`
- chunk source text
- chunk result artifacts
- logs

Those richer export modes are deferred until there is a clear user need and privacy posture.

## Acceptance Criteria

- `python sift.py farm collect <run-ref>` creates a collection from an existing farm run.
- `<run-ref>` accepts both run directory paths and known run IDs.
- The default output is under `.run/farm_collections/`.
- `--output` overrides the parent output directory.
- `--label` controls the collection folder name and defaults to the run ID.
- The command writes `farm-collection.json`.
- The command writes `FARM_COLLECTION.md`.
- The command writes copied per-job result artifacts under `items/`.
- Copied item filenames are deterministic, safe, sequence-prefixed, and collision-resistant.
- The manifest includes schema version, created timestamp, label, run ID, run path, mode, agent, model, counts, artifacts, items, and diagnostics.
- A tracked JSON schema validates `farm-collection.json`.
- The schema is registered in `schemas/index.json`.
- `farm schema validate <collection-json>` auto-detects the collection schema.
- Jobs are processed in farm-status order.
- Complete and warning-complete jobs are collected.
- Failed, queued, running, unknown-status, missing-result, and malformed-result jobs are skipped with diagnostics.
- A run with no collectable jobs still produces empty collection artifacts with diagnostics.
- The command does not call a model.
- The command does not copy source input files or raw model responses by default.
- Existing `farm run`, `farm list`, `farm status`, `farm snippets pack`, `farm synthesis bundle`, dogfood, timing, and schema validation behavior remain unchanged.
- Docs explain when to use `farm collect` instead of snippet packs or synthesis bundles.
- BL-0010 is marked planned/implemented as appropriate in the same PR that advances lifecycle state.
- Model-free tests cover CLI parsing, run-ref resolution, artifact copying, safe filenames, manifest shape, Markdown rendering, missing artifacts, malformed JSON, skipped statuses, empty collections, schema validation, and schema auto-detection.

## Test Plan

Automated:

- unit tests for building a collection from fixture `farm-status.json` and job result artifacts
- unit tests for path and run-ID resolution
- unit tests for safe item filename generation and collision handling
- unit tests for copying Markdown-only, JSON-only, and both-artifact jobs
- unit tests for skipped failed/running/queued jobs
- unit tests for missing and malformed result artifacts
- unit tests for empty collection diagnostics
- unit tests for Markdown index rendering
- schema validation tests for representative collection JSON
- schema auto-detection tests through `farm schema validate`
- CLI parser tests for `farm collect`
- full model-free test suite

Verification:

```powershell
python -m src.qwen_spec_guard
python -m unittest discover -s tests -p "test_*.py"
python -m compileall sift.py examples src tests
git diff --check
```

Dogfood:

Use a new ignored folder only if implementation needs a manual smoke:

```text
.run/dogfood_0024/
```

Suggested smoke:

```powershell
python sift.py farm collect <known-lite-run-id-or-path> --output .run/dogfood_0024/farm_collections --label dogfood-lite-0024
python sift.py farm schema validate .run/dogfood_0024/farm_collections/dogfood-lite-0024/farm-collection.json
```

Inspect:

- whether a primary AI can find every collected result without opening `jobs/job-*`
- whether the Markdown index is enough for quick human review
- whether diagnostics are clear for partial or warning runs
- whether no source text or raw responses are copied unexpectedly

## Deferred To Roadmap

- Zip/archive export for farm collections.
- Explicit opt-in collection of raw model responses, logs, source input files, or chunk artifacts.
- Collection filters and templates for choosing artifact types or fields.
- Cross-run collections.
