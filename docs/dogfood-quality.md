# Dogfood Quality History

Dogfood quality history is a local-first way to compare farm runs over time. It records compact metrics and optional human or primary-AI scores without copying raw article text, raw model responses, or full source snippets into history records.

Generated history lives under:

```text
.run/dogfood_history/
```

## Record A Run

Record an existing farm run:

```powershell
python qwen.py farm dogfood record .run/dogfood_0008/lite-ranked-final/farm-results/farm-run-2026-08-24-123139-37f1 --label 0008-lite-ranked-final
```

The default output folder is:

```text
.run/dogfood_history/runs/
```

The record includes run ID, label, commit, model, mode, status, duration, compact runtime settings, per-job timing, chunk counts, warnings, snippet selected/verified/requested counts, and snippet drop counts.

## Add Quality Notes

Scores use a 1-5 scale:

- `1`: unusable or materially wrong
- `2`: partially useful but important gaps or noise
- `3`: acceptable with clear caveats
- `4`: good and worth using downstream
- `5`: excellent, compact, accurate, and easy to trust

Score fields:

- `summary_accuracy`
- `summary_usefulness`
- `snippet_usefulness`
- `diagnostic_clarity`
- `overall`

Optional notes file:

```json
{
  "quality": {
    "summary_accuracy": 4,
    "summary_usefulness": 4,
    "snippet_usefulness": 4,
    "diagnostic_clarity": 5,
    "overall": 4
  },
  "notes": [
    "Article 004 snippets improved.",
    "Article 009 chose fewer but cleaner snippets."
  ],
  "jobs": {
    "009-qmd-query-markup-documents.txt": {
      "quality": {
        "summary_accuracy": 4,
        "snippet_usefulness": 3,
        "overall": 4
      },
      "notes": ["Snippet count was lower, but weak pointer text was gone."]
    }
  }
}
```

Record with notes:

```powershell
python qwen.py farm dogfood record <run-dir> --label 0009-lite-candidate --notes .run/dogfood_0009/quality-notes.json
```

## Compare Runs

Compare two records:

```powershell
python qwen.py farm dogfood compare .run/dogfood_history/runs/0008-lite-ranked-final.json .run/dogfood_history/runs/0009-lite-candidate.json
```

The default output folder is:

```text
.run/dogfood_history/comparisons/
```

Comparison output includes:

- JSON for scripts and primary AIs
- Markdown for quick human review
- runtime deltas
- warning deltas
- snippet selected/verified/requested deltas
- supplied quality score deltas
- run notes

## Privacy And Noise Rules

History records intentionally omit:

- raw article text
- raw model responses
- full summary Markdown
- full source snippet text

Keep generated history in `.run/` unless the project explicitly decides to track aggregate benchmark files later.
