# 0034 Add Package Shaping And Budget Controls

Status: Implemented
Type: Add

## WHY

Snippet packs and synthesis bundles are now useful handoff artifacts for frontier-model synthesis. The next pain point is control: a primary AI or power user needs to decide what fits in a downstream prompt without manually editing Markdown or guessing which parts were removed.

Synthesis bundles already report estimated size and can cap output, but the fitting order is fixed and callers cannot choose which summary fields to include. Snippet packs already provide ranked source evidence, but they do not report or enforce character/token budgets.

This change should make post-run packages easier to shape for different downstream jobs:

- compact orientation when the frontier model only needs summaries
- evidence-heavy packets when the frontier model needs source-backed examples
- predictable character or estimated-token budgets
- deterministic omission instead of model-based rewriting
- JSON diagnostics clear enough for another AI to inspect

## Scope

Add package-shaping controls to post-run helper commands:

- summary field templates for `farm synthesis bundle`
- explicit summary field filters for `farm synthesis bundle`
- selectable synthesis bundle budget fitting policies
- character and estimated-token budget planning for `farm snippets pack`
- budget metadata and diagnostics in both package JSON shapes
- Markdown budget/policy lines that make package decisions visible without opening JSON
- schema updates for snippet packs and synthesis bundles
- README and AI usage documentation for the new controls
- model-free tests for CLI parsing, package shaping, schema validation, and deterministic budget fitting

This covers backlog items BL-0060, BL-0064, and BL-0066.

## Non-Goals

This change does not add:

- exact tokenizer adapters for downstream frontier models
- prompt-wrapper reserved budget
- model calls to rewrite or compress summaries
- semantic snippet selection
- cross-run snippet packs or synthesis bundles
- citation-specific export formats
- package browsing UI
- automatic downstream prompt construction
- any GitHub CI test that requires Ollama, network access, or a local model

## Behavior

### Summary Field Templates

`farm synthesis bundle` should support a template flag:

```powershell
python sift.py farm synthesis bundle <run-ref> --summary-template compact
```

Supported first-pass templates:

| Template | Summary Fields | Intent |
| --- | --- | --- |
| `standard` | `title`, `abstract`, `bullets`, `open_questions`, `confidence` | Current default behavior. |
| `compact` | `title`, `abstract` | Small orientation package. |
| `claims` | `title`, `abstract`, `bullets` | Argument/key-claim package. |
| `questions` | `title`, `abstract`, `open_questions` | Follow-up/research planning package. |

Default template: `standard`.

The JSON `limits` object should record:

```json
{
  "summary_template": "compact",
  "summary_fields": ["title", "abstract"]
}
```

Markdown output should render only the selected summary fields.

JSON output should also honor the selected fields in each emitted `item.summary` object, so the JSON package has roughly the same downstream budget behavior as the Markdown package. The schema should allow selected summary fields to be absent.

### Explicit Summary Field Filters

Callers should be able to override the template with explicit fields:

```powershell
python sift.py farm synthesis bundle <run-ref> --summary-fields title,abstract,bullets
```

Rules:

- supported fields are `title`, `abstract`, `bullets`, `open_questions`, and `confidence`
- `--summary-fields` overrides `--summary-template`
- duplicate field names are ignored after the first occurrence
- unknown fields, empty field lists, and lists with no supported fields fail before writing output
- emitted field order follows the canonical order above, not caller input order

### Synthesis Bundle Fit Policies

`farm synthesis bundle` should support a fitting policy flag:

```powershell
python sift.py farm synthesis bundle <run-ref> --max-chars 60000 --fit-policy evidence-first
```

Supported policies:

| Policy | Behavior |
| --- | --- |
| `summary-first` | Preserve summaries longest and drop snippets before optional summary fields. This preserves the current default behavior. |
| `evidence-first` | Preserve selected snippets longest and drop optional summary fields before snippets. |
| `balanced` | Alternate dropping lower-priority summary detail and lower-ranked snippets so packages remain useful as both orientation and evidence. |

Default policy: `summary-first`.

The fitting algorithm must remain deterministic. It should drop whole optional fields, whole snippets, or whole items only. It must not truncate snippets, summary strings, bullet strings, or open-question strings.

The budget object should record the selected policy and dropped-content diagnostics:

```json
{
  "budget": {
    "fit_policy": "evidence-first",
    "dropped": {
      "snippets": 4,
      "open_questions": 2,
      "bullets": 3,
      "items": 0
    },
    "warnings": []
  }
}
```

Markdown output should include the policy in the budget line when a budget object is present.

### Snippet Pack Budget Planning

`farm snippets pack` should support the same budget-estimation flags as synthesis bundles:

```powershell
python sift.py farm snippets pack <run-ref> --max-chars 40000
python sift.py farm snippets pack <run-ref> --max-estimated-tokens 10000
python sift.py farm snippets pack <run-ref> --chars-per-token 4.0
```

Defaults should match synthesis bundle budget planning:

- no character cap
- no estimated-token cap
- `chars_per_token`: `4.0`

Snippet packs should include a `budget` object with:

- `schema_version`
- `max_chars`
- `max_estimated_tokens`
- `chars_per_token`
- `effective_max_chars`
- pre-fit input `chars` and estimated tokens
- post-fit output `chars` and estimated tokens
- `fit`
- `was_capped`
- dropped snippet count
- warnings

When a snippet pack exceeds a requested budget, fitting should:

1. Build the candidate pack with existing ranking, dedupe, `--max-snippets`, and `--per-file` behavior.
2. Render the candidate Markdown and record input size.
3. Drop whole snippets in deterministic lowest-priority order until the rendered pack fits.
4. Keep JSON `counts` and snippet lists aligned with the final emitted package.
5. Mark `fit: false` with a warning if the minimum package header and diagnostics cannot fit.

Snippet pack fitting should not invent, rewrite, or truncate snippet text.

### JSON Schemas

Update tracked schemas so generated package JSON validates:

- `schemas/farm-synthesis-bundle.schema.json`
- `schemas/farm-snippet-pack.schema.json`
- `schemas/index.json` only if schema metadata changes

The synthesis bundle schema should allow shaped `summary` objects where selected fields are absent. The snippet pack schema should include budget metadata as a first-class contract.

### Documentation

Update docs so humans and AI assistants can discover the controls:

- README package/bundle examples
- AI usage guidance for frontier-model handoff
- any schema list or validation guidance affected by the new JSON fields

Docs should explain that estimated token counts are deterministic planning estimates, not exact frontier-tokenizer counts.

## Acceptance Criteria

- `farm synthesis bundle <run-ref>` keeps current default behavior unless new shaping flags are supplied.
- `farm synthesis bundle --summary-template <name>` emits only the template's selected summary fields in Markdown and JSON.
- `farm synthesis bundle --summary-fields <csv>` emits only valid selected fields and records the selection in JSON limits.
- Invalid summary templates or fields fail before writing package outputs.
- `farm synthesis bundle --fit-policy summary-first` preserves the current default drop order.
- `farm synthesis bundle --fit-policy evidence-first` preserves snippets longer than optional summary detail under a tight budget.
- `farm synthesis bundle --fit-policy balanced` deterministically removes both summary detail and snippets under a tight budget.
- Bundle budget diagnostics record the selected fit policy and dropped-content counts.
- `farm snippets pack` emits budget metadata even when no cap is supplied.
- `farm snippets pack --max-chars <n>` caps rendered Markdown when feasible by dropping whole snippets.
- `farm snippets pack --max-estimated-tokens <n>` resolves to a deterministic effective character cap using `chars_per_token`.
- Supplying both snippet-pack caps uses the stricter effective character budget.
- Snippet-pack budget fitting never truncates snippet text.
- Snippet-pack JSON counts and selected snippets reflect the final emitted package.
- Markdown package headers expose enough budget/policy information for primary-AI inspection.
- Updated schemas validate generated shaped package JSON.
- README and AI usage docs include examples for field shaping, fit policy, and snippet-pack budgets.
- Model-free tests cover CLI parsing, invalid options, deterministic field shaping, each fit policy, snippet-pack budget fitting, schema validation, and docs examples.

## Test Plan

Automated:

- CLI parser tests for `--summary-template`, `--summary-fields`, `--fit-policy`, and snippet-pack budget flags
- unit tests for summary template resolution
- unit tests for explicit summary field parsing and validation
- unit tests for synthesis bundle JSON/Markdown field shaping
- unit tests for all three synthesis fit policies under tight budgets
- unit tests for snippet-pack budget metadata with no cap
- unit tests for snippet-pack character and estimated-token caps
- unit tests that snippet-pack fitting preserves whole snippets
- schema validation tests for shaped synthesis bundles and budgeted snippet packs
- documentation command parse tests where applicable
- full model-free unit test discovery

Verification:

```powershell
python -m unittest tests.test_sift_cli tests.test_sift_farm_synthesis_bundles tests.test_sift_farm_snippet_packs tests.test_sift_farm_schema
python -m unittest discover -s tests
python -m src.sift_spec_guard
git diff --check
```

Optional runtime smoke, using an existing local summarize run:

```powershell
python sift.py farm synthesis bundle <run-id> --output .run/dogfood_0034/packages --label compact --summary-template compact --max-chars 20000 --fit-policy evidence-first
python sift.py farm snippets pack <run-id> --output .run/dogfood_0034/packages --label snippets-budget --max-estimated-tokens 5000
python sift.py farm schema validate .run/dogfood_0034/packages/compact.json
python sift.py farm schema validate .run/dogfood_0034/packages/snippets-budget.json
```

Inspect:

- whether shaped Markdown is materially easier to paste into a frontier-model prompt
- whether JSON records enough policy and dropped-content information
- whether the budget behavior is obvious from package headers
- whether defaults still feel unsurprising

## Deferred To Roadmap

- Exact downstream tokenizer adapters remain BL-0063.
- Reserved prompt-wrapper budget remains BL-0065.
- Cross-run synthesis bundles remain BL-0062.
- Cross-run snippet packs remain BL-0056.
- Snippet pack browsing UI remains BL-0057.
- Generated schema documentation remains BL-0070.
