# 0003 Add Farm Runtime Profiles

Status: Implemented
Type: Add

## WHY

Sift currently behaves as if every user is running the same local machine profile. That was useful for dogfooding on an 8GB GPU system, but it makes the farm harder to trust on smaller CPU-only machines and leaves performance unused on larger local systems.

The farm needs an explicit runtime profile layer so:

- power users can tune model, chunking, and concurrency directly
- AI assistants can set up conservative defaults for less technical users
- every run records the resolved capacity assumptions that shaped its outputs
- local CI can keep model-free assumptions while runtime behavior becomes configurable

This change favors visible, file-backed configuration over hidden heuristics. Hardware detection is useful, but the first durable behavior should be profile resolution and run observability.

## Scope

This change adds the first farm runtime profile system:

- built-in named profiles for common local capacity tiers
- project-level config file support
- CLI overrides for selected profile fields
- deterministic config resolution
- resolved runtime config written into every farm run
- status output that shows the effective profile, model, chunk sizing, and concurrency
- documentation for power-user and AI-assistant setup paths

## Non-Goals

This change does not add:

- GPU or RAM hardware probing
- automatic benchmark-based profile selection
- Ollama model installation
- remote/frontier API execution
- live model quality scoring
- per-file adaptive chunk sizing
- dynamic mid-run profile changes
- a full `farm doctor` workflow
- a dedicated AI skill implementation

## Behavior

### Built-In Profiles

The farm defines built-in profiles for common local operating envelopes:

```text
cpu-small
local-4gb
local-8gb
local-12gb
local-24gb
custom
```

Each built-in profile resolves at least these fields:

```json
{
  "profile": "local-8gb",
  "model": "qwen3.5:4b",
  "summarize": {
    "chunk_chars": 12000,
    "reduce_chars": 12000
  },
  "concurrency": {
    "jobs": 1,
    "chunks": 1
  }
}
```

Exact numeric defaults are implementation details, but they must be conservative for the named tier and documented in user-facing help or docs.

The existing farm behavior becomes the default `local-8gb` profile unless a config file or CLI flag selects another profile.

### Config Files

The farm can read a JSON config file for project or scripted setup.

Default discovery:

```text
.sift-farm.json
```

Explicit config:

```bash
python sift.py farm run input-folder --config path/to/qwen-farm.json
```

The config file may select a profile and override individual fields:

```json
{
  "profile": "local-12gb",
  "model": "qwen3.5:8b",
  "summarize": {
    "chunk_chars": 18000,
    "reduce_chars": 16000
  },
  "concurrency": {
    "jobs": 2,
    "chunks": 1
  }
}
```

Invalid config files fail before a run starts with a clear error. Unknown fields are rejected rather than silently ignored.

### CLI Overrides

The farm run command accepts explicit overrides for common profile fields:

```bash
python sift.py farm run input-folder --profile local-12gb
python sift.py farm run input-folder --profile local-12gb --model qwen3.5:8b
python sift.py farm run input-folder --chunk-chars 18000 --parallel-jobs 2
```

CLI overrides are intended for power users and for AI assistants that have already selected a safe profile.

### Resolution Order

Runtime config resolves deterministically:

1. Start with the selected built-in profile.
2. If no profile is selected, use `local-8gb`.
3. Apply values from the discovered or explicit config file.
4. Apply CLI overrides last.
5. Validate the fully resolved config before starting work.

If a config file or CLI flag selects an unknown profile, the command fails before creating a run folder.

### Run Artifacts

Every farm run writes the final resolved config:

```text
farm-config.resolved.json
```

The artifact includes:

- selected profile name
- model
- summarize chunk/reduce sizing
- concurrency settings
- config source path, if any
- CLI override fields, if any

The artifact must not include downloaded article text, prompts beyond existing run artifacts, secrets, API keys, or unrelated environment details.

### Status Output

`farm-status.json` includes compact runtime config metadata so a primary AI can inspect a run without separately locating config files.

Markdown status output includes a short profile block, for example:

```text
Profile: local-8gb
Model: qwen3.5:4b
Chunk chars: 12000
Parallel jobs: 1
Parallel chunks: 1
```

### Assistant-Friendly Setup

The docs describe two setup paths:

- power users edit `.sift-farm.json` or pass CLI flags
- AI assistants generate or update `.sift-farm.json` after asking about machine size or using a future doctor/recommendation command

The assistant path must produce the same visible config file and resolved run artifact that power users can inspect.

## Acceptance Criteria

- The farm has built-in named profiles: `cpu-small`, `local-4gb`, `local-8gb`, `local-12gb`, `local-24gb`, and `custom`.
- The default behavior resolves to `local-8gb` when no config file or CLI profile is provided.
- A `.sift-farm.json` config file can select a profile and override model, summarize sizing, and concurrency settings.
- `--config` can point to an explicit config file.
- CLI flags can override profile, model, summarize chunk sizing, and job concurrency.
- Resolution order is deterministic and documented.
- Invalid config JSON fails before a run folder is created.
- Unknown config fields fail before a run folder is created.
- Unknown profile names fail before a run folder is created.
- Every farm run writes `farm-config.resolved.json`.
- `farm-config.resolved.json` includes profile, model, summarize sizing, concurrency, and config/override provenance.
- `farm-status.json` includes compact runtime profile metadata.
- Markdown status output shows the effective profile and key runtime settings.
- Existing model-free CI assumptions remain intact.
- Unit tests cover profile defaults, config loading, override precedence, validation failures, resolved artifact writing, and status metadata.
- User-facing docs show both power-user CLI/config usage and AI-assistant setup usage.

## Deferred To Roadmap

- `farm doctor` for machine and Ollama inspection.
- Benchmark-based profile recommendation.
- Automatic config writing from doctor output.
- Hardware-specific model installation guidance.
- Tokenizer-aware sizing.
- Per-mode profile fields beyond summarize and prompt.
- Dynamic concurrency adjustment after runtime failures.
- Remote/frontier model profiles.
