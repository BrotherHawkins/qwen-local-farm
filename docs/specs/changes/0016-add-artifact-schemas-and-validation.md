# 0016 Add Artifact Schemas And Validation

Status: Implemented
Type: Add

## WHY

The farm now emits several JSON artifacts that primary AIs and scripts rely on: `farm-status.json`, per-job `result.json`, `farm status --json` envelopes, and `setup-doctor.json`. Those artifacts are useful, but their contracts currently live mostly in code, tests, README examples, and prior specs. That makes it too easy for a later change to drift a field shape without noticing.

The farm should carry explicit schema files for its most important machine-readable artifacts and model-free validation coverage that proves current outputs still satisfy those contracts.

This change favors:

- stable machine-readable contracts over prose-only examples
- JSON Schema-compatible files under version control
- model-free validation and tests
- additive schemas that tolerate known optional fields
- clear separation between persisted run artifacts and CLI JSON envelopes
- preserving existing artifact shapes unless a mismatch exposes a real bug

## Scope

This change adds the first schema layer for farm artifacts:

- add a tracked `schemas/` folder
- add a small schema index/README that explains available schemas and compatibility expectations
- add JSON Schema-compatible contracts for:
  - persisted run status: `farm-status.json`
  - persisted job result: `jobs/job-*/result.json`
  - `farm status --json` overview envelope
  - `farm status <run-id> --json` single-run envelope
  - doctor report: `setup-doctor.json`
- identify shared field patterns such as schema version, timestamps, artifact paths, timing records, warnings, and counts
- include summarize-result payload fields that are already produced today
- keep room for optional fields such as chunking, snippets, timing, tokenizer diagnostics, and future additive metadata
- add model-free validation helpers or test utilities that load schemas and validate representative generated artifacts
- update docs so primary AIs and power users know where schema contracts live
- update BL-0007 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- schema-driven model prompting
- LLM JSON grammar mode
- JSON repair behavior changes
- strict validation during every `farm run`
- a new external runtime dependency solely for validation
- a formal compatibility guarantee for every `.run/` artifact
- schemas for every post-run helper artifact
- schemas for timing summaries, snippet packs, synthesis bundles, or dogfood history
- automatic migration of old local `.run/` artifacts
- network calls, model calls, or Ollama-dependent tests

## Behavior

### Schema Files

The first implementation should add schema files under a top-level tracked folder:

```text
schemas/
  README.md
  index.json
  farm-status.schema.json
  farm-job-result.schema.json
  farm-status-overview.schema.json
  farm-status-run.schema.json
  farm-doctor.schema.json
```

Exact filenames can be refined during planning, but the folder should be obvious to a primary AI or script scanning the repo.

Each schema should include:

- `$schema`
- `$id`
- `title`
- `description`
- `type`
- required top-level fields
- enum constraints for stable status/scope fields where practical
- permissive handling for optional/additive fields that already vary by mode or feature

Schemas should target the artifact versions currently emitted by each surface. Persisted farm run/job artifacts currently use `schema_version: "0.1"`, while newer CLI/report envelopes such as `farm status --json` and `farm doctor --json` currently use `schema_version: 1`.

### Contract Boundaries

The first schema pass should distinguish these contract surfaces:

1. **Persisted run status**: the contents of a run's `farm-status.json`.
2. **Persisted job result**: the contents of a job's `result.json`, including the generic job envelope and summarize payload.
3. **Status overview command output**: the envelope printed by `python sift.py farm status --json`.
4. **Status run command output**: the envelope printed by `python sift.py farm status <run-id> --json`.
5. **Doctor report output**: the contents of `.run/reports/setup-doctor.json` and `python sift.py farm doctor --json`.

Persisted artifacts and CLI envelopes should not be collapsed into one schema just because they share fields. The schema names should tell callers which command or file they validate.

### Validation

Validation should be model-free and CI-friendly.

The implementation should provide enough local validation support to prove the schemas match current outputs without adding a required network-time dependency. Acceptable approaches include:

- a small repo-native validator for the limited schema features used by these files
- test-only validation helpers
- optional use of a JSON Schema library if already available, with a no-new-required-dependency fallback

Validation should check at least:

- required top-level fields exist
- stable scalar fields have expected types
- stable status/scope fields match allowed values
- arrays and objects are shaped correctly enough for primary-AI consumption
- representative generated artifacts from tests conform to the appropriate schemas
- malformed fixture artifacts fail validation with useful messages

The first implementation does not need a public CLI command for validation unless planning finds it very cheap. If a CLI is deferred, it should be captured as backlog.

### Documentation

Docs should explain:

- where schemas live
- which current artifact each schema applies to
- that schemas describe machine-readable contracts for primary AIs and scripts
- that schemas are additive and may allow optional fields
- that schema validation is model-free and does not require Ollama
- that `result.json` has a generic envelope plus mode-specific payload sections

### Compatibility

This change should avoid rewriting current artifact shapes unless the schema work reveals an obvious inconsistency or bug.

Where current artifacts have optional feature-specific fields, schemas should allow those fields without forcing unrelated runs to include them. For example:

- unchunked summarize jobs may not include chunking details
- runs without snippets may omit snippet details or mark snippet policy as off
- doctor reports may include tokenizer diagnostics only in some environments
- failed jobs may have error fields instead of complete result payloads

## Acceptance Criteria

- A tracked `schemas/` folder exists.
- `schemas/README.md` or equivalent documentation explains the schema set and intended consumers.
- A schema index exists and lists each schema ID, file path, artifact/command surface, and status.
- A persisted `farm-status.json` schema exists for current run status artifacts.
- A persisted job `result.json` schema exists for current job result artifacts.
- A `farm status --json` overview-envelope schema exists.
- A `farm status <run-id> --json` run-envelope schema exists.
- A `farm doctor --json` / `setup-doctor.json` schema exists.
- Schemas are valid JSON and include `$schema`, `$id`, title, type, and required top-level fields.
- Schemas target the current schema version emitted by each output surface.
- Schemas preserve the distinction between persisted artifacts and CLI JSON envelopes.
- Schemas permit known optional fields for chunking, snippets, timing, tokenizer diagnostics, and warnings without requiring them for every artifact.
- Model-free tests validate representative generated/current-shaped artifacts against the schemas.
- Model-free tests include at least one negative case that fails validation with a useful message.
- Current `farm run`, `farm status --json`, and `farm doctor --json` behavior remains unchanged except for documentation or additive validation utilities.
- Existing `.run/` artifacts are not migrated or rewritten.
- No tests require Ollama, installed local models, tokenizer downloads, or network access.
- README and AI usage docs mention the schema folder and when primary AIs/scripts should use it.
- BL-0007 is marked planned/implemented as appropriate.
- Deferred schema and validation follow-ups are captured in backlog.

## Test Plan

Automated:

- tests that every schema file is valid JSON
- tests that `schemas/index.json` points to existing schema files
- tests that each schema declares `$schema`, `$id`, title, description, and type
- validation tests for representative `farm-status.json`
- validation tests for representative job `result.json`
- validation tests for representative `farm status --json` overview output
- validation tests for representative `farm status <run-id> --json` output
- validation tests for representative `setup-doctor.json`
- negative validation test for a malformed artifact missing required fields
- full model-free test suite

Verification:

```powershell
python -m unittest tests.test_qwen_farm_schema tests.test_qwen_farm tests.test_qwen_farm_status tests.test_qwen_farm_doctor
python -m unittest discover -s tests
git diff --check
```

Optional manual smoke:

```powershell
python sift.py farm status --json
python sift.py farm doctor --json
```

If a validation helper or command is added during implementation, smoke it against a recent local run and the doctor report.

## Deferred To Roadmap

- Public `farm schema validate <path>` CLI command if not included in the first implementation.
- Schemas for `timing-summary.json` and `TIMING_SUMMARY.md` metadata.
- Schemas for snippet packs.
- Schemas for synthesis bundles and budget metadata.
- Schemas for dogfood history records and comparison outputs.
- Strict CI validation of checked-in fixture artifacts.
- Schema version migration guidance across persisted farm artifact versions and newer CLI/report envelope versions.
- Generating schema documentation from schema files.
- Strict mode that rejects unknown/additional fields after contracts stabilize.
