# 0007 Implement Source Snippets For Summarize

Status: Implemented
Change Spec: [0007 Add Source Snippets For Summarize](../changes/0007-add-source-snippets-for-summarize.md)

## WHY

0006 made summarize fast enough for real dogfood, but long technical inputs can become too terse after map/reduce. A primary frontier model can use a short local summary, but it benefits more when the farm also preserves a few exact source passages that carry claims, definitions, limitations, examples, or memorable operational details.

This plan adds optional verified snippets to summarize results while preserving the fast labeled-text summarize path.

## Scope

Planned:

- snippet policy settings with normal farm config precedence
- CLI overrides for `--snippets off|auto|N` and `--snippet-max-chars`
- default snippets disabled for backward compatibility
- per-job auto snippet count resolution
- prompt updates for candidate snippet output when enabled
- labeled-text parsing for snippet candidates
- exact source verification before snippets enter final artifacts
- source location metadata for verified snippets
- Markdown rendering for source snippets
- single-pass summarize snippet support
- chunked summarize snippet carry-forward from verified chunk candidates
- run/job/result metadata for resolved snippet policy/count
- docs for humans and primary AIs
- focused dogfood on articles 005 and 009
- model-free tests

Deferred:

- advanced snippet ranking
- cross-file snippet packs
- dedicated extraction modes
- quote/citation export formats
- semantic or embedding-assisted snippet selection
- snippet review state
- snippet-quality history dashboards

## Implementation Plan

### 1. Extend Runtime Config

Update `src/qwen_farm_profiles.py` to accept snippet settings under `summarize`:

- `snippet_policy`: `off`, `fixed`, or `auto`
- `snippet_count`: integer or null
- `snippet_min_count`: non-negative integer
- `snippet_max_count`: non-negative integer
- `snippet_max_chars`: positive integer

Defaults:

```json
{
  "snippet_policy": "off",
  "snippet_count": null,
  "snippet_min_count": 2,
  "snippet_max_count": 8,
  "snippet_max_chars": 600
}
```

Validation rules:

- `fixed` requires `snippet_count`.
- `auto` and `off` require `snippet_count` to be null or absent.
- `snippet_max_count >= snippet_min_count`.
- `snippet_max_chars > 0`.

Persist the resolved run-level settings in `farm-config.resolved.json` as normal.

### 2. Add CLI Override Plumbing

Update `qwen.py farm run` argument parsing:

```powershell
--snippets off
--snippets auto
--snippets 3
--snippet-max-chars 800
```

Map CLI values into runtime overrides:

- `off` or `0` -> `snippet_policy: off`, `snippet_count: null`
- `auto` -> `snippet_policy: auto`, `snippet_count: null`
- positive integer -> `snippet_policy: fixed`, `snippet_count: N`

Reject invalid values before run folder creation when possible.

### 3. Add Snippet Data Helpers

Add small helpers, likely in a new `src/qwen_farm_snippets.py` unless `qwen_farm_model.py` remains cleaner:

- `resolve_snippet_request(...)`
- `parse_snippet_candidates(...)`
- `verify_snippet_candidate(...)`
- `line_range_for_span(...)`
- `select_final_snippets(...)`

Use simple dictionaries for result payloads unless a dataclass clearly improves readability.

Verified snippet shape:

```json
{
  "text": "Exact source passage.",
  "reason": "Why this passage matters.",
  "source_path": "article.txt",
  "start_line": 12,
  "end_line": 14,
  "char_start": 345,
  "char_end": 430
}
```

### 4. Resolve Per-Job Snippet Counts

Add a per-job resolution step after content/chunk facts are known.

For `off`:

- requested snippets = 0

For `fixed`:

- requested snippets = `snippet_count`

For `auto`:

```text
if token count is available:
  requested = ceil(source_tokens / 3000)
else if chunked:
  requested = chunk_count + 1
else:
  requested = 2

requested = clamp(requested, snippet_min_count, snippet_max_count)
```

For character-strategy runs without token counts, a simple character fallback is acceptable if it is documented, such as:

```text
requested = ceil(source_chars / 12000)
requested = clamp(requested, snippet_min_count, snippet_max_count)
```

Persist the resolved per-job count in status/result artifacts.

### 5. Update Summary Prompt Shape

When requested snippet count is greater than zero, update `summarize_messages(...)` to ask for a snippet section in the same labeled-text response:

```text
SOURCE SNIPPETS:
- TEXT: <exact source passage>
  REASON: <why it matters>
```

Guardrails in the prompt:

- snippets must be copied exactly from source text
- snippets should be no longer than `snippet_max_chars`
- snippets should be independently useful for later synthesis
- if no useful snippet exists, return none

Keep the fast call shape:

- no Ollama JSON grammar mode
- `think: false`
- bounded output

If needed, increase default summarize `num_predict` only modestly when snippets are enabled and document that tradeoff.

### 6. Parse And Verify Single-Pass Snippets

Extend `parse_summary_response(...)` to parse snippet candidates from labeled text while preserving compatibility with existing JSON-like model responses.

For single-pass jobs:

- parse candidate snippets
- verify exact source substring against the original source text
- trim only harmless boundary whitespace
- drop unverified candidates
- record warnings when candidates are unverified or fewer than requested were verified
- include verified snippets in `payload["snippets"]`

Do not include unverified text in `payload["snippets"]`.

### 7. Preserve Chunk Snippet Candidates

For chunked summarize jobs:

- resolve a final requested snippet count for the file
- ask each chunk map call for a small number of candidate snippets, likely 2
- verify candidates against the chunk/source text before writing chunk result artifacts
- include verified chunk snippets in chunk result JSON/Markdown
- carry verified chunk snippets forward outside the reduce prompt/control path

The final reduce call summarizes chunk payloads, but it must not be the authority for source snippets.

### 8. Select Final Chunked Snippets

After chunk maps and reduce finish:

- collect verified snippets from chunk results
- select up to the resolved final count
- first-pass selection can use model-provided order, source order, or a simple interleaving across chunks
- de-duplicate exact duplicate snippet text
- attach the selected snippets to the final file-level payload

If there are fewer verified snippets than requested, warn but keep the job complete.

### 9. Persist Metadata In Artifacts

Update:

- `farm-status.json`
- `FARM_STATUS.md`
- per-job `result.json`
- chunk result JSON where snippets exist
- `result.md`

Expose:

- run-level snippet settings in runtime config
- per-job resolved snippet policy/count
- verified snippet count
- warnings for unverified or under-request snippets

Keep existing result consumers compatible with added fields.

### 10. Update Docs And Backlog

Update:

- `README.md`: summarize snippet flags and output location
- `docs/ai-usage.md`: when primary AIs should request snippets, how auto works, and how to inspect them
- `docs/roadmap.md`: mark 0007 implemented once implementation lands
- `docs/specs/SPEC_DASHBOARD.md`: lifecycle status updates
- `docs/backlog.md`: keep deferred snippet follow-ups open unless implemented

### 11. Focused Dogfood

Use a new ignored folder:

```powershell
.run/dogfood_0007/
```

Copy dogfood_lite articles 005 and 009:

- `005-karpathy-llm-wiki-starter-vault.txt`
- `009-qmd-query-markup-documents.txt`

Run a fixed-count pass:

```powershell
python qwen.py farm run .run/dogfood_0007/articles-text --output .run/dogfood_0007/fixed/farm-results --mode summarize --instructions "Summarize the article for later synthesis. Capture thesis, key claims, useful examples, open questions, and useful source evidence." --agent default --parallel-jobs 1 --chunk-strategy token --snippets 3
```

Run an auto pass:

```powershell
python qwen.py farm run .run/dogfood_0007/articles-text --output .run/dogfood_0007/auto/farm-results --mode summarize --instructions "Summarize the article for later synthesis. Capture thesis, key claims, useful examples, open questions, and useful source evidence." --agent default --parallel-jobs 1 --chunk-strategy token --snippets auto
```

Compare against the non-snippet fastpath runs:

- runtime overhead
- resolved snippet counts
- verified snippet counts
- warnings
- snippet usefulness
- summary quality
- whether snippets compensate for terse long-article summaries

Write:

```powershell
.run/dogfood_0007/DOGFOOD_0007_REPORT.md
```

## Test Plan

Automated tests:

- default config leaves snippets off
- config accepts `off`, `fixed`, and `auto`
- config rejects invalid snippet policy/count combinations
- CLI parses `--snippets off`, `--snippets auto`, `--snippets 0`, and `--snippets N`
- CLI rejects invalid `--snippets` values
- CLI/request overrides project config
- auto count resolves from token count when available
- auto count resolves from chunk count or character fallback when tokens are unavailable
- snippet candidates parse from labeled text
- exact source verification finds character offsets and line ranges
- unverified candidates are excluded and warned
- Markdown renders verified snippets
- single-pass summarize result includes snippets when requested
- chunked summarize result carries verified chunk snippets into the final payload
- final reduce cannot invent snippets
- no-snippet runs preserve existing result shape and status behavior
- fast summarize call-shape tests still prove no Ollama JSON grammar mode by default

Verification before PR:

```powershell
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

Dogfood verification:

```powershell
python qwen.py farm status <fixed-run-id>
python qwen.py farm status <auto-run-id>
```

Inspect:

- `.run/dogfood_0007/fixed/farm-results/.../farm-status.json`
- `.run/dogfood_0007/auto/farm-results/.../farm-status.json`
- per-job `result.json`
- per-job `result.md`
- chunk result JSON for article 009
- `.run/dogfood_0007/DOGFOOD_0007_REPORT.md`

## Acceptance Checklist

- [x] Change spec exists.
- [x] Human accepted the behavior target.
- [x] Implementation plan exists.
- [x] Human accepted the implementation plan.
- [x] Snippet settings are supported in farm config.
- [x] CLI snippet overrides are supported.
- [x] Existing no-snippet runs remain backward compatible.
- [x] Auto snippet policy resolves per job.
- [x] Fixed snippet policy resolves per job.
- [x] Snippet candidates are parsed from fast labeled-text output.
- [x] Snippets are verified against exact source text before persistence.
- [x] Unverified candidates are excluded and warned for strict requests.
- [x] Single-pass summarize jobs can include verified snippets.
- [x] Chunked summarize jobs can include final snippets selected from verified chunk snippets.
- [x] Final reduce does not invent snippets.
- [x] Markdown renders snippets clearly.
- [x] Result/status artifacts expose resolved snippet settings and counts.
- [x] Docs explain snippet policy and primary-AI usage.
- [x] Deferred snippet follow-ups remain tracked in backlog.
- [x] Model-free tests cover config, CLI, parsing, verification, rendering, and chunked carry-forward.
- [x] Compile check passes.
- [x] Focused dogfood report is recorded.
