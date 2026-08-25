# 0026 Implement Markdown Heading Ancestry And Chunk Overlap

Status: Implemented
Spec: [0026 Add Markdown Heading Ancestry And Chunk Overlap](../changes/0026-add-markdown-heading-ancestry-and-chunk-overlap.md)

## Plan

- [x] Accept `0026` as the behavior target for BL-0015 and BL-0035.
- [x] Add summarize config defaults and validation for heading ancestry plus overlap settings.
- [x] Add CLI overrides for heading ancestry and overlap settings.
- [x] Extend chunk planning/rendering to compute heading ancestry and optional prior overlap.
- [x] Persist heading ancestry and overlap metadata in chunk records/results.
- [x] Surface effective settings in resolved config, status JSON, and status Markdown.
- [x] Update README/AI usage docs and backlog/dashboard lifecycle state.
- [x] Add model-free tests for heading extraction, fenced code behavior, overlap, config, CLI, artifacts, and status visibility.
- [x] Run focused tests, full test discovery, spec guard, compileall, diff check, and a small `.run/dogfood_0026/` runtime smoke if practical.

## Verification

```powershell
python -m src.sift_spec_guard
python -m unittest tests.test_sift_farm_chunks tests.test_sift_farm_profiles tests.test_sift_cli tests.test_sift_farm
python -m unittest discover -s tests -p "test_*.py"
python -m compileall sift.py examples src tests
git diff --check
```

Runtime smoke target:

```powershell
python sift.py farm run .run/dogfood_0026/input --output .run/dogfood_0026/farm-results --mode summarize --chunk-chars 700 --chunk-overlap-chars 120
python sift.py farm status <run-id> --json
```

## Notes

Heading ancestry should be default-on. Overlap should remain default-off and explicit because it spends prompt budget and can create duplicate summary material.
