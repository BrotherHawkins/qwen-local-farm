# 0017 Add Schema Validation CLI

Status: Implemented
Type: Add

## WHY

0016 added tracked schema contracts and a small dependency-free validator, but the validation surface is still internal to tests. Power users, scripts, and primary AIs should be able to validate a JSON artifact with one local command instead of writing Python snippets or manually matching paths to schema files.

The farm should expose a public, model-free schema validation command that uses the tracked schemas and returns clear human-readable or machine-readable results.

This change favors:

- making the new schema layer directly usable
- preserving model-free and CI-friendly assumptions
- explicit schema selection for power users
- safe auto-detection for known artifact surfaces
- clear exit codes for scripts
- JSON stdout when requested by a primary AI or automation

## Scope

This change adds a public farm schema validation command:

- add `python sift.py farm schema validate <json-path>`
- add `python sift.py farm schema validate <json-path> --schema <schema-path-or-id>`
- add `python sift.py farm schema validate <json-path> --json`
- use tracked schemas from `schemas/index.json`
- auto-detect a schema for known current artifact shapes when `--schema` is omitted
- validate with the dependency-free helper from 0016
- print concise human-readable validation results by default
- print valid JSON results with `--json`
- return exit code `0` when validation passes
- return non-zero exit code when validation fails, input cannot be read, schema cannot be found, or auto-detection is ambiguous/unsupported
- update docs so primary AIs and scripts know how to use the command
- update BL-0068 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- new schemas beyond the core 0016 schema set
- strict unknown-field rejection
- advanced JSON Schema features such as `$ref`, `oneOf`, or pattern properties
- validation during every `farm run`
- schema migration tools
- remote schema fetching
- model calls
- Ollama-dependent tests
- tokenizer downloads or network access
- validation for Markdown files

## Behavior

### CLI Shape

Validate with auto-detection:

```powershell
python sift.py farm schema validate .run/reports/setup-doctor.json
python sift.py farm schema validate .run/farm/<run-id>/farm-status.json
python sift.py farm schema validate .run/farm/<run-id>/jobs/job-0001/result.json
```

Validate with an explicit schema path:

```powershell
python sift.py farm schema validate .run/reports/setup-doctor.json --schema schemas/farm-doctor.schema.json
```

Validate with an explicit schema ID from `schemas/index.json`:

```powershell
python sift.py farm schema validate .run/reports/setup-doctor.json --schema https://sift.local/schemas/farm-doctor.schema.json
```

Machine-readable output:

```powershell
python sift.py farm schema validate .run/reports/setup-doctor.json --json
```

### Auto-Detection

When `--schema` is omitted, the command should infer a schema from stable top-level fields:

- `scope: "overview"` and `schema_version: 1` -> `farm-status-overview.schema.json`
- `scope: "run"` and `schema_version: 1` -> `farm-status-run.schema.json`
- doctor report fields such as `environment`, `ollama`, `checks`, `recommendations`, and `report_paths` -> `farm-doctor.schema.json`
- persisted run status fields such as `run_id`, `jobs`, `counts`, `skipped_files`, and `schema_version: "0.1"` -> `farm-status.schema.json`
- persisted job result fields such as `job_id`, `structured_valid`, `result`, `artifacts`, and `schema_version: "0.1"` -> `farm-job-result.schema.json`

If no schema can be inferred, the command should fail with a useful message that suggests passing `--schema`.

If more than one schema appears plausible, the command should fail rather than guessing.

### Human Output

Successful validation should print a compact result:

```text
Valid: .run/reports/setup-doctor.json
Schema: schemas/farm-doctor.schema.json
Errors: 0
```

Failed validation should print:

```text
Invalid: path/to/artifact.json
Schema: schemas/farm-status.schema.json
Errors: 2
- $.run_id: missing required field 'run_id'
- $.status: expected one of [...]
```

Exact wording can be refined during planning, but the output should be easy for a primary AI to quote back to a user.

### JSON Output

With `--json`, stdout should contain only valid JSON:

```json
{
  "schema_version": 1,
  "valid": false,
  "artifact_path": "path/to/artifact.json",
  "schema": {
    "id": "https://sift.local/schemas/farm-status.schema.json",
    "path": "schemas/farm-status.schema.json",
    "detected": true
  },
  "errors": [
    "$: missing required field 'run_id'"
  ]
}
```

Error cases that happen before validation should also be JSON when `--json` is supplied.

### Exit Codes

The command should support script-friendly exit codes:

- `0`: validation passed
- `1`: validation completed and found schema errors
- `2`: command usage, unreadable input, invalid JSON, missing schema, or unsupported/ambiguous auto-detection

Exact numeric values can be refined during planning if repo conventions suggest something else, but pass/fail/error must be distinguishable.

## Acceptance Criteria

- `python sift.py farm schema validate <json-path>` validates a known current artifact through auto-detection.
- `--schema <schema-path>` validates with an explicit local schema file.
- `--schema <schema-id>` resolves schema IDs listed in `schemas/index.json`.
- `--json` prints valid JSON with no Markdown or explanatory prose.
- Human output clearly reports valid/invalid status, artifact path, schema path, and error count.
- Validation failures include path-aware error messages from the existing validator.
- Unknown artifact shapes fail with a helpful message suggesting `--schema`.
- Missing input files fail cleanly.
- Invalid JSON input fails cleanly.
- Missing/unknown schema paths or IDs fail cleanly.
- Exit code `0` is used only for passing validation.
- A non-zero exit code is used for schema validation failures.
- A distinct non-zero exit code is used for command/input/schema errors.
- Current `farm run`, `farm list`, `farm status`, `farm doctor`, snippets, synthesis bundles, and dogfood commands remain unchanged.
- No tests require Ollama, installed local models, tokenizer downloads, model calls, or network access.
- README and AI usage docs document the validation command for power users and primary AIs.
- BL-0068 is marked planned/implemented as appropriate.
- Deferred schema follow-ups remain backlogged.

## Test Plan

Automated:

- parser tests for `farm schema validate`
- parser tests for `--schema`
- parser tests for `--json`
- unit tests for schema ID/path resolution
- unit tests for auto-detecting all five 0016 schema surfaces
- unit tests for unsupported auto-detection
- unit tests for human rendering of valid and invalid results
- unit tests for JSON result shape
- handler tests for success exit behavior
- handler tests for validation failure exit behavior
- handler tests for invalid JSON/missing file/missing schema failures
- full model-free test suite

Verification:

```powershell
python -m unittest tests.test_sift_farm_schema tests.test_sift_cli
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Manual smoke:

```powershell
python sift.py farm schema validate .run/reports/setup-doctor.json
python sift.py farm schema validate .run/reports/setup-doctor.json --json
python sift.py farm schema validate .run/reports/setup-doctor.json --schema schemas/farm-doctor.schema.json
```

Optionally validate a recent dogfood run:

```powershell
python sift.py farm schema validate <run-dir>/farm-status.json
python sift.py farm schema validate <run-dir>/jobs/job-0001/result.json
```

## Deferred To Roadmap

- Schemas for post-run package artifacts, including timing summaries, snippet packs, synthesis bundles, dogfood history, and comparison outputs.
- Strict schema mode that rejects unknown/additional fields.
- Generated schema documentation.
- Schema version migration guidance.
- Validation commands that operate on an entire run directory.
- CI fixture validation gates for checked-in sample artifacts.
