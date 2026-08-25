# 0013 Add Farm Status JSON

Status: Implemented
Type: Add

## WHY

`farm status` is useful for humans, but primary AIs and scripts need a stable machine-readable status command. Today they can inspect `farm-status.json` directly if they already know the run directory, but that creates extra path lookup work and makes overview inspection awkward.

The farm should expose JSON status through the CLI so a caller can inspect all known runs or one run ID without parsing Markdown.

This change favors:

- stdout JSON for primary-AI and script consumption
- preserving the existing human-readable `farm status` output
- reusing existing status artifacts and run discovery behavior
- model-free tests
- no new persistent generated files

## Scope

This change adds a JSON output option for farm status:

- add `--json` to `python sift.py farm status`
- support `python sift.py farm status --json` for an overview of known runs
- support `python sift.py farm status <run-id> --json` for one run
- print valid JSON to stdout with no Markdown, prose, or code fences
- reuse existing run loading and ordering behavior
- preserve current Markdown output when `--json` is omitted
- document the option for human users and primary AIs
- update BL-0019 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- formal JSON Schema files
- JSON output for every farm command
- `farm list --json`
- watch/streaming status
- filtering, paging, or sorting flags
- status mutation
- new run artifacts on disk
- model calls
- changes to `farm-status.json` shape

## Behavior

### CLI Shape

Human-readable output remains the default:

```powershell
python sift.py farm status
python sift.py farm status <run-id>
```

Machine-readable output uses `--json`:

```powershell
python sift.py farm status --json
python sift.py farm status <run-id> --json
```

The flag may appear before or after the optional run ID if `argparse` supports it naturally.

### Overview JSON

With no run ID, the command prints an object:

```json
{
  "schema_version": 1,
  "scope": "overview",
  "counts": {
    "runs": 2
  },
  "runs": [
    {
      "run_id": "farm-run-2026-08-24-120000-abcd",
      "status": "complete",
      "mode": "summarize",
      "updated_at": "2026-08-24T12:01:00Z",
      "output": {
        "path": ".run/farm-results/farm-run-2026-08-24-120000-abcd"
      },
      "counts": {
        "total": 4,
        "complete": 4,
        "failed": 0,
        "skipped": 0
      }
    }
  ]
}
```

The `runs` entries may reuse the existing loaded status objects, but the envelope must make the response type clear.

When there are no runs, output:

```json
{
  "schema_version": 1,
  "scope": "overview",
  "counts": {
    "runs": 0
  },
  "runs": []
}
```

### Single-Run JSON

With a run ID, the command prints an object:

```json
{
  "schema_version": 1,
  "scope": "run",
  "run_id": "farm-run-2026-08-24-120000-abcd",
  "run": {
    "run_id": "farm-run-2026-08-24-120000-abcd",
    "status": "complete",
    "mode": "summarize",
    "jobs": []
  }
}
```

The `run` object should be the loaded run status content, preserving the existing `farm-status.json` shape for callers that already understand it.

### Error Behavior

Unknown run IDs should keep the existing failure semantics. The first version does not need structured JSON errors.

## Acceptance Criteria

- `python sift.py farm status` still prints the existing human-readable farm overview.
- `python sift.py farm status <run-id>` still prints the existing human-readable single-run status.
- `python sift.py farm status --json` prints valid JSON for the overview with `schema_version`, `scope`, `counts`, and `runs`.
- `python sift.py farm status <run-id> --json` prints valid JSON for one run with `schema_version`, `scope`, `run_id`, and `run`.
- JSON output contains no Markdown or explanatory prose.
- JSON overview uses the same known-run discovery and ordering as the human overview/listing.
- JSON single-run lookup uses the same run ID semantics as human `farm status <run-id>`.
- Empty overview output is valid JSON with an empty `runs` list.
- Existing `farm run`, `farm list`, post-run helpers, and status artifacts remain unchanged.
- Docs describe when an AI or script should use `--json`.
- BL-0019 is marked planned/implemented as appropriate.
- Model-free tests cover parser support, empty overview JSON, overview JSON with runs, single-run JSON, and preservation of existing Markdown output.

## Test Plan

Automated:

- unit tests for overview JSON rendering
- unit tests for single-run JSON rendering
- CLI parser tests for `farm status --json` and `farm status <run-id> --json`
- regression tests for existing Markdown status behavior
- full model-free test suite

Verification:

```powershell
python -m unittest tests.test_qwen_farm tests.test_qwen_cli tests.test_qwen_farm_status
python -m unittest discover -s tests
```

Manual smoke, using any local indexed farm run:

```powershell
python sift.py farm status --json
python sift.py farm status <run-id> --json
```

## Deferred To Roadmap

- Formal JSON Schema files for status/result validation.
- JSON output for `farm list`.
- Structured JSON error output.
- Filtering or paging large farm overviews.
- Watch/streaming status for active long-running runs.
