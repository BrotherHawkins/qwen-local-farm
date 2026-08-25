# 0016 Implement Artifact Schemas And Validation

Status: Implemented
Spec: [0016 Add Artifact Schemas And Validation](../changes/0016-add-artifact-schemas-and-validation.md)

## Plan

Implement the first schema contract layer for key farm JSON outputs:

1. Add tracked schema files under `schemas/`.
   - create `schemas/README.md`
   - create `schemas/index.json`
   - create `schemas/farm-status.schema.json`
   - create `schemas/farm-job-result.schema.json`
   - create `schemas/farm-status-overview.schema.json`
   - create `schemas/farm-status-run.schema.json`
   - create `schemas/farm-doctor.schema.json`
2. Keep schemas JSON Schema-compatible but intentionally modest.
   - include `$schema`, `$id`, `title`, `description`, `type`, and required top-level fields
   - target current emitted schema versions: persisted farm artifacts use `"0.1"` and newer CLI/report envelopes use `1`
   - use enums for stable status/scope fields
   - allow optional/additive fields where current artifacts vary by mode, failure state, or feature
   - avoid overfitting to one local dogfood run
3. Add a dependency-free validation helper.
   - create a small repo-native helper that supports only the schema features this repo uses first
   - validate object/array/string/number/integer/boolean/null types
   - validate required fields
   - validate enum and const constraints
   - validate nested object properties and array item shapes
   - return useful path-aware error messages
   - avoid adding a required `jsonschema` package dependency
4. Add representative model-free fixtures/tests.
   - validate a generated/current-shaped `farm-status.json`
   - validate a generated/current-shaped job `result.json`
   - validate a `farm status --json` overview envelope
   - validate a `farm status <run-id> --json` run envelope
   - validate a `farm doctor --json` report generated with fake probes
   - include at least one malformed artifact negative test
   - test `schemas/index.json` references existing schema files
   - test all schema files are parseable JSON and include required metadata
5. Preserve runtime behavior.
   - do not change `farm run` output shapes except if a real inconsistency is found
   - do not validate every live run by default
   - do not add a public validation CLI in this slice unless implementation shows it is nearly free
   - do not require Ollama, model calls, tokenizer downloads, or network access
6. Update docs and lifecycle records.
   - README: point power users and primary AIs to `schemas/`
   - `docs/ai-usage.md`: explain schema use for artifact inspection
   - `docs/roadmap.md`: mark the first schema folder as implemented when code lands
   - mark BL-0007 planned/implemented as lifecycle progresses
   - keep BL-0067 through BL-0071 open as follow-ups
   - update spec/dashboard status to implemented in the implementation PR

## Schema Surfaces

Treat these as separate contracts:

- `farm-status.schema.json`: persisted run status file.
- `farm-job-result.schema.json`: persisted per-job result file.
- `farm-status-overview.schema.json`: `python sift.py farm status --json`.
- `farm-status-run.schema.json`: `python sift.py farm status <run-id> --json`.
- `farm-doctor.schema.json`: `python sift.py farm doctor --json` and `.run/reports/setup-doctor.json`.

Do not collapse persisted artifacts and command envelopes into one schema just because they share fields.

## Validation Helper Scope

The helper should support the subset we need now:

- `type`
- `required`
- `properties`
- `items`
- `enum`
- `const`
- nullable types expressed as `["string", "null"]` or similar
- path-aware error reporting such as `$.jobs[0].job_id: missing required field`

Defer advanced JSON Schema features until needed:

- `$ref`
- `oneOf` / `anyOf` / `allOf`
- `patternProperties`
- numeric ranges
- string formats
- additional-properties strictness

This keeps the first pass understandable and avoids smuggling in a schema engine project.

## Non-Goals

This implementation will not add schema-driven prompting, model JSON grammar mode, JSON repair changes, validation on every farm run, package schemas for snippet/synthesis/dogfood artifacts, checked-in artifact fixture migrations, or strict unknown-field rejection.

## Verification

Implemented with:

- tracked schema contracts under `schemas/`
- `schemas/index.json`
- persisted run status schema
- persisted job result schema
- status overview CLI envelope schema
- status run CLI envelope schema
- doctor report schema
- dependency-free validation helper in `src/qwen_farm_schema.py`
- model-free tests for schema metadata, index integrity, positive validation, and negative validation
- README, AI usage, and roadmap docs

Checks:

```powershell
python -m unittest tests.test_qwen_farm_schema tests.test_qwen_farm tests.test_qwen_farm_status tests.test_qwen_farm_doctor
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Optional local smoke:

```powershell
python sift.py farm status --json
python sift.py farm doctor --json
```

If a private validation helper is easy to expose through tests, use recent local outputs only as manual examples; do not rely on `.run/` artifacts for CI.

## Implementation Checklist

- [x] Add `schemas/README.md`.
- [x] Add `schemas/index.json`.
- [x] Add persisted run status schema.
- [x] Add persisted job result schema.
- [x] Add status overview CLI schema.
- [x] Add status run CLI schema.
- [x] Add doctor report schema.
- [x] Add dependency-free schema validation helper or test utility.
- [x] Add schema metadata/index tests.
- [x] Add positive validation tests for all five contract surfaces.
- [x] Add at least one negative validation test.
- [x] Update README and AI usage docs.
- [x] Update roadmap/backlog/dashboard lifecycle records.
- [x] Run model-free verification.
