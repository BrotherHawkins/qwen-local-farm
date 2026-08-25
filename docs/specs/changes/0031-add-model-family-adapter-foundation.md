# 0031 Add Model Family Adapter Foundation

Status: Implemented
Type: Add

## WHY

The farm has deliberately centered Qwen models because they are the dogfood baseline, the known local hardware fit, and the source of the current tokenizer-aware chunking path. That focus has been useful. It keeps setup, recommendations, benchmarks, and docs concrete.

At the same time, the product direction is not "only Qwen forever." Users may want local Llama, Mistral, Gemma, Phi, DeepSeek, or custom Ollama models later. If the current Qwen assumptions stay embedded in tokenizer setup, doctor/recommend reports, runtime config, agent loading, and artifact metadata, adding those model families later will be more invasive than it needs to be.

This change adds the foundation for model-family adapters while keeping the user-facing farm commands stable:

- `farm run`
- agent IDs
- `.sift-farm.json`
- run status artifacts
- tokenizer-aware chunking behavior
- doctor/recommend/apply reports

This change implements:

- BL-0104: model family adapter foundation

It also lays groundwork for, but does not complete:

- BL-0039: additional tokenizer adapters
- BL-0023: hardware-specific model installation guidance
- BL-0034: per-agent or per-model routing across loaded models

The product principle is: Qwen remains the blessed default, but the farm should know where Qwen-specific behavior starts and ends.

## Outcome

Existing Qwen behavior remains the tested default path, while the code, agent metadata, and artifacts are refactored around a small model-family metadata layer that can describe a model's backend, family, tokenizer support, context assumptions, and support status.

## Scope

Add a first-pass model-family adapter foundation.

Preferred normalized metadata shape:

```json
{
  "model": "qwen3.5:4b",
  "backend": "ollama",
  "family": "qwen",
  "support": "tested",
  "tokenizer": {
    "strategy": "huggingface",
    "id": "Qwen/Qwen3.5-4B",
    "exact": true
  },
  "context": {
    "tokens": 8192,
    "source": "agent.options.num_ctx"
  }
}
```

The exact field names may change during planning/implementation, but the implementation should preserve these concepts:

- backend: where model calls are sent, initially `ollama`
- family: model-family label, initially inferred or configured as `qwen`
- support: tested/experimental/unknown support posture
- tokenizer strategy: whether exact local token counting is available and how it is loaded
- context tokens: effective context budget source for runtime decisions

Because this repository is private and has no external consumers, the implementation does not need to preserve older internal agent/config shapes. It may update bundled agent JSON files, tests, docs, schemas, and runtime config artifacts in one clean change.

Bundled Qwen agents should declare or normalize to model metadata equivalent to:

```json
{
  "id": "default",
  "model": "qwen3.5:4b",
  "model_family": "qwen",
  "backend": "ollama",
  "support": "tested",
  "tokenizer": {
    "strategy": "huggingface",
    "id": "Qwen/Qwen3.5-4B",
    "exact": true
  },
  "options": {
    "num_ctx": 8192
  }
}
```

Agent files may optionally declare explicit model metadata when inference is not enough:

```json
{
  "id": "llama-local",
  "name": "Experimental Llama Worker",
  "model": "llama3.1:8b",
  "model_family": "llama",
  "backend": "ollama",
  "support": "experimental",
  "tokenizer": {
    "strategy": "none"
  },
  "options": {
    "num_ctx": 4096
  }
}
```

Exact tokenizer-aware chunking should continue to work for supported Qwen mappings. Unsupported or unknown model families should fail clearly only when exact token-aware chunking is requested. Character chunking should remain available for unknown model families unless another constraint prevents the run.

## Adapter Behavior

Introduce a small registry or resolver for model metadata.

The first implementation should include:

- Qwen model-family detection for the existing supported Ollama model IDs
- an explicit Qwen tokenizer mapping equivalent to the current supported tokenizer table
- a generic unknown-family fallback
- optional agent metadata overrides for family/backend/support/tokenizer posture
- helper functions that doctor, recommend, tokenizer setup, and farm runtime can share

The registry should avoid model calls, network calls, tokenizer downloads, or Ollama requirements during pure metadata resolution.

## Status And Artifact Behavior

Resolved farm artifacts should expose model metadata directly in the resolved runtime shape.

Preferred locations:

- `farm-config.resolved.json`
- `farm-status.json` runtime metadata
- `farm status <run-id> --json`
- doctor JSON report
- recommendation JSON report where model/tokenizer readiness is discussed

Fields such as `model`, `agent`, and `runtime.model` may remain where they keep artifacts readable, but the implementation does not need to preserve duplicate older fields solely because they existed before. Prefer one clear normalized shape when a field is only internally consumed.

If new JSON fields are added to tracked artifacts, the relevant schemas must be updated in the same implementation PR.

## CLI And Config Behavior

The main CLI should not grow a new required argument for this first pass.

User-facing commands should keep their current shape:

```powershell
python sift.py farm run input --mode summarize --agent default
python sift.py farm tokenizer status
python sift.py farm doctor --json
python sift.py farm recommend --json
```

Explicit model metadata should be accepted through agent JSON files. Config-level overrides may be added only if they can be validated simply and documented clearly.

This spec does not require renaming:

- the repository
- `sift.py`
- `SIFT_MODEL`
- existing Qwen agent IDs
- existing Qwen docs sections

Naming cleanup can happen later if the product outgrows the Qwen-centered entrypoint.

## Doctor And Recommend Behavior

Doctor should report the normalized model metadata for the selected agent/model.

Recommendation logic should keep Qwen as the tested default and clearly label non-Qwen or unknown families as experimental/unknown unless they have explicit adapter metadata and dogfood evidence.

If an unknown model family is selected:

- doctor should not fail solely because the family is unknown
- tokenizer readiness should report unsupported/unknown exact tokenizer support
- recommend should prefer conservative character chunking unless exact tokenizer support is available
- user-facing guidance should say the model can still be used through Ollama, but quality/performance/tokenizer behavior is not yet dogfood-backed

## Non-Goals

This change does not add:

- new bundled non-Qwen agents
- Ollama model pulls
- automatic model installation
- model-family quality benchmarks
- automatic model-size upgrades or downgrades
- automatic agent switching
- remote/frontier model execution
- multiple Ollama server pools
- exact tokenizer adapters for every model family
- semantic differences in summarize prompts by family
- repo or CLI rename away from Qwen
- hard CI requirements for Ollama, local models, tokenizer downloads, or network access

## Acceptance Criteria

- Bundled Qwen agents are updated or normalized to the new model-family metadata shape.
- Existing `farm run`, `farm doctor`, `farm recommend`, and `farm tokenizer` command spelling remains stable for the current product workflow.
- A normalized model metadata object can be resolved for each bundled Qwen agent.
- A normalized model metadata object can be resolved for an unknown Ollama model without crashing.
- Agent-level explicit family/backend/support/tokenizer metadata is validated if supported by the implementation.
- Qwen tokenizer-aware chunking still works through the new adapter metadata.
- Token-aware chunking for an unsupported tokenizer still fails before starting jobs with a clear message.
- Character chunking remains available for unknown model families when the rest of the run config is valid.
- Doctor JSON includes model-family/backend/support/tokenizer capability metadata.
- Doctor Markdown renders enough model-family metadata for a human or primary AI to understand whether the selected model is tested or experimental.
- Recommendation JSON includes model-family/backend/support/tokenizer capability metadata where model/tokenizer guidance is produced.
- Recommendation Markdown or command output labels unknown/non-tested families clearly.
- `farm-config.resolved.json` records normalized model metadata or an equivalent additive structure.
- `farm-status.json` runtime metadata records normalized model metadata or an equivalent additive structure.
- Status/result artifacts use one clear normalized model metadata shape; internal duplicate fields may be removed if all code/tests/docs are updated together.
- Relevant JSON schemas are updated for any new artifact fields.
- README and AI usage docs explain that Qwen is the tested default and other families are extension paths.
- Tests stay model-free and do not require Ollama, downloaded models, tokenizer downloads, or network.
- BL-0104 is marked planned/implemented as lifecycle advances.

## Tests

Add model-free tests for:

- Qwen model metadata resolution from bundled agent files
- unknown Ollama model metadata fallback
- explicit agent metadata validation
- invalid family/backend/support/tokenizer metadata rejection where validation applies
- Qwen tokenizer mapping through the adapter registry
- unsupported tokenizer failure for token-aware chunking
- character chunking support for unknown model families
- doctor JSON/Markdown model metadata rendering
- recommendation JSON/Markdown model metadata rendering
- resolved runtime config model metadata persistence
- farm status model metadata persistence
- schema validation for updated JSON artifacts
- existing Qwen-focused behavior after the refactor

Run:

```powershell
python -m src.qwen_spec_guard
python -m unittest tests.test_qwen_farm_tokenizer tests.test_qwen_farm_profiles tests.test_qwen_farm_doctor tests.test_qwen_farm_recommend tests.test_qwen_farm tests.test_qwen_farm_schema
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

## Manual Verification

Use ignored artifacts only:

```text
.run/dogfood_0031/
```

Suggested model-free/manual smoke:

1. Create a temporary experimental agent under `.run/dogfood_0031/agents/` or a temp test root with:

```json
{
  "id": "experimental-llama",
  "model": "llama3.1:8b",
  "model_family": "llama",
  "backend": "ollama",
  "support": "experimental",
  "tokenizer": {
    "strategy": "none"
  },
  "options": {
    "num_ctx": 4096
  }
}
```

2. Run doctor/recommend paths with fake or no Ollama dependency where possible.
3. Run a small farm test with a fake model processor and the experimental agent metadata.
4. Inspect resolved config/status JSON and Markdown to confirm the model-family metadata is visible.
5. Confirm Qwen dogfood-lite inputs still run through the normal user-facing commands if a real local smoke is desired.

## Deferred To Backlog

- BL-0039: additional tokenizer adapters
- BL-0023: hardware-specific model installation guidance
- BL-0026: remote/frontier model profiles
- BL-0034: per-agent or per-model routing across loaded models
- BL-0073: automatic model-size upgrades or downgrades
- BL-0074: automatic agent switching based on resource mode
- BL-0105: non-Qwen dogfood benchmark matrix
- BL-0106: product naming and CLI alias review if support becomes broadly model-agnostic

## Lifecycle

When this spec is accepted:

- mark this spec `Accepted`
- add an implementation plan under `docs/specs/plans/`
- update `SPEC_DASHBOARD.md`
- mark BL-0104 planned in `docs/backlog.md`
- add deferred follow-ups as open backlog rows if still out of scope

When implementation is complete in the PR:

- mark this spec `Implemented`
- mark the plan `Implemented`
- update `SPEC_DASHBOARD.md`
- mark BL-0104 implemented in `docs/backlog.md`
