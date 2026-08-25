# 0030 Implement Farm Discovery Include/Exclude Overrides

Status: Implemented

Change Spec: [0030-add-farm-discovery-include-exclude-overrides.md](../changes/0030-add-farm-discovery-include-exclude-overrides.md)

## Goal

Add reproducible include/exclude controls for farm file discovery while preserving the existing safe default skips for unsupported files and generated/vendor folders.

## Implementation Steps

- [x] Add `discovery.include` and `discovery.exclude` to runtime config resolution and validation.
- [x] Add repeated `farm run --include` and `farm run --exclude` CLI flags.
- [x] Implement normalized run-relative glob matching for otherwise eligible text files.
- [x] Preserve built-in safety skips and make exclude win over include.
- [x] Add additive discovery diagnostics while preserving flat `skipped_files`.
- [x] Persist effective discovery settings in `farm-config.resolved.json` and `farm-status.json` runtime metadata.
- [x] Render discovery filters in `FARM_STATUS.md`.
- [x] Update schemas for status/resolved runtime metadata where needed.
- [x] Update README and AI usage docs with examples and first-pass safety limits.
- [x] Add model-free unit tests for matching, config, CLI, status/schema behavior, and retry compatibility.
- [x] Run a real filesystem smoke under `.run/dogfood_0030/` covering include, exclude, include+exclude, config, and safety skips.
- [x] Mark spec, plan, dashboard, and backlog implemented in the implementation PR.

## Test Plan

Run:

```powershell
python -m src.qwen_spec_guard
python -m unittest tests.test_qwen_farm_files tests.test_qwen_farm_profiles tests.test_qwen_farm tests.test_qwen_cli tests.test_qwen_farm_status tests.test_qwen_farm_schema
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

## Manual Verification

Use ignored artifacts only:

```text
.run/dogfood_0030/
```

Create a real directory with eligible text files, nested files, excluded folders, generated/vendor folders, and a binary-like file. Run CLI smoke commands for:

- include-only
- exclude-only
- include plus exclude
- config-driven include/exclude
- safety skip preservation

Inspect selected jobs, `skipped_files`, discovery diagnostics, resolved config, `farm-status.json`, `FARM_STATUS.md`, and `farm status --json`.
