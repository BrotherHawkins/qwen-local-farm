# Extract Lite Dogfood

Synthetic extract-mode fixture set for repeatable local runtime checks.

The files are intentionally authored rather than downloaded. They plant claims, facts, examples, questions, tensions, entities, links, tasks, decisions, risks, requirements, blockers, and follow-ups so a local run can be checked for recall, precision, source grounding, JSON shape, and chunk behavior.

Suggested runtime output location:

```powershell
python sift.py farm run dogfood/extract_lite/inputs --mode extract --extract-preset research --output .run/dogfood_extract_lite/research
```

To force the long research fixture through chunked extract behavior:

```powershell
python sift.py farm run dogfood/extract_lite/inputs --mode extract --extract-preset research --chunk-strategy character --chunk-chars 2500 --output .run/dogfood_extract_lite/research_chunked
```

Useful preset-specific runs:

```powershell
python sift.py farm run dogfood/extract_lite/inputs --mode extract --extract-preset evidence --output .run/dogfood_extract_lite/evidence
python sift.py farm run dogfood/extract_lite/inputs --mode extract --extract-preset entities --output .run/dogfood_extract_lite/entities
python sift.py farm run dogfood/extract_lite/inputs --mode extract --extract-preset work --output .run/dogfood_extract_lite/work
```

After a run, validate the aggregate:

```powershell
python sift.py farm schema validate .run/dogfood_extract_lite/research/<run-id>/extract-results.json --json
```

Use `expected-signals.json` as a scoring guide. It is not a strict golden output because extract mode intentionally allows sparse results and model wording differences.

