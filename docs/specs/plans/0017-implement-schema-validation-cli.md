# 0017 Implement Schema Validation CLI

Status: Implemented
Spec: [0017 Add Schema Validation CLI](../changes/0017-add-schema-validation-cli.md)

## Plan

Implement a public CLI around the tracked schema contracts and dependency-free validator:

1. Extend `src/qwen_farm_schema.py`.
   - load `schemas/index.json`
   - resolve explicit schema references by local path or schema ID
   - auto-detect known artifact surfaces from stable top-level fields
   - validate artifacts and return a structured result object
   - render concise human-readable output
   - preserve JSON-friendly error results for missing files, invalid JSON, missing schemas, and unsupported/ambiguous detection
2. Add CLI support in `qwen.py`.
   - `python qwen.py farm schema validate <json-path>`
   - `--schema <schema-path-or-id>`
   - `--json`
   - print human output by default
   - print only JSON with `--json`
   - exit `0` for valid, `1` for schema validation errors, `2` for command/input/schema/detection errors
3. Add model-free tests.
   - parser tests for the new command and flags
   - schema ID/path resolution tests
   - auto-detection tests for all five 0016 schema surfaces
   - unsupported detection test
   - valid/invalid render tests
   - JSON result shape tests
   - CLI handler tests for success, validation failure, and input/schema errors
4. Update docs and lifecycle records.
   - README command examples
   - AI usage guidance for primary AIs and scripts
   - roadmap note that public schema validation exists
   - mark BL-0068 implemented when code lands
   - update spec/dashboard status to implemented in the implementation PR

## Auto-Detection Rules

Infer schemas only from stable top-level fields:

- `scope: "overview"` and `schema_version: 1` -> `farm-status-overview.schema.json`
- `scope: "run"` and `schema_version: 1` -> `farm-status-run.schema.json`
- doctor report fields `environment`, `ollama`, `checks`, `recommendations`, and `report_paths` -> `farm-doctor.schema.json`
- persisted run fields `run_id`, `jobs`, `counts`, `skipped_files`, and `schema_version: "0.1"` -> `farm-status.schema.json`
- persisted job fields `job_id`, `structured_valid`, `result`, `artifacts`, and `schema_version: "0.1"` -> `farm-job-result.schema.json`

Unsupported or ambiguous shapes should fail with exit code `2` and recommend passing `--schema`.

## Non-Goals

This implementation will not add new schemas, advanced JSON Schema features, validation during every farm run, directory-wide validation, strict unknown-field rejection, schema migration tools, remote schema fetching, model calls, or Ollama-dependent tests.

## Verification

Implemented with:

- schema index loading and schema reference resolution by path or ID
- auto-detection for the five 0016 schema surfaces
- structured validation result objects
- human and JSON render paths
- `python qwen.py farm schema validate <json-path>`
- `--schema <schema-path-or-id>`
- `--json`
- exit codes `0`, `1`, and `2`
- README, AI usage, schema README, and roadmap docs
- model-free schema and CLI tests

Checks:

```powershell
python -m unittest tests.test_qwen_farm_schema tests.test_qwen_cli
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

Manual smoke:

```powershell
python qwen.py farm schema validate .run/reports/setup-doctor.json
python qwen.py farm schema validate .run/reports/setup-doctor.json --json
python qwen.py farm schema validate .run/reports/setup-doctor.json --schema schemas/farm-doctor.schema.json
```

Optional local run smoke:

```powershell
python qwen.py farm schema validate <run-dir>/farm-status.json
python qwen.py farm schema validate <run-dir>/jobs/job-0001/result.json
```

## Implementation Checklist

- [x] Extend schema module with index loading and schema resolution.
- [x] Add auto-detection for all five 0016 schema surfaces.
- [x] Add structured validation result helper.
- [x] Add human and JSON render behavior.
- [x] Wire `farm schema validate` CLI parser and handler.
- [x] Add schema helper tests.
- [x] Add CLI parser and handler tests.
- [x] Update README and AI usage docs.
- [x] Update roadmap/backlog/dashboard lifecycle records.
- [x] Run model-free verification.
