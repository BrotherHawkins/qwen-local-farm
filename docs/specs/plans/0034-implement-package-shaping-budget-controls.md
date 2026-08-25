# 0034 Implement Package Shaping And Budget Controls

Spec: [0034-add-package-shaping-budget-controls.md](../changes/0034-add-package-shaping-budget-controls.md)

## Outcome

Add deterministic package-shaping controls so synthesis bundles and snippet packs can be sized and tailored for downstream frontier-model handoff without extra model calls.

## Checklist

- [x] Add synthesis summary template and field-filter parsing.
- [x] Apply selected summary fields to synthesis bundle JSON and Markdown.
- [x] Add synthesis bundle fit policies: `summary-first`, `evidence-first`, and `balanced`.
- [x] Add snippet-pack budget estimation and cap fitting.
- [x] Update package JSON schemas for shaped summaries and snippet-pack budgets.
- [x] Add CLI flags and command wiring.
- [x] Update README and AI usage documentation.
- [x] Add model-free unit, CLI, and schema tests.
- [x] Update spec dashboard and backlog lifecycle bookkeeping.

## Verification

Run:

```bash
python -m unittest tests.test_sift_cli tests.test_sift_farm_synthesis_bundles tests.test_sift_farm_snippet_packs tests.test_sift_farm_schema
python -m unittest discover -s tests
python -m compileall sift.py examples src tests
python -m src.sift_spec_guard
git diff --check
```

No Ollama model calls, model pulls, tokenizer downloads, or network access are required for this implementation.
