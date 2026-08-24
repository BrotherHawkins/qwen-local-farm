# 0025 Implement Configurable Farm Failure Policy

Status: Implemented
Spec: [0025 Add Configurable Farm Failure Policy](../changes/0025-add-configurable-farm-failure-policy.md)

## Plan

- [x] Accept `0025` as the behavior target for BL-0009 and BL-0017.
- [x] Add `failure_policy` defaults to resolved runtime profiles.
- [x] Add config and CLI override validation for file attempts, model-call timeout, chunk attempts, and reduce attempts.
- [x] Route `farm run` through the resolved failure policy while preserving direct `run_farm` override compatibility.
- [x] Add chunk/reduce model-call retry wrappers that keep failed attempt timing records.
- [x] Surface failure policy in resolved config, status JSON, and status Markdown.
- [x] Update docs, dashboard, backlog, and lifecycle state.
- [x] Add model-free tests for config, CLI, retry behavior, status visibility, and spec guard coverage.
- [x] Run a small runtime smoke with the new flags under `.run/dogfood_0025/`.

## Verification

```powershell
python -m src.qwen_spec_guard
python -m unittest tests.test_qwen_farm_profiles tests.test_qwen_cli tests.test_qwen_farm
python -m unittest discover -s tests -p "test_*.py"
python -m compileall qwen.py examples src tests
git diff --check
```

Runtime smoke:

```powershell
python qwen.py farm run .run/dogfood_0025/input --output .run/dogfood_0025/farm-results --mode summarize --max-attempts 1 --chunk-max-attempts 1 --reduce-max-attempts 1
python qwen.py farm status <run-id> --json
```

## Notes

This implementation keeps adaptive recovery deferred. The new policy is explicit, fixed, and model-free to validate.
