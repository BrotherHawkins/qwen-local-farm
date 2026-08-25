# 0018 Implement Post-Run Package Schemas

Status: Implemented
Spec: [0018 Add Post-Run Package Schemas](../changes/0018-add-post-run-package-schemas.md)

## Plan

Implement tracked schema contracts and validator support for current post-run package artifacts:

1. Add package schema files.
   - `schemas/farm-timing-summary.schema.json`
   - `schemas/farm-snippet-pack.schema.json`
   - `schemas/farm-synthesis-bundle.schema.json`
   - `schemas/farm-dogfood-record.schema.json`
   - `schemas/farm-dogfood-comparison.schema.json`
   - keep schemas JSON Schema-compatible and permissive around optional/additive nested metadata
   - target current emitted versions: `timing-summary.json` inherits persisted run schema version `"0.1"`; package artifacts use `1`
2. Update schema discovery docs.
   - add all new schemas to `schemas/index.json`
   - document them in `schemas/README.md`
   - update README and AI usage docs to mention expanded package validation coverage
3. Extend schema auto-detection in `src/sift_farm_schema.py`.
   - detect timing summaries from `aggregate_by_call_kind`, `slowest_jobs`, and `slowest_calls`
   - detect snippet packs from `limits.source`, `snippets`, and `diagnostics`
   - detect synthesis bundles from `items`, `budget`, and `limits.snippet_source`
   - detect dogfood records from `recorded_at`, `totals`, `quality`, and job records
   - detect dogfood comparisons from `compared_at`, `baseline`, `candidate`, comparison `duration_ms`, and comparison `jobs`
   - preserve existing ambiguity/unsupported behavior and explicit `--schema` support
4. Add model-free tests.
   - schema metadata/index tests should cover the new files automatically
   - generated/current-shaped timing summary validation
   - generated/current-shaped snippet pack validation
   - generated/current-shaped synthesis bundle validation including budget metadata
   - generated/current-shaped dogfood quality record validation
   - generated/current-shaped dogfood comparison validation
   - auto-detection tests for all five new package schemas
   - explicit schema path/ID validation for at least one package schema
   - negative malformed package validation test with path-aware errors
   - regression coverage for existing core schema detection
5. Preserve runtime behavior.
   - do not change package command output shapes unless schema work reveals a real bug
   - do not add validation during every package command
   - do not add directory-wide validation
   - do not require Ollama, model calls, tokenizer downloads, or network access
6. Update lifecycle records.
   - mark BL-0067 implemented in the implementation PR
   - keep BL-0069, BL-0070, BL-0071, and related follow-ups open
   - update spec/dashboard status to implemented in the implementation PR

## Schema Surfaces

Treat these as separate contracts:

- `farm-timing-summary.schema.json`: `timing-summary.json`
- `farm-snippet-pack.schema.json`: JSON from `farm snippets pack`
- `farm-synthesis-bundle.schema.json`: JSON from `farm synthesis bundle`
- `farm-dogfood-record.schema.json`: JSON from `farm dogfood record`
- `farm-dogfood-comparison.schema.json`: JSON from `farm dogfood compare`

Do not collapse package artifacts into one generic schema. Each package serves a different downstream workflow.

## Validation Helper Scope

Reuse the existing dependency-free validator from 0016/0017. Do not add advanced JSON Schema features for this slice. Shape the schemas around supported features:

- `type`
- `required`
- `properties`
- `items`
- `enum`
- `const`
- nullable type lists

Keep nested package data reasonably shaped, but avoid strict unknown-field rejection.

## Non-Goals

This implementation will not add new package commands, schema migrations, generated schema docs, strict schema mode, validation-on-write, directory-wide validation, exact downstream tokenizer adapters, model calls, Ollama calls, tokenizer downloads, or network access.

## Verification

Completed checks:

```powershell
python -m unittest tests.test_sift_farm_schema tests.test_sift_farm_snippet_packs tests.test_sift_farm_synthesis_bundles tests.test_sift_farm_dogfood
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Completed manual smoke with an existing local dogfood run:

```powershell
python sift.py farm schema validate .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf/timing-summary.json
python sift.py farm snippets pack .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/schema-smoke/snippet-packs --label schema-smoke
python sift.py farm synthesis bundle .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/schema-smoke/synthesis-bundles --label schema-smoke
python sift.py farm dogfood record .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/schema-smoke/dogfood-runs --label schema-smoke-baseline
python sift.py farm dogfood record .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/schema-smoke/dogfood-runs --label schema-smoke-candidate
python sift.py farm schema validate .run/schema-smoke/snippet-packs/schema-smoke.json
python sift.py farm schema validate .run/schema-smoke/synthesis-bundles/schema-smoke.json
python sift.py farm schema validate .run/schema-smoke/dogfood-runs/schema-smoke-baseline.json
python sift.py farm dogfood compare .run/schema-smoke/dogfood-runs/schema-smoke-baseline.json .run/schema-smoke/dogfood-runs/schema-smoke-candidate.json --output .run/schema-smoke/dogfood-comparisons
python sift.py farm schema validate .run/schema-smoke/dogfood-comparisons/schema-smoke-baseline--schema-smoke-candidate.json
```

## Implementation Checklist

- [x] Add timing summary schema.
- [x] Add snippet pack schema.
- [x] Add synthesis bundle schema with budget metadata.
- [x] Add dogfood quality record schema.
- [x] Add dogfood comparison schema.
- [x] Update `schemas/index.json`.
- [x] Update schema README and user docs.
- [x] Extend validator auto-detection for package artifacts.
- [x] Add positive validation tests for all five package schemas.
- [x] Add auto-detection tests for all five package schemas.
- [x] Add explicit path/ID validation coverage for a package schema.
- [x] Add negative malformed package validation coverage.
- [x] Update lifecycle records.
- [x] Run model-free verification.
