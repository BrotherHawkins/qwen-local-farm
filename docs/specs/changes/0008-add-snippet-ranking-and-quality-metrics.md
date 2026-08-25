# 0008 Add Snippet Ranking And Quality Metrics

Status: Implemented
Type: Add

## WHY

0007 proved that verified source snippets add useful downstream value for modest overhead, but dogfood also showed that the first implementation still depends too much on the model's candidate order. Prompt guidance and simple low-signal filters removed the worst padding, but they do not reliably choose the most useful passages when a chunk offers several valid candidates.

The farm should make snippet selection more deliberate and inspectable without turning snippet extraction into a separate slow pipeline.

This change favors:

- better snippet usefulness for frontier-model synthesis
- deterministic ranking over ad hoc candidate order
- visible quality diagnostics for dogfood and future tuning
- model-free implementation and CI assumptions
- preserving the 0007 fast summarize call shape
- small, source-local scoring before larger semantic approaches

## Scope

This change improves source snippets for `summarize` mode:

- rank verified snippet candidates before final selection
- prefer thesis, key claims, definitions, examples, caveats, limits, and operational details
- penalize or drop low-signal candidates such as front matter, source URLs, conversion headers, bibliography lines, navigation text, and generic "read more" lines
- prefer source diversity so chunked summaries do not over-select adjacent or duplicate passages
- expose snippet selection diagnostics in result/status artifacts
- track candidate counts, selected counts, and drop/reject reasons
- keep `--snippets auto`, `--snippets N`, and existing snippet config semantics intact
- keep snippets disabled by default
- dogfood against the same lite article set and compare to the final 0007 snippet run

## Non-Goals

This change does not add:

- embedding-assisted snippet search
- semantic retrieval over the full source
- an additional model call solely to rank snippets
- cross-file snippet packs
- quote or citation export formats
- snippet review UI or accepted/rejected states
- automatic snippet extraction by default
- new summarize chunk sizing behavior
- changes to the main summary schema beyond additive snippet diagnostics

## Behavior

### Ranking

After snippet candidates are verified against the source, the farm ranks them before final selection. Ranking should be deterministic and cheap.

The first implementation should use source-local signals such as:

- candidate length within a useful range
- source words that indicate claims, limits, examples, definitions, measurements, rules, warnings, or tradeoffs
- model-provided reason text, when present
- source position and chunk position
- duplicate or near-duplicate text
- low-signal patterns from 0007

The ranking does not need to be perfect. It needs to be better than "first verified candidate wins" and easy to inspect.

### Diversity

For chunked files, the final selected snippets should avoid clustering when possible:

- prefer at most one selected snippet from the same small source neighborhood before filling remaining slots
- preserve important snippets even if they are near each other when the requested count cannot otherwise be filled
- keep exact source provenance for every selected snippet

### Diagnostics

Artifacts should expose why snippets were selected or not selected without making the human read raw model responses.

Each snippet-enabled job should include a compact diagnostics object with counts such as:

```json
{
  "snippet_selection": {
    "policy": "auto",
    "requested_count": 5,
    "candidate_count": 10,
    "verified_count": 7,
    "selected_count": 4,
    "dropped": {
      "unverified": 2,
      "low_signal": 1,
      "duplicate": 0,
      "too_long": 0
    }
  }
}
```

Selected snippets may include ranking metadata if it is useful and not too noisy, for example:

```json
{
  "text": "Exact source passage.",
  "reason": "Why this passage matters.",
  "score": 8,
  "score_reasons": ["claim", "limit"],
  "source_path": "article.txt",
  "start_line": 12,
  "end_line": 12
}
```

If ranking metadata risks cluttering `result.md`, keep it in `result.json` only.

### Status

`FARM_STATUS.md` and `farm-status.json` should remain easy for a primary AI to inspect:

- keep the existing `verified/requested` snippet count
- include selected count when it differs from verified count
- expose warning-worthy failures only when strict fixed-count requests cannot be satisfied or no snippets can be verified
- keep auto partial counts visible without turning useful partial results into warning states

### Performance

Ranking and diagnostics should not materially increase model time:

- no Ollama JSON grammar mode
- no second model call for ranking
- no embeddings
- no semantic index
- deterministic Python scoring should be negligible relative to model calls

## Acceptance Criteria

- Existing no-snippet runs behave as before.
- Existing 0007 snippet CLI/config flags continue to work.
- Verified snippet candidates are ranked before final selection.
- Final chunked snippets are selected from verified chunk candidates, not reducer-invented text.
- Low-signal candidates have explicit drop/reject reasons instead of disappearing invisibly.
- Duplicate exact snippets are not selected twice.
- Selected snippets favor higher-signal passages over tags, source headers, URL/citation lines, generic "read more" lines, and other scaffolding.
- Chunked files prefer diversity across source neighborhoods when enough candidates exist.
- `result.json` includes snippet selection diagnostics for snippet-enabled jobs.
- `farm-status.json` includes enough snippet diagnostics for a primary AI to see requested, verified, selected, and warning state.
- `FARM_STATUS.md` keeps a compact snippet column and does not become noisy.
- `result.md` remains readable and only renders selected verified snippets.
- Auto snippet runs can complete cleanly with partial selected counts when at least one useful verified snippet is selected.
- Fixed snippet runs still warn when fewer than the requested number can be selected.
- Docs explain how snippet ranking works at a high level and how to inspect diagnostics.
- Backlog items implemented by this spec are marked implemented or updated with the 0008 source.
- Deferred snippet follow-ups remain in backlog.
- Model-free tests cover scoring, low-signal drop reasons, duplicate handling, diversity selection, diagnostics shape, single-pass selection, and chunked selection.
- Dogfood compares the 0008 ranked-snippet run against the final 0007 snippet run on the lite article set.

## Test Plan

Automated:

- unit tests for snippet scoring and score reasons
- unit tests for low-signal drop reasons
- unit tests for duplicate candidate removal
- unit tests for diversity selection across source neighborhoods
- unit tests for diagnostics counts
- single-pass summarize test proving selected snippets are ranked verified snippets
- chunked summarize test proving final snippets come from verified chunk candidates and are ranked before capping
- status rendering tests for compact snippet diagnostics
- config/CLI regression tests proving 0007 flags still work
- full model-free test suite

Verification:

```powershell
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Dogfood:

Use a new ignored folder:

```text
.run/dogfood_0008/
```

Run the same lite article set:

```powershell
python sift.py farm run .run/dogfood_lite/articles-text --output .run/dogfood_0008/lite-ranked/farm-results --mode summarize --instructions "Summarize the article for later synthesis. Capture thesis, key claims, useful examples, and open questions." --agent default --chunk-strategy token --snippets auto
```

Compare against final 0007 run:

```text
.run/dogfood_0007/lite-auto-final-citation-filter/farm-results/farm-run-2026-08-24-120839-b8bc
```

Inspect:

- status and duration
- requested/verified/selected counts
- dropped low-signal candidates
- selected snippet usefulness
- whether article 004 and 009 choose better snippets than 0007
- whether summaries remain accurate
- whether runtime overhead stays close to 0007

Write:

```text
.run/dogfood_0008/DOGFOOD_0008_REPORT.md
```

## Deferred To Roadmap

- Embedding-assisted snippet selection.
- Cross-file snippet packs for later synthesis.
- Quote/citation export formats.
- Snippet review states such as accepted/rejected.
- Historical snippet-quality dashboard beyond the current dogfood report.
- Dedicated extraction modes and richer extraction schemas.
