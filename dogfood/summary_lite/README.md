# Summary Lite Dogfood

Synthetic summarize-mode fixture set for repeatable local runtime checks.

The files are authored, anonymous, and license-clean. They are designed to exercise ordinary summaries, verified snippets, character chunking, heading ancestry, chunk overlap, reduce behavior, timing records, snippet packs, and synthesis bundles without committing generated outputs.

Suggested full local run:

```powershell
python sift.py farm run dogfood/summary_lite/inputs --mode summarize --instructions "Summarize for frontier-model handoff. Capture thesis, key claims, useful examples, risks, decisions, and open questions." --snippets auto --chunk-strategy character --chunk-chars 4500 --reduce-chars 5000 --chunk-overlap-chars 200 --output .run/dogfood_summary_lite/farm-results
```

Suggested post-run benchmark and packaging:

```powershell
python sift.py farm dogfood timing record <run-id> --output .run/dogfood_summary_lite/timing --label summary-lite
python sift.py farm snippets pack <run-id> --output .run/dogfood_summary_lite/snippet-packs --label summary-lite --max-snippets 12 --per-file 3
python sift.py farm synthesis bundle <run-id> --output .run/dogfood_summary_lite/synthesis-bundles --label summary-lite-compact --summary-template compact --max-estimated-tokens 6000
```

Use `expected-signals.json` as a scoring guide. It is not a strict golden output because summarize mode may phrase results differently across local model versions.

