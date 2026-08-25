# 0018 Add Post-Run Package Schemas

Status: Implemented
Type: Add

## WHY

The farm now has tracked schemas for core run/job/status/doctor artifacts and a public `farm schema validate` command. The next most important JSON surfaces are the post-run packages used for performance inspection, evidence packaging, synthesis handoff, and dogfood comparison.

Those artifacts are increasingly likely to be consumed by scripts, dashboards, and primary AIs. They should have tracked schema contracts and validation coverage before we add more package types or build richer downstream workflows on top of them.

This change favors:

- validating the artifacts that downstream workflows actually consume
- keeping schemas model-free and CI-friendly
- extending the public validator rather than adding a separate validation path
- documenting which post-run package schemas are available
- preserving existing package output shapes unless schema work exposes a real bug
- leaving stricter compatibility and migration policy as follow-up work

## Scope

This change adds tracked schemas for current post-run package artifacts:

- `timing-summary.json`
- snippet pack JSON from `python sift.py farm snippets pack`
- synthesis bundle JSON from `python sift.py farm synthesis bundle`
- dogfood quality record JSON from `python sift.py farm dogfood record`
- dogfood comparison JSON from `python sift.py farm dogfood compare`

This change also:

- adds these schemas to `schemas/index.json`
- documents them in `schemas/README.md`
- updates `farm schema validate` auto-detection for the new artifact surfaces
- adds model-free validation tests for representative current-shaped package artifacts
- updates README and AI usage docs with the expanded validation coverage
- updates BL-0067 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- new post-run package commands
- changes to package output layout or filenames unless a real inconsistency is found
- strict unknown-field rejection
- schema migration tools
- generated schema docs
- directory-wide validation
- validation during every package command by default
- schemas for Markdown outputs
- exact downstream tokenizer adapters
- model calls, Ollama calls, tokenizer downloads, or network access

## Behavior

### Schema Files

The first implementation should add:

```text
schemas/farm-timing-summary.schema.json
schemas/farm-snippet-pack.schema.json
schemas/farm-synthesis-bundle.schema.json
schemas/farm-dogfood-record.schema.json
schemas/farm-dogfood-comparison.schema.json
```

Exact filenames can be refined during planning, but they should be obvious and parallel the existing schema naming style.

Each schema should include:

- `$schema`
- `$id`
- `title`
- `description`
- `type`
- required top-level fields
- enum constraints where current values are stable
- permissive handling for optional/additive nested fields

Schemas should target the current package artifact versions. Most package artifacts currently use `schema_version: 1`; `timing-summary.json` currently inherits the run status schema version, usually `"0.1"`.

### Contract Surfaces

Treat each post-run package artifact as a separate contract:

1. **Timing summary**: performance summary written beside a farm run as `timing-summary.json`.
2. **Snippet pack**: selected verified source evidence package written by `farm snippets pack`.
3. **Synthesis bundle**: summary-plus-snippet package written by `farm synthesis bundle`, including budget metadata.
4. **Dogfood quality record**: compact quality/timing record written by `farm dogfood record`.
5. **Dogfood comparison**: baseline/candidate comparison written by `farm dogfood compare`.

Do not collapse these into a single generic package schema. They have different consumers and different stability needs.

### Validator Integration

`farm schema validate <json-path>` should auto-detect the new package schemas from stable top-level fields.

Suggested detection signals:

- timing summary: `run_id`, `aggregate_by_call_kind`, `slowest_jobs`, `slowest_calls`
- snippet pack: `limits.source`, `snippets`, and `diagnostics`
- synthesis bundle: `items`, `budget`, `limits.snippet_source`
- dogfood record: `recorded_at`, `totals`, `quality`, and per-job quality records
- dogfood comparison: `compared_at`, `baseline`, `candidate`, comparison `duration_ms`, and comparison `jobs`

If a shape is ambiguous, validation should keep the existing behavior and ask the caller to pass `--schema`.

Explicit `--schema <schema-path-or-id>` should work for every new schema.

### Documentation

Docs should explain that schemas now cover:

- core run/job/status/doctor artifacts
- post-run timing, snippet, synthesis, and dogfood artifacts

Docs should also recommend `farm schema validate` before feeding post-run package JSON into scripts, dashboards, or primary-AI workflows.

## Acceptance Criteria

- A tracked schema exists for `timing-summary.json`.
- A tracked schema exists for snippet pack JSON.
- A tracked schema exists for synthesis bundle JSON, including budget metadata.
- A tracked schema exists for dogfood quality record JSON.
- A tracked schema exists for dogfood comparison JSON.
- `schemas/index.json` lists all new schemas with IDs, paths, surfaces, and current status.
- `schemas/README.md` documents all new package schemas.
- New schemas are valid JSON and include `$schema`, `$id`, title, description, type, and required top-level fields.
- New schemas preserve current artifact version expectations for each package surface.
- Schemas permit known optional/additive nested fields without requiring unrelated package features.
- `farm schema validate <json-path>` auto-detects each new package artifact type.
- `farm schema validate <json-path> --schema <schema-path-or-id>` works for each new schema.
- Model-free tests validate representative current-shaped artifacts against each new schema.
- Model-free tests cover auto-detection for each new package artifact type.
- At least one negative validation test proves malformed package artifacts fail with path-aware errors.
- Current package commands continue to produce the same JSON output shape except for any intentional bug fix discovered during schema work.
- Existing core schema validation behavior remains unchanged.
- No tests require Ollama, installed local models, tokenizer downloads, model calls, or network access.
- README and AI usage docs mention expanded schema validation coverage for post-run packages.
- BL-0067 is marked planned/implemented as appropriate.
- Deferred schema follow-ups remain backlogged.

## Test Plan

Automated:

- tests that each new schema file is valid JSON with required metadata
- tests that `schemas/index.json` points to each new schema file
- validation tests for representative `timing-summary.json`
- validation tests for representative snippet pack JSON
- validation tests for representative synthesis bundle JSON with budget metadata
- validation tests for representative dogfood quality record JSON
- validation tests for representative dogfood comparison JSON
- auto-detection tests for all five new package schema surfaces
- explicit schema path/ID validation tests for at least one new package schema
- negative validation test for a malformed package artifact
- regression tests for existing core schema validation
- full model-free test suite

Verification:

```powershell
python -m unittest tests.test_sift_farm_schema tests.test_sift_farm_snippet_packs tests.test_sift_farm_synthesis_bundles tests.test_sift_farm_dogfood
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Manual smoke with existing local artifacts when available:

```powershell
python sift.py farm schema validate <run-dir>/timing-summary.json
python sift.py farm snippets pack <run-ref> --output .run/schema-smoke/snippet-packs --label schema-smoke
python sift.py farm synthesis bundle <run-ref> --output .run/schema-smoke/synthesis-bundles --label schema-smoke
python sift.py farm dogfood record <run-ref> --output .run/schema-smoke/dogfood-runs --label schema-smoke
python sift.py farm schema validate .run/schema-smoke/snippet-packs/schema-smoke.json
python sift.py farm schema validate .run/schema-smoke/synthesis-bundles/schema-smoke.json
python sift.py farm schema validate .run/schema-smoke/dogfood-runs/schema-smoke.json
```

If two dogfood records are available, also smoke:

```powershell
python sift.py farm dogfood compare <baseline-record.json> <candidate-record.json> --output .run/schema-smoke/dogfood-comparisons
python sift.py farm schema validate <comparison.json>
```

## Deferred To Roadmap

- Strict schema mode that rejects unknown/additional fields.
- Generated schema documentation.
- Schema version migration guidance.
- Directory-wide validation for complete run folders and package output folders.
- CI fixture validation gates for checked-in sample artifacts.
- Schemas for future package types and future non-summarize modes.
