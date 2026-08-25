# 0014 Add Synthesis Bundle Budget Planning

Status: Implemented
Type: Add

## WHY

Synthesis bundles are useful because they package summaries plus verified snippets for a downstream frontier or primary model. But once a run contains enough files, the bundle can grow beyond the caller's available context window. Today the caller has to open the Markdown, guess its size, and manually trim content before using it.

The farm should make synthesis bundles budget-aware: report their size, estimate token footprint, and optionally cap the Markdown bundle to a target character or estimated-token budget without making another model call.

This change favors:

- deterministic post-run packaging over model-based compression
- visible budget metadata for primary-AI inspection
- character budgets as the exact first-class cap
- estimated token budgets clearly labeled as estimates
- preserving existing bundle output when no budget is requested
- source-backed snippets over invented condensed text

## Scope

This change adds budget planning to `farm synthesis bundle`:

- report rendered Markdown character count for every bundle
- report estimated token count for every bundle using a documented deterministic estimate
- support an optional maximum character budget
- support an optional maximum estimated-token budget that resolves to an effective character budget
- include budget settings, estimates, final counts, and dropped-content diagnostics in JSON output
- include a short budget line in Markdown output
- cap budgeted bundles by omitting lower-priority optional content rather than truncating text mid-sentence or mid-snippet
- preserve run ID lookup and existing run-directory input behavior
- preserve current default output when no budget cap is supplied except for additive budget metadata
- update BL-0061 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- exact tokenizer support for downstream frontier models
- calls to a model to rewrite or compress summaries
- semantic reranking beyond the existing deterministic snippet order
- cross-run synthesis bundles
- custom summary field templates
- citation-specific export formats
- UI/dashboard budget controls
- hard guarantees for non-farm prompt wrappers around the bundle

## Behavior

### CLI Shape

Current commands continue to work:

```powershell
python sift.py farm synthesis bundle <run-ref> --label research-bundle --max-snippets 24 --per-file 4
```

Budgeted commands may add:

```powershell
python sift.py farm synthesis bundle <run-ref> --label research-bundle --max-chars 60000
python sift.py farm synthesis bundle <run-ref> --label research-bundle --max-estimated-tokens 15000
```

Defaults:

- no character cap
- no estimated-token cap
- estimated token ratio: `4.0` characters per token
- budget policy: deterministic fit when a cap is supplied

Exact flag names can be refined during planning, but the first implementation should keep the command simple and self-documenting.

### Budget Metadata

Every JSON bundle should include a `budget` object:

```json
{
  "budget": {
    "schema_version": 1,
    "max_chars": 60000,
    "max_estimated_tokens": 15000,
    "chars_per_token": 4.0,
    "effective_max_chars": 60000,
    "input": {
      "chars": 84231,
      "estimated_tokens": 21058
    },
    "output": {
      "chars": 59872,
      "estimated_tokens": 14968
    },
    "fit": true,
    "was_capped": true,
    "dropped": {
      "snippets": 6,
      "open_questions": 3,
      "bullets": 8,
      "items": 0
    },
    "warnings": []
  }
}
```

If no cap is supplied, `max_chars`, `max_estimated_tokens`, and `effective_max_chars` are `null`, `fit` is `true`, and `was_capped` is `false`.

Estimated token counts must be labeled as estimates. They should be deterministic and based on rendered Markdown character count divided by `chars_per_token`, rounded up.

### Effective Character Budget

When only `--max-chars` is supplied, `effective_max_chars` is that value.

When only `--max-estimated-tokens` is supplied, `effective_max_chars` is:

```text
floor(max_estimated_tokens * chars_per_token)
```

When both are supplied, use the stricter effective character cap.

Invalid budgets, zero or negative budgets, and invalid `chars_per_token` values should fail before writing output.

### Fitting Policy

The first implementation should keep budget fitting deterministic and conservative:

1. Build the full bundle using current 0011 behavior.
2. Render the full Markdown and record input size.
3. If no cap is supplied or the full Markdown fits, write the full bundle with budget metadata.
4. If the full Markdown exceeds the cap, drop optional content in a stable order until it fits:
   - snippets beyond the existing ranked order, preserving file diversity as much as practical
   - open questions
   - lower-priority bullets
   - summary-only items only if the bundle still cannot fit
5. Never cut a snippet or summary sentence in the middle.
6. If the header and minimum viable item metadata cannot fit, write the smallest deterministic bundle possible and mark `fit: false` with a warning.

The exact fitting algorithm can be refined during planning, but it must be reproducible and must record what was dropped.

### Markdown Output

Markdown output should include a compact budget line near the top:

```markdown
Budget: 59,872 chars, ~14,968 tokens estimated; cap 60,000 chars; fit yes
```

This line helps a primary AI decide whether the bundle can be pasted into a downstream prompt without opening the JSON.

### JSON Output

The JSON `items` and `counts` should reflect the final emitted bundle after budget fitting, not only the pre-budget bundle.

Budget diagnostics should preserve enough detail for a primary AI to understand why a bundle became terse:

- full/input size before fitting
- final/output size after fitting
- effective cap
- dropped snippets/open questions/bullets/items counts
- warnings when the budget could not be met cleanly

## Acceptance Criteria

- `farm synthesis bundle <run-ref>` still works without budget flags.
- JSON output includes budget metadata even when no cap is supplied.
- Markdown output includes a compact budget line.
- `--max-chars <n>` caps the rendered Markdown bundle to at most `n` characters when feasible.
- `--max-estimated-tokens <n>` caps by estimated token budget through a documented character conversion.
- Supplying both character and estimated-token caps uses the stricter effective character budget.
- Invalid budget values fail before writing bundle outputs.
- Budget fitting is deterministic across repeated runs with the same inputs and options.
- Budget fitting does not invent new summary or snippet text.
- Budget fitting does not truncate snippets or summary text mid-string.
- JSON `counts`, `items`, and selected snippet counts reflect the final emitted bundle.
- JSON budget diagnostics record input size, output size, effective cap, fit status, whether content was capped, dropped content counts, and warnings.
- Existing snippet cap behavior remains compatible with budget caps.
- Existing `farm run`, `farm list`, `farm status`, snippet packs, dogfood records, and unbudgeted synthesis bundles remain unchanged apart from additive budget metadata.
- README and AI usage docs explain character caps, estimated token caps, and estimate caveats.
- BL-0061 is marked planned/implemented as appropriate.
- Deferred related items remain in backlog.
- Model-free tests cover size estimation, effective budget resolution, invalid budgets, no-cap metadata, character cap fitting, estimated-token cap fitting, stricter dual caps, dropped-content diagnostics, Markdown budget line, JSON final counts, and CLI parsing.

## Test Plan

Automated:

- unit tests for estimated token calculation and effective budget resolution
- unit tests for invalid budget options
- unit tests for unbudgeted bundle metadata
- unit tests for fitting under a character cap
- unit tests for fitting under an estimated-token cap
- unit tests for dual-cap strictness
- unit tests for dropped-content diagnostics
- unit tests that budget fitting preserves whole snippets/summary strings
- unit tests for Markdown budget line rendering
- CLI parser tests for budget flags
- full model-free test suite

Verification:

```powershell
python -m unittest tests.test_qwen_farm_synthesis_bundles tests.test_qwen_cli
python -m unittest discover -s tests
git diff --check
```

Optional dogfood smoke, using an existing local lite run:

```powershell
python sift.py farm synthesis bundle <run-id> --output .run/dogfood_0014/synthesis-bundles --label dogfood-lite-budget --max-chars 60000
```

Inspect:

- whether the bundle fits the declared cap
- whether budget metadata is easy for a primary AI to inspect
- whether the capped Markdown remains useful downstream
- whether dropped-content diagnostics explain any terseness

## Deferred To Roadmap

- Exact downstream tokenizer adapters for common frontier models.
- User-selectable budget fitting policies such as evidence-first, summary-first, or balanced.
- Reserved prompt-wrapper budget so callers can target total prompt size instead of bundle-only size.
- Budget planning for snippet-only packs.
- Budget-aware cross-run bundles.
