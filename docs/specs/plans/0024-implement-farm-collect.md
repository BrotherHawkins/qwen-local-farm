# 0024 Implement Farm Collect

Status: Implemented
Spec: [0024 Add Farm Collect](../changes/0024-add-farm-collect.md)

## Plan

- [x] Accept `0024` as the behavior target for BL-0010.
- [x] Add a dedicated model-free collection module for existing run result artifacts.
- [x] Wire `python sift.py farm collect <run-ref>` into the CLI.
- [x] Support run directory paths and known run IDs through the existing resolver.
- [x] Write `farm-collection.json`, `FARM_COLLECTION.md`, and copied item artifacts under a label folder.
- [x] Keep source files, raw model responses, logs, and chunk artifacts out of the default collection.
- [x] Add a tracked JSON schema and register schema auto-detection.
- [x] Add model-free tests for collection behavior, schema validation, and CLI parsing.
- [x] Update README, backlog, and spec dashboard lifecycle records.

## Verification

```powershell
python -m src.qwen_spec_guard
python -m unittest tests.test_qwen_farm_collect tests.test_qwen_farm_schema
python -m unittest discover -s tests -p "test_*.py"
python -m compileall sift.py examples src tests
git diff --check
```

## Notes

The first implementation intentionally keeps `farm collect` as a plain run-output gatherer. Snippet packs and synthesis bundles remain the specialized downstream-context tools.
