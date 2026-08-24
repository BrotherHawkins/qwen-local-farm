# 0021 Add Safe Recommendation Config Apply

Status: Implemented
Type: Add

## WHY

Spec 0020 made local farm recommendations measurable and inspectable, but it deliberately stopped short of changing `.qwen-farm.json`.

That was the right boundary for first contact. The next useful step is a safe, explicit way for a power user or primary AI to turn a validated recommendation report into project config.

This change implements BL-0022: automatic config writing from recommendation output.

The goal is not "let the tool silently tune my machine." The goal is:

- read a recommendation JSON artifact
- validate it
- produce a clear apply preview
- show exactly what would change in `.qwen-farm.json`
- write config only when the caller explicitly asks
- leave enough Markdown/JSON evidence for a primary AI to explain what happened

## Scope

This change adds a safe recommendation-to-config workflow:

- add a command for applying recommendation output to `.qwen-farm.json`
- make preview/dry-run the default behavior
- require explicit write intent before changing files
- validate the recommendation JSON before using it
- generate the proposed `.qwen-farm.json` through existing farm config validation helpers
- preserve existing unrelated config fields where safe
- write only farm config fields supported by the current config contract
- create a timestamped backup before overwriting an existing `.qwen-farm.json`
- write a machine-readable apply report JSON and human-readable Markdown report
- add a tracked schema for the apply report JSON
- document the workflow for power users and primary-AI assisted setup
- update BL-0022 lifecycle state as this spec progresses

Suggested command shape:

```powershell
python qwen.py farm recommend apply
python qwen.py farm recommend apply .run/recommendations/farm-recommendation.json
python qwen.py farm recommend apply --write
python qwen.py farm recommend apply --config .qwen-farm.json --output .run/recommendations
python qwen.py farm recommend apply --json
```

If nested `farm recommend apply` becomes awkward in the parser, `farm config apply-recommendation` is acceptable as long as docs and doctor/recommendation next actions point to the final command.

## Non-Goals

This change does not add:

- automatic config writes during `farm doctor`
- automatic config writes during `farm recommend`
- changing Ollama service environment variables
- writing shell profile files
- starting/stopping Ollama
- model pulls or package installs
- GPU/CPU runtime enforcement
- dynamic resource routing
- interactive prompts in CI paths
- applying recommendations with failed schema validation
- applying recommendations with `status: needs_setup`
- editing arbitrary user JSON outside the supported farm config fields

## Behavior

### Apply Command

The apply command reads a recommendation report, validates it against `schemas/farm-recommendation.schema.json`, converts accepted recommendations into `.qwen-farm.json` shape, validates the proposed config using existing config normalization/resolution helpers, and produces an apply report.

Default recommendation path:

```text
.run/recommendations/farm-recommendation.json
```

Default config path:

```text
.qwen-farm.json
```

Default report paths:

```text
.run/recommendations/farm-config-apply.json
.run/recommendations/FARM_CONFIG_APPLY.md
```

Preview is the default. The command must not write `.qwen-farm.json` unless the caller passes an explicit write flag such as `--write`.

### Proposed Config Mapping

The first implementation should map only settings already supported by `.qwen-farm.json`:

```json
{
  "profile": "local-8gb",
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

Recommended `OLLAMA_NUM_PARALLEL` and resource mode should be reported as next-step guidance, not written to `.qwen-farm.json`, because those are service/runtime placement concerns rather than current farm config fields.

If an existing config contains supported fields not mentioned by the recommendation, the command should preserve them when possible. Unsupported fields should already be rejected by existing config validation, so the command should block and explain rather than rewrite unknown data.

### Safety Rules

The command should block writes when:

- recommendation JSON cannot be read
- recommendation JSON fails schema validation
- recommendation `status` is `needs_setup`
- required recommendation sections are missing
- proposed config fails existing farm config validation
- existing config contains invalid JSON or unsupported fields

The command may allow writes with warnings when recommendation status is `ready_with_warnings`, but the apply report must make that visible.

When `--write` is supplied:

- create parent folders when needed
- if `.qwen-farm.json` already exists, write a timestamped backup next to it before changing it
- write config atomically enough for local CLI use
- report the backup path
- report `status: applied`

Without `--write`:

- do not modify `.qwen-farm.json`
- report `status: preview`
- show proposed changes and next command to apply

### Apply Report JSON

Because this change creates a new machine-readable JSON artifact, implementation must add a tracked schema for it.

Required schema work:

- add `schemas/farm-config-apply.schema.json`
- add the schema to `schemas/index.json`
- document the schema in `schemas/README.md`
- make `farm schema validate .run/recommendations/farm-config-apply.json` auto-detect the apply schema
- support explicit validation by schema id or path
- add model-free valid and invalid schema tests

Apply report JSON should be close to:

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-24T21:00:00Z",
  "status": "preview",
  "dry_run": true,
  "recommendation_path": ".run/recommendations/farm-recommendation.json",
  "config_path": ".qwen-farm.json",
  "backup_path": null,
  "recommendation": {
    "status": "ready",
    "agent": "default",
    "model": "qwen3.5:4b",
    "generated_at": "2026-08-24T20:15:50Z"
  },
  "proposed_config": {},
  "existing_config": {},
  "changes": [
    {
      "path": "summarize.chunk_strategy",
      "before": "character",
      "after": "token",
      "action": "update"
    }
  ],
  "not_applied": [
    {
      "path": "resource_mode",
      "reason": "Resource mode is recommendation guidance, not a current .qwen-farm.json field."
    }
  ],
  "warnings": [],
  "next_actions": []
}
```

Exact fields can be refined during planning, but the stable envelope should include:

- `schema_version`
- `generated_at`
- `status`
- `dry_run`
- `recommendation_path`
- `config_path`
- `backup_path`
- `recommendation`
- `proposed_config`
- `changes`
- `not_applied`
- `warnings`
- `next_actions`

### Markdown Report

Markdown should be concise and useful to humans:

- whether this was preview or applied
- recommendation source
- config target
- backup path if written
- changed fields
- intentionally not-applied fields such as `resource_mode` and `OLLAMA_NUM_PARALLEL`
- warnings
- next command to apply or verify

### Config Validation

The proposed config must be validated with existing farm config logic before preview or write succeeds.

After write, a follow-up `farm doctor` or small `farm run` should be able to resolve the new config without special handling.

## Acceptance Criteria

- A documented command exists to preview applying a recommendation to `.qwen-farm.json`.
- Preview is the default and does not modify config.
- A write requires an explicit flag such as `--write`.
- The command reads the default recommendation path when no path is supplied.
- The command accepts an explicit recommendation JSON path.
- Recommendation JSON is schema-validated before it is used.
- Recommendations with `status: needs_setup` are blocked from write.
- The proposed config includes supported profile, model, summarize, and concurrency fields.
- Resource mode and `OLLAMA_NUM_PARALLEL` are reported as not-applied guidance rather than written to config.
- Existing valid config is preserved/merged where safe.
- Existing invalid config blocks write with a clear error.
- Existing config is backed up before overwrite.
- The command writes Markdown and JSON apply reports under `.run/recommendations/` by default.
- A tracked schema exists for the apply report JSON.
- The apply report schema is registered in `schemas/index.json`.
- `schemas/README.md` documents the apply report schema.
- `farm schema validate` auto-detects apply report JSON.
- Explicit schema validation by schema id/path works for apply report JSON.
- Docs explain the power-user and primary-AI assisted flows.
- Model-free tests cover preview, write, validation, backups, blocked writes, schema validation, docs/index coverage, and CLI parsing/handling.
- No CI test requires Ollama, model calls, tokenizer downloads, or network access.
- BL-0022 is marked planned/implemented as appropriate.

## Test Plan

Automated:

- build proposed config from representative recommendation JSON
- preview mode does not write `.qwen-farm.json`
- write mode writes `.qwen-farm.json`
- write mode backs up existing config
- missing recommendation path returns clear input error
- malformed recommendation JSON returns clear input error
- recommendation schema validation failure blocks apply
- `status: needs_setup` blocks write
- `status: ready_with_warnings` produces warning-visible preview/apply behavior
- proposed config validates through existing config helpers
- invalid existing config blocks merge/write
- unsupported recommendation fields are listed in `not_applied`
- Markdown apply report rendering
- apply report JSON validates against tracked schema
- schema index/docs coverage
- schema auto-detection for apply report JSON
- explicit schema id/path validation
- CLI parser and handler coverage

Verification:

```powershell
python -m unittest tests.test_qwen_farm_recommend tests.test_qwen_farm_profiles tests.test_qwen_farm_schema tests.test_qwen_cli
python -m unittest discover -s tests
python -m compileall qwen.py src tests
git diff --check
```

Manual/local smoke:

```powershell
python qwen.py farm recommend --agent default --profile local-8gb --output .run/recommendations
python qwen.py farm recommend apply
python qwen.py farm schema validate .run/recommendations/farm-config-apply.json
python qwen.py farm recommend apply --write
python qwen.py farm doctor --json
```

If write smoke would disturb a developer's real config, run it against a temporary config path:

```powershell
python qwen.py farm recommend apply --config .run/dogfood_0021/.qwen-farm.json --write
```

Save a local smoke report if implemented:

```text
.run/dogfood_0021/CONFIG_APPLY_SMOKE_REPORT.md
```

## Deferred To Roadmap

- Interactive confirmation prompts.
- Automatic config writes from `farm doctor`.
- Automatic config writes from `farm recommend`.
- Applying Ollama service environment settings such as `OLLAMA_NUM_PARALLEL`.
- Shell profile or service manager edits.
- Full resource-aware runtime routing or automatic agent switching.
- Config migration helpers for future schema versions.
- Strict config formatting preservation.
