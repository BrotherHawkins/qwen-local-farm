# 0036 Implement Extract Mode

Spec: [0036-add-extract-mode.md](../changes/0036-add-extract-mode.md)

Status: Implemented

## Goal

Add a fast, JSON-first `extract` farm mode with presets, compact tagged-line parsing, deterministic dedupe, source offsets, chunk support, run-level aggregation, schemas, docs, and model-free tests.

## Plan

- [x] Add the 0036 change spec and backlog follow-ups.
- [x] Add extract runtime config defaults, validation, CLI flags, and resolved config output.
- [x] Add extract model prompt helpers, tagged-line parser, snippet verification, deterministic scoring, and dedupe.
- [x] Integrate extract with single-pass and chunked farm jobs.
- [x] Write per-job extract artifacts and chunk raw outputs.
- [x] Write run-level `extract-results.json` and `EXTRACT_RESULTS.md`, including partial coverage/failures.
- [x] Add schema registration and auto-detection for extract aggregate artifacts.
- [x] Update README, AI usage docs, chunking roadmap, and skills.
- [x] Add model-free parser, farm, schema, profile, CLI, and collect tests.
- [x] Run targeted model-free tests.

## Verification

```powershell
python -m unittest tests.test_sift_farm_extract tests.test_sift_farm tests.test_sift_farm_profiles tests.test_sift_farm_schema tests.test_sift_cli tests.test_sift_farm_collect tests.test_sift_skills
```

Optional runtime dogfood:

```powershell
python sift.py farm run .run/dogfood_0036/input --mode extract --extract-preset research --output .run/dogfood_0036/results
python sift.py farm schema validate .run/dogfood_0036/results/<run>/extract-results.json
```

## Notes

The implementation intentionally keeps local model work to map calls only. Python owns parsing, snippet verification, deterministic dedupe, caps, and aggregation.
