# 0012 Add Run-ID Lookup For Post-Run Helpers

Status: Implemented
Type: Add

## WHY

Post-run helper commands now make useful artifacts from existing farm runs, but they still require the caller to provide the full run directory path. That is awkward for humans and primary AIs because `farm run`, `farm list`, and `farm status` already teach users to think in run IDs.

The farm should let post-run helpers accept the same run ID a caller sees in status output while preserving the current path-based workflow for scripts.

This change favors:

- less copy-paste friction after `farm list` or `farm status`
- a shared run-reference resolver instead of command-specific lookup logic
- exact, deterministic lookup through the existing run index
- preserving current full-path command behavior
- model-free tests and no changes to farm run execution

## Scope

This change adds run-reference lookup to post-run helper commands that read an existing farm run:

- add a shared resolver for a run reference
- accept either an existing filesystem path or an exact known run ID
- resolve run IDs through the farm run index
- use path semantics first when the supplied reference points to an existing path
- preserve current behavior for full absolute and relative run directory paths
- update CLI help/docs to describe `<run-ref>` as either a run directory or run ID
- apply the resolver to:
  - `farm snippets pack <run-ref>`
  - `farm synthesis bundle <run-ref>`
  - `farm dogfood record <run-ref>`
- update BL-0058 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- partial run ID matching
- fuzzy matching
- labels or aliases for runs
- lookup of runs outside the existing run index and known farm result folders
- changes to run directory naming or storage layout
- changes to `farm run`, `farm list`, or `farm status` behavior
- cross-run helper behavior
- new model calls
- a JSON status mode

## Behavior

### CLI Shape

Existing path-based commands remain valid:

```powershell
python qwen.py farm snippets pack .run/dogfood_lite/farm-results/farm-run-2026-08-24-120000-abcd --label lite-pack
python qwen.py farm synthesis bundle .run/dogfood_lite/farm-results/farm-run-2026-08-24-120000-abcd --label lite-bundle
python qwen.py farm dogfood record .run/dogfood_lite/farm-results/farm-run-2026-08-24-120000-abcd --label lite-record
```

The same commands should also accept the known run ID:

```powershell
python qwen.py farm snippets pack farm-run-2026-08-24-120000-abcd --label lite-pack
python qwen.py farm synthesis bundle farm-run-2026-08-24-120000-abcd --label lite-bundle
python qwen.py farm dogfood record farm-run-2026-08-24-120000-abcd --label lite-record
```

The parser may keep its internal argument name as `run_dir` for compatibility, but user-facing help and docs should call the positional value `<run-ref>` where practical.

### Resolution Rules

When a helper receives a run reference:

1. If the reference resolves to an existing filesystem path, use that path.
2. Otherwise, look for an exact run ID match in the existing farm run index.
3. If an indexed path exists and contains `farm-status.json`, use that path.
4. If the run ID is known but its path is missing or invalid, fail with a clear stale-index message.
5. If the reference is neither an existing path nor a known run ID, fail with a clear unknown-run message that suggests `farm list`.

Path-first behavior avoids surprising scripts that happen to use a directory name that resembles a run ID.

### Diagnostics

Failures should be actionable. Error text should distinguish:

- unknown run reference
- run ID known but indexed run directory no longer exists
- run directory exists but is missing `farm-status.json`

The command should not fall back to broad filesystem crawling when exact lookup fails.

## Acceptance Criteria

- `farm snippets pack <run-id>` creates the same kind of Markdown/JSON pack as `farm snippets pack <run-dir>` for an indexed run.
- `farm synthesis bundle <run-id>` creates the same kind of Markdown/JSON bundle as `farm synthesis bundle <run-dir>` for an indexed run.
- `farm dogfood record <run-id>` creates the same kind of local quality record as `farm dogfood record <run-dir>` for an indexed run.
- Existing absolute and relative run directory inputs continue to work for all three commands.
- Existing path inputs take precedence over run ID lookup.
- Unknown run references fail with a clear message that suggests running `farm list`.
- Stale indexed run IDs fail with a clear message that names the missing or invalid path.
- The resolver uses exact run ID matching only.
- No helper performs model calls as part of reference resolution.
- `farm run`, `farm list`, and `farm status` behavior remain unchanged.
- README and AI usage docs show that post-run helper arguments can be a run directory or run ID.
- BL-0058 is marked planned/implemented as appropriate.
- Model-free tests cover successful path resolution, successful run ID resolution, path-first precedence, unknown references, stale indexed paths, and at least one CLI helper using a run ID.

## Test Plan

Automated:

- unit tests for the shared run-reference resolver
- CLI or command tests proving post-run helpers pass resolved directories to existing helper modules
- parser/help tests if positional names are changed
- full model-free test suite

Verification:

```powershell
python -m unittest discover -s tests
```

Manual smoke, using any local indexed farm run:

```powershell
python qwen.py farm list
python qwen.py farm snippets pack <run-id> --output .run/smoke/snippet-packs
python qwen.py farm synthesis bundle <run-id> --output .run/smoke/synthesis-bundles
python qwen.py farm dogfood record <run-id> --output .run/smoke/dogfood-history
```

## Deferred To Roadmap

- Partial run ID prefixes for ergonomics.
- User-defined labels or aliases for important runs.
- Machine-readable `farm status --json` output.
- Cross-run helper lookup once cross-run helpers exist.
