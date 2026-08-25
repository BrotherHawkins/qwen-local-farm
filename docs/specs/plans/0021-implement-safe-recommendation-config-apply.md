# 0021 Implement Safe Recommendation Config Apply

Status: Implemented
Spec: [0021 Add Safe Recommendation Config Apply](../changes/0021-add-safe-recommendation-config-apply.md)

## Plan

Implement a safe recommendation-to-config workflow that previews by default, writes only with explicit intent, validates both input and output, and leaves machine-readable evidence for primary AIs.

1. Add apply helpers to the recommendation module.
   - extend `src/sift_farm_recommend.py` or a small sibling module only if the file gets unwieldy
   - load recommendation JSON from the default or explicit path
   - validate recommendation JSON against `schemas/farm-recommendation.schema.json`
   - block missing, malformed, invalid, or `needs_setup` recommendations
   - extract supported farm config fields from the recommendation
   - list `resource_mode` and `OLLAMA_NUM_PARALLEL` as not-applied guidance
2. Build proposed config safely.
   - read existing `.sift-farm.json` when present
   - validate existing config through existing profile/config helpers before merging
   - merge supported recommendation fields while preserving safe existing fields
   - validate the proposed config through existing config normalization helpers
   - compute stable field-level changes with before/after/action values
3. Implement preview and write behavior.
   - default to preview/dry-run and do not modify config
   - require `--write` before writing config
   - create parent folders as needed for non-default config paths
   - back up existing config before overwrite
   - write config with deterministic JSON formatting
   - write the apply report JSON and Markdown in preview and write modes
4. Wire CLI.
   - implement the nested command `python sift.py farm recommend apply`
   - support optional recommendation path
   - support `--config`, `--output`, `--write`, and `--json`
   - preserve existing `python sift.py farm recommend` behavior
   - print concise human output plus report paths in Markdown mode
5. Define the apply report schema.
   - add `schemas/farm-config-apply.schema.json`
   - register it in `schemas/index.json`
   - document it in `schemas/README.md`
   - make schema auto-detection recognize apply reports
   - add explicit schema id/path validation coverage
6. Update docs.
   - update README with preview/apply commands
   - update AI usage docs with primary-AI assisted config apply guidance
   - clearly state that Ollama environment settings are guidance only
   - document generated apply report paths
7. Add model-free tests.
   - preview does not write config
   - write writes config
   - existing config backup
   - existing valid config merge/preservation
   - existing invalid config blocks apply
   - missing/malformed/invalid recommendation handling
   - `needs_setup` write block
   - `ready_with_warnings` warning-visible behavior
   - not-applied guidance for resource mode and `OLLAMA_NUM_PARALLEL`
   - apply report Markdown rendering
   - apply report schema validation and auto-detection
   - CLI parser and handler behavior
8. Run local smoke.
   - generate a fresh recommendation under `.run/recommendations`
   - run preview apply
   - validate `.run/recommendations/farm-config-apply.json`
   - run write apply against a temporary config under `.run/dogfood_0021/`
   - resolve doctor or config against that temporary path where practical
   - save `.run/dogfood_0021/CONFIG_APPLY_SMOKE_REPORT.md`
9. Update lifecycle records in the implementation PR.
   - mark BL-0022 implemented when code/docs/tests land
   - mark this plan implemented
   - mark the change spec implemented
   - update the spec dashboard counts/status

## CLI Shape

Preferred command shape:

```powershell
python sift.py farm recommend apply
python sift.py farm recommend apply .run/recommendations/farm-recommendation.json
python sift.py farm recommend apply --config .sift-farm.json
python sift.py farm recommend apply --write
python sift.py farm recommend apply --json
```

Expected outputs:

```text
.run/recommendations/farm-config-apply.json
.run/recommendations/FARM_CONFIG_APPLY.md
```

Schema validation:

```powershell
python sift.py farm schema validate .run/recommendations/farm-config-apply.json
```

## Apply Report Shape

The apply report JSON should keep a stable envelope:

- `schema_version`
- `generated_at`
- `status`
- `dry_run`
- `recommendation_path`
- `config_path`
- `backup_path`
- `recommendation`
- `existing_config`
- `proposed_config`
- `changes`
- `not_applied`
- `warnings`
- `next_actions`

`changes` should contain compact path/before/after/action rows. `not_applied` should explain supported recommendation values that are guidance-only for now, especially `resource_mode` and `OLLAMA_NUM_PARALLEL`.

## Non-Goals

This implementation will not add interactive prompts, automatic config writes from `farm doctor`, automatic config writes from plain `farm recommend`, Ollama service environment edits, shell profile edits, service management, model pulls, package installs, GPU/CPU runtime enforcement, full resource-aware routing, or config migration tooling.

## Verification

Completed checks:

```powershell
python -m unittest tests.test_sift_farm_recommend tests.test_sift_farm_profiles tests.test_sift_farm_schema tests.test_sift_cli
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Completed manual/local smoke:

```powershell
python sift.py farm recommend --agent default --profile local-8gb --output .run/recommendations
python sift.py farm recommend apply
python sift.py farm schema validate .run/recommendations/farm-config-apply.json
python sift.py farm recommend apply --config .run/dogfood_0021/.sift-farm.json --write
python sift.py farm schema validate .run/recommendations/farm-config-apply.json
```

Smoke report:

```text
.run/dogfood_0021/CONFIG_APPLY_SMOKE_REPORT.md
```

## Implementation Checklist

- [x] Add recommendation apply helpers.
- [x] Validate recommendation JSON before use.
- [x] Build proposed `.sift-farm.json` from supported recommendation fields.
- [x] Preserve and merge valid existing config.
- [x] Block invalid existing config.
- [x] Compute field-level changes.
- [x] Report guidance-only fields in `not_applied`.
- [x] Implement preview/dry-run behavior.
- [x] Implement explicit `--write` behavior.
- [x] Back up existing config before overwrite.
- [x] Write apply JSON and Markdown reports.
- [x] Wire `farm recommend apply`.
- [x] Add `schemas/farm-config-apply.schema.json`.
- [x] Register and document the apply schema.
- [x] Add apply schema auto-detection.
- [x] Update README and AI usage docs.
- [x] Add model-free tests.
- [x] Run model-free verification.
- [x] Run local config apply smoke.
- [x] Update lifecycle records in the implementation PR.
