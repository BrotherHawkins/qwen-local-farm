# 0022 Add Resource-Aware Runtime Modes

Status: Implemented
Type: Add

## WHY

The farm now has runtime profiles, doctor reports, measured recommendations, and safe recommendation-to-config apply. That gives both power users and primary AI assistants a way to choose reasonable local settings, but resource placement is still only guidance.

The project needs a first-class runtime resource mode so users can say what kind of machine pressure they want:

- `gpu`: prefer speed and GPU placement
- `hybrid`: allow partial GPU offload plus CPU/RAM fallback
- `cpu`: avoid VRAM pressure even if slower
- `auto`: let the farm resolve a conservative concrete mode from current config, selected agent, profile, and recommendation evidence

This change implements BL-0072: resource-aware runtime mode and routing.

The goal is not to magically optimize every machine. The goal is to make resource intent explicit, validated, visible in artifacts, and safe enough for both CLI users and chatbot-assisted users.

## Scope

This change adds first-class resource mode support:

- add `resource_mode` to farm runtime config
- add CLI overrides for resource mode on farm run, doctor, recommend, and recommendation apply flows where useful
- validate resource mode values: `auto`, `gpu`, `hybrid`, and `cpu`
- resolve `auto` to a concrete effective resource mode using deterministic local evidence
- enforce CPU placement by applying `num_gpu: 0` to the effective agent options
- reject obvious conflicts, such as `--resource-mode gpu` with an agent that explicitly forces `num_gpu: 0`
- preserve existing power-user agent selection
- update recommendation apply so `resource_mode` is written to `.qwen-farm.json` instead of only listed as not-applied guidance
- include requested and effective resource mode in resolved run config, status JSON, timing/dogfood identity where applicable, and doctor JSON/Markdown
- document the power-user CLI path and the primary-AI assisted setup path
- update affected schemas when existing JSON artifacts gain stable resource-mode fields
- update BL-0072 lifecycle state as this spec progresses

Suggested command shape:

```powershell
python qwen.py farm run articles --mode summarize --resource-mode auto
python qwen.py farm run articles --mode summarize --resource-mode cpu
python qwen.py farm run articles --mode summarize --agent qwen14-hybrid --resource-mode hybrid
python qwen.py farm doctor --resource-mode auto
python qwen.py farm recommend --resource-mode auto
python qwen.py farm recommend apply --write
```

Suggested config shape:

```json
{
  "profile": "local-8gb",
  "resource_mode": "auto",
  "model": "qwen3.5:4b",
  "summarize": {
    "chunk_strategy": "token",
    "chunk_tokens": 4096,
    "reduce_tokens": 4096,
    "token_safety_margin": 0.1
  },
  "concurrency": {
    "jobs": 1,
    "chunks": 1
  }
}
```

## Non-Goals

This change does not add:

- multiple Ollama server pools
- starting, stopping, or reconfiguring the Ollama service
- writing `OLLAMA_NUM_PARALLEL` to shell profiles or service managers
- automatic model installation or model pulls
- automatic model-size upgrades or downgrades
- dynamic scheduler backoff after runtime failures
- mid-run resource-mode changes
- benchmark runs inside `farm doctor`
- remote/frontier model routing
- GPU memory reservation
- precise VRAM fit guarantees
- semantic quality selection between models
- interactive prompts in CI paths

## Behavior

### Resource Mode Vocabulary

The farm recognizes four resource modes:

| Mode | Meaning |
| --- | --- |
| `gpu` | Prefer speed through GPU placement. Fail early on obvious CPU-forced agent conflicts. |
| `hybrid` | Allow partial GPU offload plus CPU/RAM fallback. Fail early on obvious CPU-forced agent conflicts. |
| `cpu` | Avoid VRAM pressure by forcing the effective agent options to include `num_gpu: 0`. |
| `auto` | Resolve to a concrete effective mode using deterministic local evidence. |

`auto` is the only mode that may remain user-friendly for less technical users. It should never pretend to know more than it does. When evidence is weak, it should resolve conservatively and explain the reason in artifacts.

### Config Resolution

Resource mode participates in the existing deterministic config resolution order:

1. Start with the selected built-in profile.
2. Apply discovered or explicit `.qwen-farm.json`.
3. Apply CLI overrides.
4. Load the selected agent.
5. Resolve requested resource mode to an effective resource mode.
6. Apply safe agent option overrides for the effective mode.
7. Validate the fully resolved runtime config before starting work.

Built-in profiles should include a default requested resource mode:

| Profile | Default requested resource mode |
| --- | --- |
| `cpu-small` | `cpu` |
| `local-4gb` | `auto` |
| `local-8gb` | `auto` |
| `local-12gb` | `auto` |
| `local-24gb` | `auto` |
| `custom` | `auto` |

### Auto Resolution

The first implementation resolves `auto` without model calls or long probes.

Acceptable deterministic evidence:

- selected profile
- selected agent options
- recommendation JSON if explicitly supplied or already applied to config
- local doctor hardware facts already available without slow work

Initial rules should be conservative:

- if selected profile is `cpu-small`, effective mode is `cpu`
- if selected agent options explicitly set `num_gpu: 0`, effective mode is `cpu`
- if selected agent options explicitly set positive `num_gpu`, effective mode is `hybrid`
- otherwise, effective mode is `gpu` for GPU-capable local profiles and `cpu` for CPU profile

If implementation can cheaply inspect VRAM via already-existing status/doctor helpers, it may choose `hybrid` instead of `gpu` when VRAM evidence is missing or tight. It must explain that decision in the resolved config or doctor report.

### Enforcement

The farm should enforce only what it can do safely and locally:

- `cpu` sets the effective agent options `num_gpu: 0` before Ollama calls are made.
- `gpu` does not set a magic GPU value; it allows Ollama/default agent placement unless the selected agent explicitly blocks GPU usage.
- `hybrid` allows a positive `num_gpu` agent setting when present, or otherwise allows Ollama/default placement.
- `auto` resolves to one of `gpu`, `hybrid`, or `cpu` before model calls.

Conflict handling:

- `--resource-mode gpu` with an explicitly CPU-forced agent fails before creating a farm run.
- `--resource-mode hybrid` with an explicitly CPU-forced agent fails before creating a farm run.
- `--resource-mode cpu` may override any selected agent by forcing `num_gpu: 0`.
- `--resource-mode auto` does not fail for CPU-forced agents; it resolves to `cpu`.

The error text should explain the selected agent, requested resource mode, conflicting option, and a copyable remedy.

### Agent Selection

This change preserves the existing explicit agent model:

- users may still pass `--agent qwen8`, `--agent qwen8-cpu`, `--agent qwen14-hybrid`, or other agent ids
- `resource_mode` adjusts or validates placement for the selected agent
- the farm does not silently switch from one model size to another
- automatic model or agent switching remains a follow-up

This keeps power users in control and avoids surprising quality/performance changes.

### Resolved Artifacts

Every farm run already writes:

```text
farm-config.resolved.json
farm-status.json
FARM_STATUS.md
```

After this change, resolved runtime metadata should include:

```json
{
  "resource_mode": {
    "requested": "auto",
    "effective": "gpu",
    "source": "profile",
    "reason": "Selected profile local-8gb allows GPU placement and no CPU-forced agent option was present."
  }
}
```

Exact field names may be refined during planning, but the stable values must show:

- requested mode
- effective mode
- source/provenance
- reason
- any agent option override applied by the farm

Status and timing/dogfood identity artifacts should include enough resource-mode metadata for a primary AI to compare runs and spot “this got slower because it used CPU mode.”

### Recommendation Apply

Spec 0021 intentionally left recommendation `resource_mode` as not-applied guidance because config did not support it yet.

After this change:

- `farm recommend apply` should write supported `resource_mode` values into `.qwen-farm.json`
- apply reports should show the resource-mode change in `changes`
- `resource_mode` should no longer appear in `not_applied` when it is valid and supported
- `OLLAMA_NUM_PARALLEL` remains not-applied guidance
- recommendations with invalid resource mode still fail schema/config validation

### Doctor And Recommend

`farm doctor` remains read-only and fast.

Doctor should report:

- requested resource mode
- effective resource mode
- selected agent and model
- whether CPU enforcement would apply
- conflicts or warnings
- next commands for power users and primary AIs

`farm recommend` should continue recommending a resource mode, but now its output and next actions should mention that `farm recommend apply --write` can persist the mode to config.

### Schema Work

This change should not create a brand-new standalone JSON artifact unless implementation discovers a clear need.

Because existing JSON artifacts gain stable resource-mode fields, implementation must update affected tracked schemas:

- status/run schemas if runtime metadata shape changes
- doctor schema if doctor report shape changes
- recommendation/apply schemas if apply behavior or report fields change
- any post-run package schemas that capture compact runtime identity

If implementation adds a new JSON artifact, it must add:

- a tracked schema under `schemas/`
- an entry in `schemas/index.json`
- documentation in `schemas/README.md`
- auto-detection support in `farm schema validate` when practical
- model-free schema tests

## Acceptance Criteria

- `.qwen-farm.json` accepts a validated `resource_mode` field with values `auto`, `gpu`, `hybrid`, or `cpu`.
- Farm run CLI accepts `--resource-mode`.
- Runtime config resolution includes requested and effective resource mode.
- `auto` resolves deterministically before model calls.
- `cpu` mode forces effective agent options to include `num_gpu: 0`.
- `gpu` mode fails before run creation when the selected agent explicitly forces CPU with `num_gpu: 0`.
- `hybrid` mode fails before run creation when the selected agent explicitly forces CPU with `num_gpu: 0`.
- `auto` with a CPU-forced agent resolves to `cpu` without failing.
- Resource mode never silently changes the selected model id.
- Resource mode never silently switches to a different agent id in this first slice.
- Run artifacts expose requested/effective resource mode and the reason for the decision.
- `farm status` Markdown and JSON make resource mode visible for run inspection.
- Timing/dogfood identity records include resource mode where they already capture runtime identity.
- `farm doctor` reports resource mode resolution without running benchmarks.
- `farm recommend` docs/next actions explain that resource mode can now be applied to config.
- `farm recommend apply` writes valid resource mode recommendations to `.qwen-farm.json`.
- `farm recommend apply` keeps `OLLAMA_NUM_PARALLEL` as not-applied guidance.
- Invalid resource modes fail before a run starts or config is written.
- Existing valid configs without `resource_mode` continue to work and resolve through profile defaults.
- Existing docs explain `gpu`, `hybrid`, `cpu`, and `auto` as runtime modes, not merely recommendation vocabulary.
- Affected tracked JSON schemas are updated.
- Model-free tests cover config validation, CLI parsing, auto resolution, CPU enforcement, conflict failures, resolved artifacts, doctor output, recommendation apply behavior, and schema validation.
- No CI test requires Ollama, model calls, tokenizer downloads, GPU hardware, or network access.
- BL-0072 is marked planned/implemented as appropriate.

## Test Plan

Automated:

- config accepts each valid resource mode
- config rejects unknown resource mode
- CLI parser accepts `farm run --resource-mode`
- runtime override precedence handles profile, config, and CLI resource mode
- `cpu` mode applies `num_gpu: 0` to effective agent options
- `gpu` mode rejects a CPU-forced selected agent before run creation
- `hybrid` mode rejects a CPU-forced selected agent before run creation
- `auto` resolves `cpu-small` to `cpu`
- `auto` resolves CPU-forced agents to `cpu`
- `auto` resolves positive `num_gpu` agents to `hybrid`
- default local profile behavior remains compatible with existing runs
- resolved config artifact includes resource-mode metadata
- status JSON and Markdown include resource-mode metadata
- doctor JSON and Markdown include resource-mode metadata
- recommendation apply writes `resource_mode` to proposed config
- recommendation apply still lists `OLLAMA_NUM_PARALLEL` as not-applied
- affected schemas validate representative artifacts
- malformed resource-mode artifact fields produce schema errors

Verification:

```powershell
python -m unittest tests.test_qwen_farm_profiles tests.test_qwen_farm tests.test_qwen_farm_doctor tests.test_qwen_farm_recommend tests.test_qwen_farm_schema tests.test_qwen_cli
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

Manual/local smoke:

```powershell
python qwen.py farm doctor --resource-mode auto --json
python qwen.py farm recommend --agent default --profile local-8gb --resource-mode auto --output .run/recommendations
python qwen.py farm recommend apply --config .run/dogfood_0022/.qwen-farm.json --write
python qwen.py farm run .run/dogfood_lite/articles-text --output .run/dogfood_0022/gpu --mode summarize --agent default --resource-mode gpu
python qwen.py farm run .run/dogfood_lite/articles-text --output .run/dogfood_0022/cpu --mode summarize --agent default --resource-mode cpu
python qwen.py farm status <run-id> --json
```

Save local smoke notes under:

```text
.run/dogfood_0022/RESOURCE_MODE_SMOKE_REPORT.md
```

The smoke report should answer:

- Did `auto`, `gpu`, and `cpu` resolve as expected?
- Did CPU mode clearly show `num_gpu: 0` in effective metadata?
- Did status/doctor make resource mode visible enough for a primary AI?
- Did recommendation apply persist `resource_mode` and keep `OLLAMA_NUM_PARALLEL` guidance-only?
- Did CPU mode get slower in a way timing artifacts made obvious?

## Deferred To Roadmap

- Multiple Ollama server pools.
- Automatic model-size upgrades or downgrades.
- Automatic agent switching based on resource mode.
- Dynamic scheduler backoff after memory or timeout failures.
- Runtime retry on a different resource mode after failure.
- Starting/stopping Ollama with selected resource settings.
- Persisting or applying `OLLAMA_NUM_PARALLEL`.
- GPU memory reservation or exact VRAM fit checks.
- Cross-machine resource benchmark normalization.
- Remote/frontier model routing.
