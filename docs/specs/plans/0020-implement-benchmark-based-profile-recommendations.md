# 0020 Implement Benchmark-Based Profile Recommendations

Status: Implemented
Spec: [0020 Add Benchmark-Based Profile Recommendations](../changes/0020-add-benchmark-based-profile-recommendations.md)

## Plan

Implement a conservative measured recommendation workflow that gives power users CLI-ready settings and gives a primary AI a clear JSON/Markdown artifact to inspect for less technical users.

1. Add a recommendation module.
   - create a focused helper module, likely `src/sift_farm_recommend.py`
   - keep recommendation scoring deterministic and model-free when fed synthetic evidence
   - combine doctor-style environment evidence, selected agent/profile config, tokenizer readiness, and bounded benchmark evidence
   - keep recommendations conservative when evidence is missing, stale, failed, or weak
   - represent confidence and reasons for each major recommendation
2. Add the recommendation command.
   - add `python sift.py farm recommend`
   - support `--agent`, `--profile`, and `--output`
   - default output to `.run/recommendations/`
   - write `.run/recommendations/farm-recommendation.json`
   - write `.run/recommendations/FARM_RECOMMENDATION.md`
   - keep the probe explicitly user-invoked, bounded, and free of internet/dogfood article dependencies
3. Define the recommendation JSON contract.
   - add `schemas/farm-recommendation.schema.json`
   - register it in `schemas/index.json`
   - document it in `schemas/README.md`
   - require stable envelope fields for primary AI/script consumption
   - allow nested evidence metadata to evolve without unnecessary breakage
   - make `farm schema validate` auto-detect recommendation JSON artifacts
   - support explicit schema id/path validation
4. Implement recommendation scoring.
   - recommend runtime profile from selected/default profile and measured evidence
   - recommend resource mode vocabulary: `gpu`, `hybrid`, `cpu`, or `auto`
   - recommend `parallel_jobs`
   - recommend `OLLAMA_NUM_PARALLEL`
   - recommend summarize chunk strategy and chunk/reduce sizing
   - include warnings and next actions for missing Ollama/model/tokenizer evidence
   - do not write `.sift-farm.json` or modify Ollama environment variables
5. Integrate with doctor.
   - keep `farm doctor` fast and read-only
   - detect the latest recommendation report when present
   - show compact recommendation metadata in human output
   - include machine-readable recommendation status/summary in `doctor --json`
   - point users and primary AIs to `farm recommend` when recommendations are missing or stale
6. Add docs.
   - update README with the power-user recommendation flow
   - update AI usage docs with the primary-AI assisted setup flow
   - explain `gpu`, `hybrid`, `cpu`, and `auto` as recommendation vocabulary
   - explain `parallel_jobs` versus `OLLAMA_NUM_PARALLEL`
   - document generated files and privacy expectations under `.run/`
7. Add model-free tests.
   - recommendation scoring from synthetic benchmark evidence
   - conservative fallbacks when evidence is missing
   - concurrency recommendation logic
   - resource mode recommendation logic
   - tokenizer-ready and tokenizer-missing chunk recommendations
   - stale recommendation detection
   - Markdown rendering
   - schema validation for representative valid and invalid recommendation JSON
   - schema index/docs coverage
   - schema auto-detection and explicit schema validation
   - doctor JSON integration without running a benchmark
   - CLI parser and handler coverage with mocked evidence
8. Run local smoke.
   - run `farm doctor --json`
   - run `farm recommend --agent default --profile local-8gb --output .run/recommendations`
   - validate the recommendation JSON with `farm schema validate`
   - run `farm doctor` and `farm doctor --json` again
   - save `.run/dogfood_0020/RECOMMENDATION_SMOKE_REPORT.md` if the implementation uses a real tiny local probe
9. Update lifecycle records in the implementation PR.
   - mark BL-0021 implemented when code/docs/tests land
   - mark BL-0028 implemented when code/docs/tests land
   - keep BL-0072 open for full resource-aware runtime routing
   - mark this plan implemented
   - mark the change spec implemented
   - update the spec dashboard counts/status

## CLI Shape

Preferred command shape:

```powershell
python sift.py farm recommend
python sift.py farm recommend --agent default --profile local-8gb
python sift.py farm recommend --agent default --profile local-8gb --output .run/recommendations
```

Expected outputs:

```text
.run/recommendations/farm-recommendation.json
.run/recommendations/FARM_RECOMMENDATION.md
```

Schema validation:

```powershell
python sift.py farm schema validate .run/recommendations/farm-recommendation.json
```

## Recommendation Shape

Recommendation JSON should keep a stable envelope:

- `schema_version`
- `generated_at`
- `status`
- `agent`
- `model`
- `resource_mode`
- `profile`
- `concurrency`
- `summarize`
- `evidence`
- `warnings`
- `next_actions`

`resource_mode`, `profile`, `concurrency`, and `summarize` should include recommendations, confidence, and reasons. `evidence` may be permissive so future benchmark inputs can evolve.

## Non-Goals

This implementation will not add automatic config writing, automatic Ollama environment changes, service management, dynamic runtime backoff, scheduled benchmarks, tracked benchmark history, dashboards, charts, CI model calls, Ollama calls in CI, tokenizer downloads in CI, network access, multiple Ollama server pools, remote/frontier model profiles, or full resource-aware runtime routing.

## Verification

Completed checks:

```powershell
python -m unittest tests.test_sift_farm_recommend tests.test_sift_farm_doctor tests.test_sift_farm_schema tests.test_sift_cli
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Completed manual/local smoke:

```powershell
python sift.py farm doctor --json
python sift.py farm recommend --agent default --profile local-8gb --output .run/recommendations
python sift.py farm schema validate .run/recommendations/farm-recommendation.json
python sift.py farm doctor
python sift.py farm doctor --json
```

Smoke report:

```text
.run/dogfood_0020/RECOMMENDATION_SMOKE_REPORT.md
```

## Implementation Checklist

- [x] Add recommendation module.
- [x] Add deterministic recommendation scoring helpers.
- [x] Wire `farm recommend`.
- [x] Write recommendation JSON and Markdown artifacts.
- [x] Add `schemas/farm-recommendation.schema.json`.
- [x] Register and document the recommendation schema.
- [x] Add schema auto-detection for recommendation JSON.
- [x] Add explicit schema id/path validation coverage.
- [x] Add resource mode recommendation vocabulary.
- [x] Add profile/concurrency/chunking recommendations.
- [x] Add doctor recommendation discovery and summary output.
- [x] Add doctor JSON recommendation metadata.
- [x] Update README and AI usage docs.
- [x] Add model-free tests.
- [x] Run model-free verification.
- [x] Run local recommendation smoke if implementation uses a real tiny probe.
- [x] Update lifecycle records in the implementation PR.
