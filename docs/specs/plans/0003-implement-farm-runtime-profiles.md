# 0003 Implement Farm Runtime Profiles

Status: Implemented
Change Spec: [0003 Add Farm Runtime Profiles](../changes/0003-add-farm-runtime-profiles.md)

## WHY

The farm should run predictably across smaller CPU-only machines, the original 8GB GPU dogfood system, and larger local systems without hiding important capacity assumptions.

This plan implements the accepted runtime profile contract before adding hardware probing. Power users get explicit CLI/config controls, and AI assistants get a visible config surface they can create, inspect, and explain for less technical users.

## Scope

Planned:

- built-in runtime profiles for common local tiers
- `.sift-farm.json` discovery and explicit `--config` loading
- CLI overrides for profile, model, chunk sizing, and concurrency
- deterministic resolved config model
- validation failures before run folder creation
- `farm-config.resolved.json` per run
- compact runtime profile metadata in `farm-status.json`
- profile block in Markdown status output
- user docs for CLI/config and assistant-operated setup
- model-free unit tests

## Non-Goals

Deferred:

- GPU/RAM hardware probing
- `farm doctor`
- benchmark-based profile recommendation
- automatic model installation
- remote/frontier API model profiles
- tokenizer-aware budgets
- adaptive runtime tuning after failures
- dedicated Codex skill implementation

## Implementation Plan

### 1. Add Runtime Profile Helpers

Add a small module for profile behavior, likely `src/sift_farm_profiles.py`.

The module should define:

- built-in profile names and defaults
- typed or dictionary-based resolved config objects
- config file parsing
- override application
- validation helpers
- serialization for run artifacts and status metadata

Keep this layer deterministic and independent of Ollama so CI remains model-free.

### 2. Define Profile Defaults

Add conservative defaults for:

- `cpu-small`
- `local-4gb`
- `local-8gb`
- `local-12gb`
- `local-24gb`
- `custom`

Map the current behavior to the default `local-8gb` profile. Avoid tuning perfection in this spec; defaults only need to be documented, conservative, and internally consistent.

### 3. Add Config Loading

Support default discovery of:

```text
.sift-farm.json
```

Support explicit config path:

```bash
python sift.py farm run input-folder --config path/to/qwen-farm.json
```

Validation should reject:

- invalid JSON
- unknown top-level fields
- unknown nested fields
- unknown profile names
- invalid numeric values
- config files that do not parse to an object

Validation failures should happen before run directory creation.

### 4. Add CLI Overrides

Extend `farm run` with:

- `--config`
- `--profile`
- `--model`
- `--chunk-chars`
- `--reduce-chars`
- `--parallel-jobs`
- `--parallel-chunks`

CLI overrides apply after built-in defaults and config-file values.

Keep existing invocations working without requiring new flags.

### 5. Wire Resolved Config Into Farm Run

Resolve runtime config before creating farm state.

Use resolved values for:

- model selection
- summarize chunk sizing
- reduce sizing
- concurrency fields, even if execution remains sequential in this spec

If concurrency fields are recorded but not yet used for parallel execution, document that they are capacity metadata and future scheduling inputs.

### 6. Write Run Artifacts

Every run writes:

```text
farm-config.resolved.json
```

The artifact should include:

- profile
- model
- summarize sizing
- concurrency
- config source path, if present
- CLI override field names, if present

Do not include secrets, environment dumps, downloaded source text, or unrelated machine details.

### 7. Extend Status Metadata

Add compact runtime config metadata to `farm-status.json`.

Update Markdown status output to include a small block with:

- profile
- model
- chunk chars
- reduce chars
- parallel jobs
- parallel chunks

Keep existing status tables readable and stable.

### 8. Update Docs

Update README and AI usage docs with:

- default behavior
- named profile examples
- `.sift-farm.json` example
- CLI override examples
- AI-assistant setup guidance
- note that hardware probing is deferred to a future doctor workflow

### 9. Test Plan

Automated tests:

- default resolution returns `local-8gb`
- each built-in profile resolves successfully
- config file overrides profile defaults
- CLI overrides beat config values
- invalid JSON fails before run creation
- unknown fields fail before run creation
- unknown profile fails before run creation
- resolved config artifact is written
- status JSON includes compact runtime metadata
- Markdown status includes profile block
- summarize chunking uses resolved chunk/reduce values
- existing no-config farm run behavior remains compatible

Manual verification:

```bash
python -m unittest discover -s tests
python sift.py farm run <small-folder> --output .run/manual-profiles-default --mode summarize
python sift.py farm status <run-id>
python sift.py farm run <small-folder> --output .run/manual-profiles-override --mode summarize --profile local-12gb --chunk-chars 18000
```

## Verification Plan

Before PR:

```bash
python -m unittest discover -s tests
python -m compileall sift.py src tests
```

Optional manual smoke test:

```bash
python sift.py farm run .run/dogfood3/articles-text --output .run/manual-profiles-dogfood --mode summarize --agent default --profile local-8gb
```

The optional dogfood run is useful but not required for the implementation PR if model-free tests cover config resolution and artifact output.

## Acceptance Checklist

- [x] Change spec exists.
- [x] Human accepted the behavior target.
- [x] Human accepted the implementation plan.
- [x] Built-in profiles exist and are documented.
- [x] Default farm behavior resolves to `local-8gb`.
- [x] Config file discovery and `--config` work.
- [x] CLI overrides work and apply last.
- [x] Invalid config/profile values fail before run creation.
- [x] Every run writes `farm-config.resolved.json`.
- [x] Status JSON includes compact runtime metadata.
- [x] Markdown status includes effective profile settings.
- [x] Existing no-config farm runs remain compatible.
- [x] Unit tests pass.
- [x] Compile check passes.
