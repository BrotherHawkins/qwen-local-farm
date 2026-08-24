# Farm Artifact Schemas

This folder contains the first tracked contracts for Qwen Local Farm JSON artifacts. They are intended for primary AIs, scripts, tests, and humans who need to inspect farm output without reverse-engineering every artifact shape from code.

The schemas are JSON Schema-compatible and intentionally permissive around optional feature metadata. They focus on the stable envelope fields that callers use to identify an artifact, inspect status, find paths, and read core result payloads.

## Schemas

| Schema | Applies To |
| --- | --- |
| `farm-status.schema.json` | Persisted run status files named `farm-status.json`. |
| `farm-job-result.schema.json` | Persisted per-job result files named `jobs/job-*/result.json`. |
| `farm-status-overview.schema.json` | `python qwen.py farm status --json` overview output. |
| `farm-status-run.schema.json` | `python qwen.py farm status <run-id> --json` output. |
| `farm-doctor.schema.json` | `python qwen.py farm doctor --json` and `.run/reports/setup-doctor.json`. |

`index.json` lists the same contracts in machine-readable form.

## Version Notes

Persisted farm run/job artifacts currently use `schema_version: "0.1"`. Newer CLI/report envelopes currently use `schema_version: 1`.

Schemas describe the current emitted shape for each surface. They are not a migration system for older local `.run/` artifacts.

## Validation Notes

The test suite validates representative generated artifacts against these schemas with a dependency-free helper in `src/qwen_farm_schema.py`. The helper supports the subset of JSON Schema used here and keeps validation model-free and CI-friendly.
