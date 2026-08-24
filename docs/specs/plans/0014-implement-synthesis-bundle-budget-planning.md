# 0014 Implement Synthesis Bundle Budget Planning

Status: Implemented
Spec: [0014 Add Synthesis Bundle Budget Planning](../changes/0014-add-synthesis-bundle-budget-planning.md)

## Plan

Implement budget planning as deterministic post-run synthesis bundle packaging:

1. Add budget helpers in `qwen_farm_synthesis_bundles`.
   - estimate tokens from rendered Markdown character count
   - resolve effective character cap from `--max-chars`, `--max-estimated-tokens`, and `--chars-per-token`
   - validate positive budget inputs before output is written
2. Add additive budget metadata to all synthesis bundle JSON outputs.
   - no-cap bundles report size estimates but do not drop content
   - capped bundles report input/output sizes, effective cap, fit status, capped status, dropped counts, and warnings
3. Add deterministic fitting when a cap is supplied.
   - start from existing 0011 bundle content
   - drop optional content in stable order until rendered Markdown fits where feasible
   - do not invent text or cut snippets/summary strings mid-text
   - keep JSON `counts`, `items`, and snippet counts aligned to final emitted content
4. Update Markdown rendering.
   - include a compact budget line near the top
   - preserve the existing synthesis-friendly grouping by input file
5. Wire CLI flags through `farm synthesis bundle`.
   - `--max-chars`
   - `--max-estimated-tokens`
   - `--chars-per-token`, default `4.0`
6. Update docs and lifecycle records.
   - README and AI usage docs
   - 0014 spec and plan to implemented in the implementation PR
   - BL-0061 to implemented
7. Add model-free tests.
   - budget estimation and cap resolution
   - invalid budgets
   - no-cap budget metadata
   - character cap fitting
   - estimated-token cap fitting
   - dual-cap strictness
   - dropped diagnostics and final counts
   - Markdown budget line
   - CLI parsing
8. Run lite dogfood smoke after implementation.
   - use `.run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf` if present
   - output to `.run/dogfood_0014/synthesis-bundles/`
   - create an uncapped and capped budget bundle
   - inspect and report the JSON budget object from the capped output

## Non-Goals

This implementation will not add exact downstream tokenizer adapters, model-based compression, custom fitting policies, reserved prompt-wrapper budget, snippet-pack budget planning, or cross-run bundle budgeting.

## Verification

Implemented with:

- budget estimation and effective-cap helpers
- additive `budget` metadata for synthesis bundle JSON
- Markdown budget header line
- `--max-chars`, `--max-estimated-tokens`, and `--chars-per-token`
- deterministic whole-content fitting for capped bundles
- README and AI usage docs
- model-free tests

Checks:

```powershell
python -m unittest tests.test_qwen_farm_synthesis_bundles tests.test_qwen_cli
python -m unittest discover -s tests
git diff --check
```

Planned lite dogfood smoke:

```powershell
python qwen.py farm synthesis bundle .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/dogfood_0014/synthesis-bundles --label dogfood-lite-0014-full
python qwen.py farm synthesis bundle .run/dogfood_0009/lite-history-candidate/farm-results/farm-run-2026-08-24-124948-92cf --output .run/dogfood_0014/synthesis-bundles --label dogfood-lite-0014-capped --max-chars 60000
```

After the dogfood smoke, inspect the capped JSON output and report the `budget` object plus whether the resulting Markdown stayed useful.
