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
| `farm-recommendation.schema.json` | Benchmark-based profile/concurrency/chunking recommendation JSON from `python qwen.py farm recommend`. |
| `farm-config-apply.schema.json` | Preview/write report from `python qwen.py farm recommend apply`. |
| `farm-timing-summary.schema.json` | Persisted timing summary files named `timing-summary.json`. |
| `farm-collection.schema.json` | Farm collection manifest JSON from `python qwen.py farm collect`. |
| `farm-snippet-pack.schema.json` | Snippet pack JSON from `python qwen.py farm snippets pack`. |
| `farm-synthesis-bundle.schema.json` | Synthesis bundle JSON from `python qwen.py farm synthesis bundle`, including budget metadata. |
| `farm-dogfood-record.schema.json` | Dogfood quality record JSON from `python qwen.py farm dogfood record`. |
| `farm-dogfood-comparison.schema.json` | Dogfood comparison JSON from `python qwen.py farm dogfood compare`. |

`index.json` lists the same contracts in machine-readable form.

## Version Notes

Persisted farm run/job artifacts and timing summaries currently use `schema_version: "0.1"`. Newer CLI/report envelopes and post-run package artifacts currently use `schema_version: 1`.

Schemas describe the current emitted shape for each surface. They are not a migration system for older local `.run/` artifacts.

## Validation Notes

The test suite validates representative generated artifacts against these schemas with a dependency-free helper in `src/qwen_farm_schema.py`. The helper supports the subset of JSON Schema used here and keeps validation model-free and CI-friendly.

Use the public CLI when validating local artifacts:

```bash
python qwen.py farm schema validate .run/reports/setup-doctor.json
python qwen.py farm schema validate .run/reports/setup-doctor.json --json
python qwen.py farm schema validate .run/reports/setup-doctor.json --schema schemas/farm-doctor.schema.json
python qwen.py farm schema validate .run/recommendations/farm-recommendation.json
python qwen.py farm schema validate .run/recommendations/farm-config-apply.json
```

Without `--schema`, the command auto-detects the current core farm JSON artifacts and post-run package JSON artifacts. Exit code `0` means valid, `1` means schema validation failed, and `2` means command/input/schema resolution failed.
