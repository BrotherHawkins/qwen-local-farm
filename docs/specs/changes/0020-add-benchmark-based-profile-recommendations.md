# 0020 Add Benchmark-Based Profile Recommendations

Status: Implemented
Type: Add

## WHY

The farm now has runtime profiles, configurable chunk sizing, scheduler concurrency, `farm doctor`, timing summaries, dogfood quality history, and dogfood timing history. That gives us enough evidence to stop relying only on static defaults when helping a user choose local settings.

Power users want CLI knobs. Less technical users want a primary AI or chatbot to inspect the machine and choose safe settings. Both paths need a measured recommendation artifact that says, in plain terms and machine-readable JSON:

- which profile looks safest
- which resource mode looks safest: `gpu`, `hybrid`, `cpu`, or `auto`
- what `parallel_jobs` should be
- what `OLLAMA_NUM_PARALLEL` should likely be
- whether token-aware chunking should be used
- which chunk/reduce token settings look reasonable
- why those recommendations were made

This change combines:

- BL-0021: benchmark-based profile recommendation
- BL-0028: safe concurrency recommendation for `parallel_jobs` and `OLLAMA_NUM_PARALLEL`

This change favors:

- explicit user-invoked local measurement over automatic background benchmarking
- conservative recommendations over chasing maximum throughput
- JSON/Markdown reports that primary AIs can inspect
- power-user CLI controls plus doctor-friendly guidance
- small model-free tests for recommendation logic
- no network or model calls in CI
- no automatic config writing in the first slice

## Scope

This change adds a first benchmark-based recommendation workflow:

- add a command that runs or records a small local benchmark profile probe
- produce a local recommendation report under `.run/`
- recommend a farm runtime profile
- recommend a resource mode vocabulary value: `gpu`, `hybrid`, `cpu`, or `auto`
- recommend safe `parallel_jobs`
- recommend safe `OLLAMA_NUM_PARALLEL`
- recommend summarize chunk/reduce sizing when token-aware chunking is available
- explain confidence, evidence, and caveats in both JSON and Markdown
- add a tracked JSON Schema for the recommendation JSON artifact
- register the recommendation schema in the schema index/docs
- make schema validation auto-detect recommendation JSON artifacts
- make `farm doctor` surface the latest measured recommendation when available
- update docs for power users and primary AIs
- update BL-0021 and BL-0028 from open to planned/implemented as lifecycle progresses

The benchmark can use existing farm/timing primitives or a small synthetic prompt/file corpus. Exact command names can be refined during planning, but the user-facing shape should be easy to discover from `farm doctor`.

## Non-Goals

This change does not add:

- automatic config writing to `.qwen-farm.json`
- automatic Ollama service environment changes
- starting/stopping Ollama with recommended environment variables
- dynamic runtime backoff during active farm runs
- cross-machine normalization
- scheduled benchmarks
- tracked benchmark history
- dashboards or charts
- CI model calls, Ollama calls, tokenizer downloads, or network access
- recommendations for every future mode
- remote/frontier model profiles
- multiple Ollama server pools
- full resource-aware runtime routing or automatic agent switching
- GPU memory probing beyond data already available to doctor unless planning finds a tiny safe read-only path

## Behavior

### Recommendation Command

Add a reproducible command for measured local recommendations.

Suggested shape:

```powershell
python qwen.py farm recommend
python qwen.py farm recommend --agent default --profile local-8gb
python qwen.py farm recommend --output .run/recommendations
```

If `farm recommend` is too broad during planning, `farm doctor recommend` or `farm benchmark recommend` is acceptable as long as:

- the command is easy to find
- docs show the exact command
- `farm doctor` can point users to it

The command should write:

```text
.run/recommendations/farm-recommendation.json
.run/recommendations/FARM_RECOMMENDATION.md
```

The command may also write raw benchmark/timing artifacts under the same output folder if useful, but the recommendation report is the stable user-facing output.

### Recommendation Inputs

The first implementation may combine:

- current doctor environment data
- selected/default agent config
- current runtime profile defaults
- tokenizer readiness
- measured benchmark timing from a tiny local probe
- existing recent dogfood timing records if explicitly supplied or easy to locate

The first implementation should not depend on internet access. It should not require dogfood article text. It should not run long benchmarks by default.

If a local model/Ollama is unavailable, the command should fail gracefully with a clear recommendation to run `farm doctor` or setup commands rather than producing fake measured advice.

### Benchmark Probe

The measured probe should be intentionally small and bounded.

Acceptable first-pass approaches include:

- run a tiny synthetic summarize corpus through the existing farm with a small output folder
- run one or more short direct local model calls and measure wall-clock duration
- reuse an existing local dogfood timing record when the caller passes it explicitly

Planning should choose the smallest implementation that proves useful recommendations without making the command slow or flaky.

The probe should record:

- started/completed timestamps
- duration
- model
- profile
- agent
- prompt/input size class
- whether token-aware chunking was available
- whether the run succeeded
- warnings or errors

### Recommendation Report

Recommendation JSON should be close to:

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-24T18:00:00Z",
  "status": "ready",
  "agent": "default",
  "model": "qwen3.5:4b",
  "resource_mode": {
    "recommended": "hybrid",
    "confidence": "medium",
    "reason": "Use GPU when available but keep CPU/RAM fallback acceptable for this local setup."
  },
  "profile": {
    "recommended": "local-8gb",
    "confidence": "medium",
    "reason": "Measured small summarize probe completed within the target range."
  },
  "concurrency": {
    "parallel_jobs": {
      "recommended": 1,
      "confidence": "high",
      "reason": "Single-worker latency is stable; no evidence yet that parallel jobs are faster on this machine."
    },
    "ollama_num_parallel": {
      "recommended": 1,
      "confidence": "medium",
      "reason": "Keep Ollama parallelism aligned with farm worker concurrency for the selected local profile."
    }
  },
  "summarize": {
    "chunk_strategy": "token",
    "chunk_tokens": 4096,
    "reduce_tokens": 4096,
    "token_safety_margin": 0.1,
    "reason": "Tokenizer is ready and measured profile uses token-aware chunking."
  },
  "evidence": {
    "benchmark": {},
    "doctor": {},
    "timing_history": {}
  },
  "warnings": [],
  "next_actions": []
}
```

Exact fields can be refined during planning. Keep it stable enough for a primary AI to consume.

### Recommendation Schema

Because this change creates a new machine-readable JSON artifact, implementation must add a tracked schema for it.

Required schema work:

- add `schemas/farm-recommendation.schema.json`
- add the schema to `schemas/index.json`
- document the schema in `schemas/README.md`
- make `farm schema validate .run/recommendations/farm-recommendation.json` auto-detect the recommendation schema
- support explicit validation by schema id or path, consistent with existing schema validation behavior
- add model-free tests for valid and invalid recommendation reports

The schema should require the stable envelope fields primary AIs and scripts need:

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

The schema may stay permissive for nested evidence metadata so future benchmark inputs can evolve without breaking older recommendation readers.

### Resource Mode Vocabulary

Recommendation output should use a small resource mode vocabulary:

| Resource Mode | Meaning |
| --- | --- |
| `gpu` | Prefer speed through GPU placement. Warn or fail when measured/known VRAM looks tight. |
| `hybrid` | Use GPU when available, but allow CPU/RAM fallback or partial offload. |
| `cpu` | Avoid VRAM pressure by recommending CPU/RAM placement, accepting slower runs. |
| `auto` | Inspect current local evidence first, then recommend one of the concrete modes above. |

Current agents already approximate this manually:

- `default` / `qwen8`: let Ollama use GPU when it can
- `qwen8-cpu` / `qwen14-cpu`: force CPU/RAM with `num_gpu: 0`
- `qwen14-hybrid`: partial GPU offload with `num_gpu: 24`

For 0020, resource mode should be recommendation vocabulary and doctor/report guidance. Full runtime enforcement, automatic agent switching, and dynamic GPU/CPU routing should remain follow-up work unless planning finds a very small safe mapping.

Markdown should summarize:

- recommended profile
- recommended resource mode
- recommended `parallel_jobs`
- recommended `OLLAMA_NUM_PARALLEL`
- recommended chunking settings
- confidence and caveats
- copyable commands for power users
- what to run next if evidence is missing

### Doctor Integration

`python qwen.py farm doctor` should remain read-only and fast by default.

Doctor should not run a benchmark automatically in this first slice. Instead it should:

- report whether a latest recommendation file exists
- show a compact recommendation summary when one exists
- tell the user/primary AI which command to run to generate or refresh measured recommendations when missing/stale
- include recommendation metadata in `doctor --json`

This keeps less technical users in the “chatbot does the hard part” path: a primary AI can run doctor, see that measured recommendations are missing, run the recommendation command, then explain or apply the result later.

### Safety And Defaults

Recommendations should be conservative:

- prefer `parallel_jobs: 1` unless measurement supports more
- prefer `OLLAMA_NUM_PARALLEL: 1` unless measurement supports more
- warn when recommending higher concurrency
- warn when benchmark evidence is missing, stale, failed, or not comparable to current agent/model/profile
- recommend `hybrid` or `cpu` when evidence suggests VRAM pressure or unknown GPU fit
- never claim hardware capability that was not measured or read from local state

### Privacy And Generated Files

Generated recommendation and benchmark artifacts should live under `.run/` by default.

No benchmark prompt/input should include user article text unless the user explicitly passes a corpus. If a user-supplied corpus is benchmarked, raw text should not be copied into tracked files.

## Acceptance Criteria

- A reproducible command exists for generating benchmark-based local farm recommendations.
- The command writes JSON and Markdown recommendation artifacts under `.run/` by default.
- The recommendation report includes status, generated timestamp, agent, model, recommended resource mode, recommended profile, recommended `parallel_jobs`, recommended `OLLAMA_NUM_PARALLEL`, summarize chunk settings, evidence, warnings, and next actions.
- The recommendation report explains confidence and reasons for each major recommendation.
- A tracked JSON Schema exists for `farm-recommendation.json`.
- The recommendation schema is registered in `schemas/index.json`.
- `schemas/README.md` documents the recommendation schema.
- `farm schema validate` auto-detects recommendation JSON artifacts.
- Explicit schema validation by schema id or path works for recommendation JSON artifacts.
- The benchmark/probe is explicitly user-invoked and bounded.
- The benchmark/probe records enough timing/evidence to support the recommendation.
- Missing Ollama/model/tokenizer prerequisites fail or degrade gracefully with clear next actions.
- Recommendations are conservative when evidence is weak or unavailable.
- `farm doctor` remains fast/read-only and does not run benchmarks automatically.
- `farm doctor` surfaces latest recommendation metadata when available.
- `farm doctor` tells users or primary AIs how to generate measured recommendations when missing.
- `doctor --json` includes machine-readable recommendation status/summary.
- Docs explain the power-user CLI flow and the primary-AI assisted setup flow.
- Docs explain `gpu`, `hybrid`, `cpu`, and `auto` resource modes as recommendation vocabulary.
- Docs explain how to interpret `parallel_jobs` vs `OLLAMA_NUM_PARALLEL`.
- Model-free tests cover recommendation selection logic, stale/missing recommendation handling, doctor JSON integration, Markdown rendering, graceful missing evidence behavior, and parser/handler behavior.
- Any model-dependent benchmark smoke is local/manual and not required in CI.
- BL-0021 and BL-0028 are marked planned/implemented as appropriate.

## Test Plan

Automated:

- recommendation scoring/selection from synthetic benchmark evidence
- conservative fallback when evidence is missing
- concurrency recommendation logic for `parallel_jobs` and `OLLAMA_NUM_PARALLEL`
- resource mode recommendation logic for `gpu`, `hybrid`, `cpu`, and `auto`
- tokenizer-ready vs tokenizer-missing chunk strategy recommendation
- stale recommendation detection
- Markdown recommendation rendering
- JSON recommendation schema validation for representative valid output
- negative schema validation for malformed recommendation output
- schema index and schema README coverage for the recommendation schema
- recommendation schema auto-detection in `farm schema validate`
- explicit recommendation schema id/path validation
- doctor report includes latest recommendation metadata without running a benchmark
- CLI parser tests for the recommendation command
- handler tests using mocked benchmark evidence, no Ollama/model calls

Verification:

```powershell
python -m unittest tests.test_qwen_farm_recommend tests.test_qwen_farm_doctor tests.test_qwen_farm_schema tests.test_qwen_cli
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

Manual/local smoke:

```powershell
python qwen.py farm doctor --json
python qwen.py farm recommend --agent default --profile local-8gb --output .run/recommendations
python qwen.py farm schema validate .run/recommendations/farm-recommendation.json
python qwen.py farm doctor
python qwen.py farm doctor --json
```

If the implementation uses an actual tiny model probe, save a local report:

```text
.run/dogfood_0020/RECOMMENDATION_SMOKE_REPORT.md
```

The report should answer:

- Did the command complete in a reasonable time?
- Did the recommendation match what we already know about the local 8GB GPU setup?
- Were concurrency recommendations conservative and understandable?
- Was the resource mode recommendation understandable?
- Did doctor make the next action obvious for a primary AI?

## Deferred To Roadmap

- Automatic config writing from recommendation output.
- CLI helpers for starting Ollama with recommended environment variables.
- Dynamic scheduler backoff after runtime failures.
- Cross-machine benchmark normalization.
- Scheduled benchmark checks on known hardware.
- Tracked aggregate benchmark history.
- Dashboards or charts.
- Multiple Ollama server pools.
- Per-agent or per-model routing.
- Full resource-aware runtime routing and automatic agent switching.
- Remote/frontier model profiles.
- Token-per-second backend metrics from Ollama eval/generation metadata.
