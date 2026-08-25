# 0030 Add Farm Discovery Include/Exclude Overrides

Status: Implemented
Type: Add

## WHY

The farm currently discovers readable text files with a fixed set of built-in skip rules for generated folders, vendor folders, binary files, archives, images, PDFs, Office documents, and minified assets. That default is intentionally conservative, but it leaves callers with one clumsy escape hatch: move files around until discovery sees exactly the desired set.

That gets awkward for real folders with notes, article downloads, source trees, generated artifacts, scratch files, and dogfood inputs living side by side. A human or primary AI should be able to say "run this folder, but only these files" or "run this folder, except these noisy paths" without editing the folder.

This change implements:

- BL-0008: skip-list overrides

The product principle is: discovery should stay safe by default, but callers should be able to narrow or exclude file paths reproducibly from the CLI and config.

## Scope

Add first-pass file discovery overrides for `farm run`:

```powershell
python sift.py farm run notes --include "*.md"
python sift.py farm run notes --include "articles/*.txt" --include "notes/**/*.md"
python sift.py farm run notes --exclude "drafts/**" --exclude "*.tmp"
python sift.py farm run notes --include "**/*.txt" --exclude "**/raw/**"
```

Add matching config support under `.sift-farm.json`:

```json
{
  "discovery": {
    "include": ["articles/*.txt", "notes/**/*.md"],
    "exclude": ["**/drafts/**", "**/*.tmp"]
  }
}
```

Resolved run config should persist the effective discovery overrides in `farm-config.resolved.json` and `farm-status.json` runtime metadata.

Pattern semantics:

- patterns match normalized run-relative paths using `/` separators
- `--include` may be supplied multiple times
- `--exclude` may be supplied multiple times
- config values and CLI values are merged by default, with CLI values appended after config values
- if no include patterns are supplied, all otherwise eligible text files are included
- if include patterns are supplied, only matching otherwise eligible text files are included
- exclude patterns remove otherwise included files
- exclude wins over include when both match
- matching should be case-insensitive on Windows and case-sensitive on case-sensitive platforms where practical

Safety semantics:

- built-in binary, archive, image, PDF, Office, and minified-file safety skips remain in force
- include patterns do not force non-text or unsupported file types into processing
- built-in generated/vendor directory skips remain in force in this first pass unless implementation can support clear, testable diagnostics without making binary/vendor processing surprising
- forcing normally unsafe or vendor paths into processing remains a follow-up, not part of this spec

## Discovery Diagnostics

Today `skipped_files` is a flat list. This change should preserve that field for compatibility and may add additive structured discovery diagnostics.

Preferred additive shape:

```json
{
  "discovery": {
    "include": ["articles/*.txt"],
    "exclude": ["**/raw/**"],
    "counts": {
      "selected": 3,
      "skipped": 5
    },
    "skipped": [
      {
        "path": "raw/page.html",
        "reason": "excluded_by_pattern",
        "pattern": "**/raw/**"
      }
    ]
  }
}
```

The first implementation may keep structured diagnostics minimal, but humans and AI callers should be able to distinguish "skipped by built-in safety" from "skipped because the caller asked for it."

## CLI Behavior

`farm run` should accept:

```powershell
--include <pattern>
--exclude <pattern>
```

The flags should work with existing options such as:

- `--mode`
- `--instructions`
- `--agent`
- `--config`
- `--profile`
- `--resource-mode`
- chunking options
- snippet options
- failure-policy options
- concurrency options

The command should fail before model calls if an include or exclude pattern is invalid for the supported matcher.

If discovery finds no processable files after include/exclude filtering, the command should keep existing empty-run semantics unless implementation already has a clearer existing behavior. The status output should make it clear that files were skipped by discovery filters.

## Non-Goals

This change does not add:

- recursive `.gitignore` parsing
- `.qwenignore` files
- forcing binary, PDF, Office, image, archive, or minified files into processing
- text extraction for PDFs or Office documents
- include/exclude controls for post-run helpers
- per-mode discovery patterns
- a new matching language beyond simple glob-style path patterns
- UI support
- drop-folder request file syntax
- remote URL ingestion

## Acceptance Criteria

- `farm run` accepts repeated `--include` flags.
- `farm run` accepts repeated `--exclude` flags.
- `.sift-farm.json` accepts `discovery.include` as an array of strings.
- `.sift-farm.json` accepts `discovery.exclude` as an array of strings.
- Unknown `discovery` fields fail config validation before creating a run folder.
- Non-string include/exclude config entries fail config validation before creating a run folder.
- Effective include/exclude values are present in `farm-config.resolved.json`.
- Effective include/exclude values are visible in `farm-status.json` runtime metadata.
- Include patterns narrow discovery to matching otherwise eligible text files.
- Exclude patterns remove matching otherwise eligible text files.
- Exclude wins when a file matches both include and exclude.
- Existing default discovery behavior is unchanged when no overrides are supplied.
- Built-in binary and unsupported suffix safety skips remain in force.
- `skipped_files` remains present and backward compatible.
- Status or discovery diagnostics distinguish caller-filtered skips from built-in safety skips where practical.
- `FARM_STATUS.md` renders enough discovery filter information for a human to understand why a run processed fewer files than expected.
- `farm status <run-id> --json` exposes discovery override metadata without special parsing.
- Retry failed files continues to work with source runs that used include/exclude overrides.
- Docs explain pattern syntax, examples, and first-pass safety limits.
- BL-0008 is marked planned/implemented as lifecycle advances.

## Tests

Add model-free tests for:

- default discovery compatibility with no overrides
- include-only discovery
- exclude-only discovery
- include plus exclude where exclude wins
- repeated CLI include/exclude parsing
- config include/exclude resolution
- CLI overrides merged with config values
- invalid discovery config fields
- invalid non-string pattern values
- binary/unsupported files still skipped even when included
- persisted resolved config includes discovery settings
- `farm-status.json` includes discovery/runtime metadata
- `FARM_STATUS.md` renders discovery filter metadata
- schema compatibility for status artifacts with discovery metadata
- retry planning compatibility for source runs created with discovery overrides

Run:

```powershell
python -m src.qwen_spec_guard
python -m unittest tests.test_qwen_farm_files tests.test_qwen_farm_profiles tests.test_qwen_farm tests.test_qwen_cli tests.test_qwen_farm_status tests.test_qwen_farm_schema
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

## Manual Verification

Use ignored artifacts only:

```text
.run/dogfood_0030/
```

Suggested smoke:

1. Create a small folder with eligible files, a nested `raw/` folder, a binary-like file, and a generated/vendor-like folder.
2. Run:

```powershell
python sift.py farm run .run/dogfood_0030/input --output .run/dogfood_0030/include --include "**/*.txt"
python sift.py farm run .run/dogfood_0030/input --output .run/dogfood_0030/exclude --exclude "**/raw/**"
python sift.py farm status <run-id> --json
```

Inspect:

- selected file count
- skipped file count
- `skipped_files`
- any structured discovery diagnostics
- `farm-config.resolved.json`
- `FARM_STATUS.md`

## Deferred To Backlog

- BL-0100: `.qwenignore` or repo-local ignore files
- BL-0101: force-include normally skipped text files from generated/vendor folders
- BL-0102: include/exclude controls for post-run helpers
- BL-0103: richer structured discovery diagnostics and reason codes

## Lifecycle

When this spec is accepted:

- mark this spec `Accepted`
- add an implementation plan under `docs/specs/plans/`
- update `SPEC_DASHBOARD.md`
- mark BL-0008 planned in `docs/backlog.md`
- add deferred follow-ups as open backlog rows if still out of scope

When implementation is complete in the PR:

- mark this spec `Implemented`
- mark the plan `Implemented`
- update `SPEC_DASHBOARD.md`
- mark BL-0008 implemented in `docs/backlog.md`
