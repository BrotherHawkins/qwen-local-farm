# 0033 Add Hardware-Specific Model Install Guidance

Status: Implemented
Type: Add

## WHY

Sift can already inspect a machine with `farm doctor`, benchmark a small local probe with `farm recommend`, and safely preview/write farm config with `farm recommend apply`. That gives power users enough raw information, but less technical users still need help answering the practical question:

```text
What should I install on this machine, and which Sift agent/profile should I use first?
```

BL-0023 exists because the current docs and reports say what is present, but they do not provide a clear hardware-specific installation path. A primary AI can infer a lot from doctor and recommendation output, but Sift should make the safe path explicit, beginner-readable, and machine-readable enough for AI skills and scripts to consume without guessing.

The product posture should stay conservative: Sift may recommend model install commands, but it should not silently download models, install Ollama, change global environment settings, or edit config without an explicit user action.

## Scope

Add first-class hardware-specific model installation guidance for local Ollama-backed Sift usage.

The first pass should include:

- a human-readable model installation guide
- a machine-readable model installation guidance JSON artifact or catalog
- a tracked schema for that new JSON shape
- model-free validation tests for the guide/catalog/schema
- links from the README, platform notes, AI usage docs, and relevant skills
- doctor/recommend output that points to the guidance and includes the most relevant install next actions when possible
- beginner-friendly commands for installing/pulling the recommended local models
- clear warnings for CPU-only, low-VRAM, hybrid/offload, and large-model paths

The guidance should cover the hardware bands Sift already talks about:

- CPU-only or unknown GPU
- about 4 GB VRAM
- about 8 GB VRAM
- about 12 GB VRAM
- about 24 GB VRAM
- larger RAM/VRAM machines
- Apple Silicon/unified memory as a special "measure and smoke test" path rather than NVIDIA-style VRAM

The guidance should describe the relationship between:

- Ollama install
- `ollama pull <model>`
- Sift agents
- runtime profiles
- resource modes
- tokenizer setup
- smoke tests
- recommendation apply preview/write

## Non-Goals

- No automatic model download during `farm doctor`.
- No automatic Ollama install.
- No automatic global environment variable changes.
- No new GUI or interactive wizard.
- No promise that Sift can exactly predict every GPU fit before a smoke test.
- No automatic agent/model switching based on hardware.
- No remote/frontier model setup.
- No support claim for non-Qwen models beyond the existing experimental adapter posture.

## Behavior

### Human Guide

Add a concise guide, likely:

```text
docs/model-installation.md
```

The guide should help a less technical user or primary AI choose a starting point:

| Machine Shape | Suggested First Path | Notes |
| --- | --- | --- |
| CPU-only or unknown GPU | `cpu-small` plus CPU agent | Slow but avoids VRAM assumptions. |
| Around 4 GB VRAM | small/default model only after smoke test | Keep chunk/context conservative. |
| Around 8 GB VRAM | `default` / `qwen3.5:4b` with `local-8gb` | Current tested comfortable default. |
| Around 12 GB VRAM | 4B default or 8B trial | Measure before raising concurrency. |
| Around 24 GB VRAM | 8B or 14B experiments | Larger models still need timing/quality checks. |
| Apple Silicon/unified memory | use doctor/recommend and smoke tests | Treat memory differently than NVIDIA VRAM. |

The guide should include exact commands such as:

```bash
python sift.py farm doctor --json
ollama pull qwen3.5:4b
python sift.py farm recommend --agent default --profile local-8gb
python sift.py farm recommend apply
python sift.py farm recommend apply --write
python sift.py farm run .run/smoke/input --mode summarize --output .run/smoke/output
```

Where commands install packages, download models, or write durable config, the docs should clearly say the user should approve that action first.

### Machine-Readable Guidance

Add a small JSON guidance catalog, likely:

```text
docs/model-installation.json
schemas/model-installation.schema.json
```

The catalog should not try to encode every possible hardware reality. It should provide stable bands and commands that a primary AI can read and explain.

Example shape:

```json
{
  "schema_version": 1,
  "default_band": "local-8gb",
  "hardware_bands": [
    {
      "id": "local-8gb",
      "label": "About 8 GB VRAM",
      "recommended_profile": "local-8gb",
      "recommended_agent": "default",
      "recommended_model": "qwen3.5:4b",
      "resource_mode": "auto",
      "install_commands": ["ollama pull qwen3.5:4b"],
      "setup_commands": [
        "python sift.py farm doctor --json",
        "python sift.py farm recommend --agent default --profile local-8gb"
      ],
      "warnings": [
        "Start with parallel_jobs 1 until a small smoke test passes."
      ]
    }
  ]
}
```

The schema should validate the fields that scripts and AI skills are expected to rely on:

- `schema_version`
- hardware band `id`
- human label
- recommended profile
- recommended agent
- recommended model
- resource mode
- install commands
- setup/check commands
- warnings or notes

The catalog should avoid user-specific paths and should not include command strings that write config unless they are clearly marked as preview or explicit-write actions.

### Doctor And Recommend Integration

`farm doctor` should remain read-only. It may add a compact guidance pointer and next-action object such as:

```json
{
  "model_installation_guidance": {
    "guide_path": "docs/model-installation.md",
    "catalog_path": "docs/model-installation.json",
    "suggested_band": "local-8gb",
    "recommended_agent": "default",
    "recommended_model": "qwen3.5:4b",
    "missing_models": ["qwen3.5:4b"],
    "safe_next_commands": ["ollama pull qwen3.5:4b"]
  }
}
```

If the machine cannot be confidently classified, doctor should say so and direct the user to `farm recommend` plus a tiny smoke test rather than overstating certainty.

`farm recommend` may include the same guide/catalog links and model install guidance in its JSON and Markdown output. It should distinguish:

- already installed models
- missing recommended models
- optional larger models
- commands that only inspect
- commands that download
- commands that write config

### AI Skill Integration

The setup skill should tell an AI assistant to consult the hardware guide before recommending model pulls. It should make the approval boundary clear:

- ask before installing Ollama
- ask before `ollama pull`
- ask before tokenizer dependency install
- ask before `farm recommend apply --write`
- ask before changing persistent service environment settings

The operator skill can mention the guide as a resource when a run is failing due to model availability, resource pressure, or unsuitable profile/model choices.

### Validation And Sync

Add model-free checks that keep this guidance from drifting:

- the JSON catalog validates against its schema
- every catalog `recommended_agent` exists under `agents/`
- every catalog `recommended_profile` is a known runtime profile
- every catalog `recommended_model` matches the selected agent model unless deliberately marked as an alternate
- every Sift command in the guide/catalog parses with `sift.parse_args()` after safe placeholder substitution
- docs and skills mention the guide path
- the guide does not use stale renamed commands or config names

These tests should not install Ollama, pull models, call Ollama, download tokenizers, or require network access.

## Acceptance Criteria

- `docs/model-installation.md` exists and explains the recommended model/profile/resource-mode path by hardware band.
- A machine-readable model installation guidance JSON artifact exists.
- A tracked JSON schema validates the guidance artifact.
- `schemas/index.json` includes the new schema.
- README, platform notes, AI usage docs, and setup/operator skills link to or mention the model installation guide where relevant.
- `farm doctor` output includes a read-only pointer to the model installation guide and, when possible, a suggested hardware band or safe next action.
- `farm recommend` output includes relevant model-install guidance without downloading models or writing config.
- The guidance clearly marks commands that download models or write config as approval-required.
- The guidance preserves the existing model-free CI posture.
- Tests verify that guide/catalog Sift commands parse without executing model work.
- Tests verify that catalog agents, models, profiles, and schema references stay in sync with tracked repo files.
- Tests verify that no stale pre-rebrand command/config names appear in the new guidance.
- `python -m unittest discover -s tests` passes.
- `python -m src.sift_spec_guard` passes.

## Deferred To Roadmap

- Automatic Ollama/model installation helpers.
- A first-run interactive setup wizard that asks questions and executes approved steps.
- Exact VRAM fit prediction beyond conservative guidance and smoke tests.
- Cross-machine benchmark normalization for stronger hardware recommendations.
- Automatic model-size upgrades/downgrades or agent switching.
- Platform-specific skill installation helpers beyond linking the guide from existing skills.
