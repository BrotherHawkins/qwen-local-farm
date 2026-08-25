# 0008 Implement Snippet Ranking And Quality Metrics

Status: Implemented
Change Spec: [0008 Add Snippet Ranking And Quality Metrics](../changes/0008-add-snippet-ranking-and-quality-metrics.md)

## WHY

0007 made source snippets useful, exact-verified, and cheap enough to keep, but final selection is still mostly model candidate order plus a few low-signal filters. Dogfood showed that this can preserve useful evidence, but it can also waste slots on weak passages when better verified candidates exist.

This plan adds deterministic ranking and diagnostics so snippet selection becomes inspectable, tunable, and better suited for downstream frontier-model synthesis.

## Scope

Planned:

- deterministic snippet scoring
- score reasons for selected snippets
- explicit reject/drop reasons for low-signal, duplicate, too-long, and unverified candidates
- final selection that ranks before capping
- chunked selection from verified chunk candidates only
- simple source-neighborhood diversity for chunked files
- snippet selection diagnostics in JSON artifacts
- compact status exposure for selected/requested counts
- docs explaining ranking and diagnostics
- backlog updates for 0008-covered follow-ups
- dogfood against the full `dogfood_lite` article set

Deferred:

- embeddings or semantic retrieval
- second model call for snippet ranking
- cross-file snippet packs
- citation export formats
- snippet review state
- historical quality dashboard beyond per-run dogfood reporting
- new extraction modes

## Implementation Plan

### 1. Refactor Snippet Verification Into Selection-Friendly Helpers

Update `src/sift_farm_snippets.py` so candidate handling can distinguish:

- parsed candidate count
- exact verification success/failure
- low-signal rejection
- duplicate rejection
- too-long rejection
- selected final snippets

Keep the existing public behavior for 0007 callers, but introduce a richer selection result shape for farm internals.

Likely helper shape:

```python
{
    "snippets": [...],
    "diagnostics": {
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
    },
    "warnings": [...]
}
```

### 2. Add Deterministic Snippet Scoring

Add a cheap score function for verified snippets.

Suggested first-pass signals:

- positive terms for claim/value words: `because`, `therefore`, `rule`, `must`, `warning`, `limit`, `tradeoff`, `example`, `definition`, `measured`, `tokens`, `cost`, `fails`, `works`, `requires`
- reason-text signal when the model says the snippet captures a thesis, limitation, caveat, definition, or example
- useful length range bonus for passages that are neither tiny nor close to max chars
- modest penalty for extremely early header-like content unless it has strong signal terms
- penalty for generic pointer text such as `read more`, `see changelog`, or `learn more`

Each selected snippet should be able to carry:

- `score`
- `score_reasons`

Keep `result.md` clean; score metadata belongs in JSON unless the implementation finds a very compact Markdown presentation.

### 3. Add Diversity-Aware Selection

Implement final selection as:

1. verify and reject candidates
2. score verified candidates
3. sort by score descending, then source order for stable ties
4. select up to requested count while avoiding near-neighbor source clustering when enough candidates exist
5. backfill from remaining scored candidates if diversity would underfill the requested count

Use a simple line-distance threshold rather than a complex semantic strategy. The goal is to avoid selecting several adjacent passages from the same source neighborhood when other useful candidates are available.

### 4. Preserve 0007 Warning Semantics

Keep the warning policy from 0007:

- no snippets requested: no snippet diagnostics or empty/off compact status
- auto with at least one selected snippet: complete cleanly, with selected/requested visible
- auto with zero selected snippets when requested: warning
- fixed with fewer selected than requested: warning
- unverified candidate warnings remain strict for fixed requests and zero-result auto requests

### 5. Wire Diagnostics Into Single-Pass Jobs

Update single-pass summarize processing so:

- model output is parsed as before
- candidate snippets are verified, scored, and selected
- final payload includes only selected snippets
- final JSON result includes selection diagnostics
- status/job update includes compact selection counts
- raw response remains available for debugging

### 6. Wire Diagnostics Into Chunked Jobs

Update chunked summarize processing so:

- each map chunk verifies and scores its own candidate snippets
- chunk result artifacts can include chunk-level diagnostics
- final reduce still cannot invent snippets
- final file-level selection ranks all verified chunk snippets before capping
- final result/status artifacts expose file-level diagnostics

The reducer summary content should remain unchanged unless a tiny prompt tweak is needed for snippet candidate quality.

### 7. Update Status Rendering

Update `src/sift_farm_status.py` to preserve compact readability:

- keep the existing snippets column
- show selected/requested when selected differs from verified or when diagnostics are present
- avoid large drop-reason tables in `FARM_STATUS.md`
- keep full diagnostic counts in `farm-status.json`

### 8. Update Docs And Backlog

Update:

- `README.md`: explain ranking at a high level and where diagnostics live
- `docs/ai-usage.md`: guide primary AIs on inspecting snippet diagnostics
- `docs/backlog.md`: mark advanced ranking planned/implemented when appropriate and keep larger deferred items open
- `docs/roadmap.md`: mention accepted/implemented ranking once the PR lands
- `docs/specs/SPEC_DASHBOARD.md`: move lifecycle status as the PR progresses

### 9. Focused Dogfood

Use:

```text
.run/dogfood_0008/
```

Run:

```powershell
python sift.py farm run .run/dogfood_lite/articles-text --output .run/dogfood_0008/lite-ranked/farm-results --mode summarize --instructions "Summarize the article for later synthesis. Capture thesis, key claims, useful examples, and open questions." --agent default --chunk-strategy token --snippets auto
```

Compare against:

```text
.run/dogfood_0007/lite-auto-final-citation-filter/farm-results/farm-run-2026-08-24-120839-b8bc
```

Write:

```text
.run/dogfood_0008/DOGFOOD_0008_REPORT.md
```

Report:

- final status
- model used
- runtime vs 0007
- snippet requested/verified/selected counts
- drop/reject reason counts
- whether article 004 improved over the 0007 4/6 result
- whether article 009 avoids generic weak snippets better than 0007
- whether summaries remain accurate
- whether diagnostics are useful to inspect

## Test Plan

Automated tests:

- scoring gives higher rank to claims, caveats, definitions, and concrete examples than low-signal pointers
- scoring records stable `score_reasons`
- low-signal candidates are rejected with explicit reasons
- too-long candidates are counted separately from unverified candidates
- exact duplicate snippets are rejected before selection
- near-duplicate or adjacent snippets are diversified when alternatives exist
- fixed-count underfill produces warnings
- auto partial success does not produce warnings when at least one snippet is selected
- auto zero-selection produces warnings
- selected snippets are the only snippets rendered in Markdown
- `result.json` includes snippet selection diagnostics
- chunked final selection uses verified map-stage snippets and cannot preserve reducer-invented snippets
- `farm-status.json` includes compact snippet selection counts
- `FARM_STATUS.md` remains compact
- existing 0007 CLI/config tests continue to pass

Verification before PR:

```powershell
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Dogfood verification:

```powershell
python sift.py farm status <run-id>
```

Inspect:

- `.run/dogfood_0008/lite-ranked/farm-results/.../farm-status.json`
- `.run/dogfood_0008/lite-ranked/farm-results/.../FARM_STATUS.md`
- several per-job `result.json`
- several per-job `result.md`
- chunk diagnostics for article 004 or 009
- `.run/dogfood_0008/DOGFOOD_0008_REPORT.md`

## Acceptance Checklist

- [x] Change spec exists.
- [x] Human accepted the behavior target.
- [x] Implementation plan exists.
- [x] Human accepted the implementation plan.
- [x] Snippet candidates are verified, scored, and selected before final persistence.
- [x] Final snippets are ranked before capping.
- [x] Selected snippets include score metadata in JSON when snippets are enabled.
- [x] Score reasons are deterministic and covered by tests.
- [x] Low-signal rejection has explicit diagnostics.
- [x] Duplicate rejection has explicit diagnostics.
- [x] Too-long rejection has explicit diagnostics.
- [x] Unverified rejection has explicit diagnostics.
- [x] Diversity selection avoids clustered snippets when useful alternatives exist.
- [x] Single-pass jobs include snippet selection diagnostics.
- [x] Chunked jobs include final file-level snippet selection diagnostics.
- [x] Final reduce cannot invent snippets.
- [x] Auto warning behavior stays best-effort.
- [x] Fixed warning behavior stays strict.
- [x] `result.md` remains readable and renders only selected snippets.
- [x] `result.json` exposes full snippet diagnostics.
- [x] `farm-status.json` exposes compact snippet diagnostics.
- [x] `FARM_STATUS.md` stays compact.
- [x] README and AI usage docs are updated.
- [x] Backlog items covered by 0008 are updated.
- [x] Model-free test suite passes.
- [x] Compile check passes.
- [x] Diff check passes.
- [x] Dogfood 0008 report is recorded.
