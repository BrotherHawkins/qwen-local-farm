# 0036 Add Extract Mode

Status: Implemented
Type: Add

## Summary

Add a first-class, fast, JSON-first `extract` farm mode that scans files and chunks for source-grounded evidence, entities, links, and work items, then emits compact schema-validated per-job and run-level artifacts for frontier-model handoff.

## Motivation

`summarize` is useful when a caller wants local workers to compress source material. The next frontier-handoff workflow is different: a primary AI often needs compact harvested material, not prose synthesis. It needs claims, examples, entities, links, tasks, decisions, risks, and source pointers that can be inspected later.

`extract` should feel like fast scanning. The local model should harvest candidates with minimal thinking and minimal output, while Python handles parsing, snippet verification, deterministic dedupe, caps, ranking, schema validation, and aggregation.

## Goals

- Add `python sift.py farm run <folder> --mode extract`.
- Default extract preset to `research`.
- Support structured presets:
  - `evidence`: `claim`, `fact`, `example`, `quote`, `question`, `tension`
  - `entities`: `entity`, `link`
  - `work`: `task`, `decision`, `risk`, `requirement`, `blocker`, `follow_up`
  - `research`: evidence plus entities
- Add optional `--extract-focus` for brief extraction steering.
- Keep `--instructions` out of extract mode for v1.
- Use a compact tagged-line local worker protocol rather than local-model strict JSON.
- Produce strict final JSON artifacts.
- Include type-aware verified source snippets and original-file character offsets where useful.
- Support automatic chunking from day one with extract-specific defaults and the existing chunk controls.
- Use deterministic Python dedupe and ranking, including merged `sources[]`.
- Save raw tagged model output per file or chunk for debugging.
- Produce run-level `extract-results.json` and `EXTRACT_RESULTS.md` artifacts.
- Keep `farm collect` compatible with extract job artifacts.
- Keep GitHub CI/model-free assumptions intact.

## Non-Goals

- No custom user-defined extraction schemas in v1.
- No model-assisted dedupe or ranking in v1.
- No embeddings, semantic clustering, or retrieval dependency in v1.
- No first-class extract package helper beyond the automatic run-level aggregate.
- No automatic frontier-model calls.
- No requirement that the model fill quotas. Zero items can be correct.

## CLI

Default research extraction:

```powershell
python sift.py farm run articles --mode extract
```

Focused research extraction:

```powershell
python sift.py farm run articles --mode extract --extract-preset research --extract-focus "Capture local AI models, tools, benchmarks, and setup pitfalls."
```

Work extraction:

```powershell
python sift.py farm run notes --mode extract --extract-preset work
```

`--extract-focus` is a brief steering hint, not a schema language. It may bias item selection and entity attributes, but it must not create arbitrary top-level result fields.

`--instructions` with `--mode extract` should fail clearly and point to `--extract-focus`.

## Runtime Config

Resolved farm config should include an `extract` namespace:

```json
{
  "extract": {
    "preset": "research",
    "focus": null,
    "chunk_strategy": "character",
    "chunk_chars": 6000,
    "chunk_tokens": null,
    "token_safety_margin": 0.1,
    "preserve_heading_ancestry": true,
    "chunk_overlap_chars": 0,
    "chunk_overlap_tokens": 0,
    "max_items_per_file": 40,
    "max_items_per_chunk": 10,
    "snippet_max_chars": 240
  }
}
```

Power users can tune extract separately from summarize because extract is speed-biased and has different output caps.

## Output Contract

Each completed job writes the normal farm artifacts:

```text
jobs/job-0001/result.json
jobs/job-0001/result.md
jobs/job-0001/raw-response.txt
```

Chunked extract jobs additionally write per-chunk raw and result artifacts under the job directory.

Each extract run writes:

```text
extract-results.json
EXTRACT_RESULTS.md
```

The run-level aggregate includes completed jobs, warnings, partial coverage, and useful failure data for failed jobs.

## Extract Item Shape

Final extract items should be compact and source-grounded:

```json
{
  "id": "claim-001",
  "type": "claim",
  "text": "Local models are useful preprocessing workers before frontier synthesis.",
  "attributes": {},
  "rank_score": 0.82,
  "source_support": "snippet_verified",
  "sources": [
    {
      "file": "articles/005-karpathy-llm-wiki-starter-vault.txt",
      "chunk_id": "chunk-0001",
      "snippet": "local models can do preprocessing work",
      "source_support": "snippet_verified",
      "char_start": 184,
      "char_end": 221
    }
  ]
}
```

`entity` items may include `entity_type`. `link` items may include `url`.

`attributes` is optional, bounded, and shallow. It may contain scalar strings or short arrays of strings, but not nested objects.

## Sample JSON

Entities preset job result excerpt:

```json
{
  "schema_version": 1,
  "job_id": "job-0001",
  "mode": "extract",
  "status": "complete",
  "structured_valid": true,
  "input": { "path": "notes/market-map.txt" },
  "result": {
    "preset": "entities",
    "focus": null,
    "counts": { "items": 3, "by_type": { "entity": 3 } },
    "items": [
      {
        "id": "entity-001",
        "type": "entity",
        "text": "Mira Chen",
        "entity_type": "person",
        "attributes": { "role": "research lead" },
        "rank_score": 0.92,
        "source_support": "snippet_verified",
        "sources": [
          {
            "file": "notes/market-map.txt",
            "snippet": "Research lead Mira Chen argued",
            "char_start": 114,
            "char_end": 145,
            "source_support": "snippet_verified"
          }
        ]
      },
      {
        "id": "entity-002",
        "type": "entity",
        "text": "Jon Patel",
        "entity_type": "person",
        "attributes": { "role": "buyer" },
        "rank_score": 0.76,
        "source_support": "snippet_verified",
        "sources": [
          {
            "file": "notes/market-map.txt",
            "snippet": "Jon Patel said procurement",
            "char_start": 392,
            "char_end": 419,
            "source_support": "snippet_verified"
          }
        ]
      },
      {
        "id": "entity-003",
        "type": "entity",
        "text": "Asha Morgan",
        "entity_type": "person",
        "attributes": { "role": "operator" },
        "rank_score": 0.68,
        "source_support": "snippet_verified",
        "sources": [
          {
            "file": "notes/market-map.txt",
            "snippet": "operator Asha Morgan tracks",
            "char_start": 812,
            "char_end": 840,
            "source_support": "snippet_verified"
          }
        ]
      }
    ]
  },
  "warnings": []
}
```

Work preset job result excerpt:

```json
{
  "schema_version": 1,
  "job_id": "job-0002",
  "mode": "extract",
  "status": "complete",
  "structured_valid": true,
  "input": { "path": "meetings/planning.txt" },
  "result": {
    "preset": "work",
    "focus": "Capture implementation follow-ups.",
    "counts": { "items": 2, "by_type": { "decision": 1, "task": 1 } },
    "items": [
      {
        "id": "decision-001",
        "type": "decision",
        "text": "Use tokenizer-aware chunking by default for large Markdown inputs.",
        "attributes": { "owner": "team" },
        "rank_score": 0.88,
        "source_support": "snippet_verified",
        "sources": [
          {
            "file": "meetings/planning.txt",
            "snippet": "Decision: tokenizer-aware chunking becomes the default",
            "char_start": 44,
            "char_end": 99,
            "source_support": "snippet_verified"
          }
        ]
      },
      {
        "id": "task-001",
        "type": "task",
        "text": "Add runtime timing fields to dogfood comparison records.",
        "attributes": { "owner": "Chris" },
        "rank_score": 0.74,
        "source_support": "snippet_verified",
        "sources": [
          {
            "file": "meetings/planning.txt",
            "snippet": "Chris will add timing fields",
            "char_start": 151,
            "char_end": 180,
            "source_support": "snippet_verified"
          }
        ]
      }
    ]
  },
  "warnings": []
}
```

Run-level aggregate example:

```json
{
  "schema_version": 1,
  "run_id": "20260825-141233-9f3a2b",
  "mode": "extract",
  "preset": "research",
  "focus": null,
  "status": "partial",
  "coverage": {
    "status": "partial",
    "total_jobs": 3,
    "completed_jobs": 2,
    "failed_jobs": 1,
    "skipped_files": 0
  },
  "counts": {
    "items": 17,
    "by_type": { "claim": 8, "entity": 6, "link": 3 }
  },
  "items": [
    {
      "id": "claim-001",
      "type": "claim",
      "text": "Local workers can reduce frontier-model context load before synthesis.",
      "attributes": {},
      "rank_score": 0.84,
      "source_support": "snippet_verified",
      "sources": [
        {
          "file": "articles/005-karpathy-llm-wiki-starter-vault.txt",
          "snippet": "smaller local models can preprocess",
          "char_start": 203,
          "char_end": 240,
          "source_support": "snippet_verified"
        }
      ]
    }
  ],
  "failures": [
    {
      "job_id": "job-0003",
      "file": "articles/009-long-article.txt",
      "failure_category": "worker_error",
      "retry_recommended": true,
      "message": "Worker command exited before producing tagged output."
    }
  ],
  "artifacts": {
    "markdown": "EXTRACT_RESULTS.md",
    "json": "extract-results.json"
  },
  "diagnostics": {
    "warnings": [],
    "dedupe": { "candidate_items": 23, "selected_items": 17 }
  }
}
```

## Snippet And Offset Policy

Source snippets are type-aware:

- Strongly useful for `claim`, `fact`, `example`, `quote`, `question`, `tension`, `decision`, `risk`, `requirement`, and `blocker`.
- Useful but optional for `task` and `follow_up`.
- Optional and sparse for `entity` and `link`.

Verified snippets should include `char_start` and `char_end` relative to the original source file as read by Sift. Chunk-local offsets are not the primary contract.

## Chunking And Dedupe

`extract` is chunk-safe. It should auto-chunk large inputs using the existing chunk strategy controls with extract-specific defaults.

Chunked extract should:

- map each chunk with one compact local model call
- avoid a model reduce pass in v1
- parse valid tagged lines even when some lines are malformed
- merge duplicate items in Python
- preserve multiple source references in `sources[]`
- cap by file and chunk ceilings without treating ceilings as targets

Dedupe should be deterministic and conservative. Entities and links can merge more aggressively across files by normalized name or URL. Evidence and work items should merge only exact-ish normalized duplicates.

## Failure And Partial Coverage

Per-job failures use existing farm failure guidance.

Run-level extract aggregates should still be written for partial runs. They must include coverage metadata and failure summaries so a primary AI can decide whether the partial handoff is usable.

## Acceptance Criteria

- `farm run --mode extract` is accepted by the CLI and defaults to `--extract-preset research`.
- `--extract-preset evidence|entities|work|research` controls the allowed item families.
- `--extract-focus` is accepted for extract mode and stored in request/runtime artifacts.
- `--instructions` with extract mode fails with a helpful message.
- Extract uses compact tagged-line model output and Python parses it into strict JSON.
- Malformed tagged lines are counted and sampled as warnings while valid lines survive.
- Final extract items include stable IDs, controlled item types, deterministic ranking metadata, and `sources[]`.
- Verified snippets include original-file `char_start` and `char_end` when found.
- Chunked extract jobs map chunks and deterministically merge/cap extracted items without a model reduce call.
- Run-level `extract-results.json` and `EXTRACT_RESULTS.md` are written for extract runs, including partial runs.
- A strict `farm-extract-results.schema.json` validates the run-level aggregate.
- Validator auto-detection recognizes extract aggregate artifacts.
- `farm collect` can collect extract job `result.json` and `result.md` artifacts.
- README, AI usage docs, and repo skills document extract as a normal mode.
- Tests remain model-free unless explicitly marked as runtime dogfood.

## Tests

- Model-free parser tests for tagged-line extraction, malformed-line warnings, attributes, and item taxonomy.
- Model-free snippet verification tests for original-file character offsets.
- Model-free dedupe tests for merged `sources[]`.
- Model-free run tests for extract single-pass and chunked jobs.
- Schema tests for generated extract job results and run-level `extract-results.json`.
- CLI parser tests for `--mode extract`, `--extract-preset`, `--extract-focus`, and `--instructions` rejection.
- A small runtime dogfood may run against crafted fake inputs and a few dogfood-lite articles outside CI.

## Deferred To Backlog

- Model-assisted extract dedupe and ranking.
- Custom user-defined extraction schemas.
- First-class extract package helper if the automatic aggregate is not enough.
- Broader dogfood quality records for extract runs.
- Semantic clustering or embedding-assisted extract grouping.
- Quote/citation export formats that use source offsets.
