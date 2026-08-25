# 0001 Implement Worker Farm MVP

Status: Implemented
Spec: [Farm MVP](../implemented/farm-mvp.md)
Change Spec: [0001 Add Worker Farm MVP](../changes/0001-add-worker-farm-mvp.md)

## WHY

The Farm MVP spec was accepted, so this plan translated the behavior contract into implementation steps before runtime code changed.

The plan keeps implementation, tests, verification, and spec lifecycle updates tied together so a future AI or human can inspect what was intended, what was built, and what was verified.

## Scope

Implemented the first filesystem-backed worker-farm slice:

- `python sift.py farm run <input-folder> --mode summarize`
- `python sift.py farm run <input-folder> --mode prompt --instructions <text>`
- `python sift.py farm list`
- `python sift.py farm status`
- `python sift.py farm status <run-id>`
- filesystem run folders
- file-level sub-jobs
- status artifacts
- Markdown, JSON, and raw-response result artifacts
- default retry and timeout behavior

## Non-Goals

This implementation does not include:

- queue-only runs
- background scheduler or daemon
- HTTP farm endpoints
- chunking
- SQLite
- include/exclude override syntax
- caller-provided failure policies
- strict JSON Schema files
- `extract`, `classify`, or `review`

## Implementation Plan

### 1. Add Farm Modules

Created focused Python modules under `src/` rather than growing `sift.py` into a large implementation file.

Likely split:

- `src/qwen_farm.py`: run orchestration and CLI-facing operations.
- `src/qwen_farm_files.py`: input discovery, skip rules, path helpers, run folder creation.
- `src/qwen_farm_status.py`: status JSON and Markdown rendering.
- `src/qwen_farm_model.py`: model prompt construction and gateway/Ollama invocation helpers.

Keep pure filesystem/status helpers unit-testable without Ollama.

### 2. Extend CLI

Extended `sift.py` with a `farm` namespace:

```bash
python sift.py farm run <input-folder> --mode summarize
python sift.py farm run <input-folder> --mode prompt --instructions <text>
python sift.py farm list
python sift.py farm status
python sift.py farm status <run-id>
```

The CLI should stay friendly for non-power-users:

- clear errors for missing input folders
- clear errors when `prompt` mode omits `--instructions`
- readable success output showing run ID and output folder

### 3. Implement Run Storage

Implemented the default farm home:

```text
.run/farm/
```

Run folders use:

```text
farm-run-YYYY-MM-DD-HHMMSS-xxxx
```

If `--output <dir>` is provided, the run folder is created inside that destination and remembered in `.run/farm/runs.json`.

### 4. Implement File Discovery

Processes readable text files under the input folder.

Skip:

- binary files
- `.git/`
- `node_modules/`
- `bin/`
- `obj/`
- `dist/`
- `build/`
- `__pycache__/`
- archives
- images
- PDFs
- Office documents
- minified assets

Skipped files are recorded in status counts and `skipped_files`.

### 5. Implement Status Artifacts

Writes both:

```text
farm-status.json
FARM_STATUS.md
```

Update status after each file/sub-job.

`farm-status.json` is the machine-readable source of truth. `FARM_STATUS.md` is the human-readable rendering.

### 6. Implement Result Artifacts

Each completed job writes:

```text
result.md
result.json
raw-response.txt
```

The farm owns the deterministic JSON envelope.

The model owns the mode-specific `result` payload.

### 7. Implement Modes

Implemented:

- `summarize`
- `prompt`

For `summarize`, asks the model for:

```json
{
  "title": "Short title",
  "abstract": "One compact paragraph summarizing the file.",
  "bullets": ["...", "..."],
  "open_questions": [],
  "confidence": "low|medium|high"
}
```

For `prompt`, preserve raw and Markdown output; JSON structure can be simpler unless it falls naturally out of shared result handling.

### 8. Implement Failure Handling

Default behavior:

- `max_attempts`: 2 total attempts
- `per_file_timeout_seconds`: 600
- `run_timeout_seconds`: null
- retry a failing file/sub-job once
- continue remaining files after a failed retry
- mark failed jobs and final run status correctly

### 9. Update Docs

Completed docs/spec lifecycle updates:

- updated `README.md` with farm commands
- updated `docs/ai-usage.md` with farm delegation examples
- updated `docs/roadmap.md` to mark the MVP slice as implemented and move remaining items forward
- moved [Farm MVP](../implemented/farm-mvp.md) from `accepted/` to `implemented/`
- updated [SPEC_DASHBOARD.md](../SPEC_DASHBOARD.md)
- marked [0001 Add Worker Farm MVP](../changes/0001-add-worker-farm-mvp.md) `Implemented`

## Test Plan

### Unit Tests

Added tests for:

- run ID format and sortability
- farm home and output path selection
- job folder naming
- text file discovery
- skip rules
- status JSON rendering
- status Markdown rendering
- result JSON envelope construction
- final run status calculation
- CLI argument parsing for `farm`

### Integration-Style Local Tests

Used temporary folders and monkeypatched model invocation to verify:

- happy path with two text files
- generated/vendor folders are skipped
- one file failure does not stop remaining work
- `--output <dir>` creates a run under the requested destination
- `farm list` finds known runs
- `farm status` renders an overview
- `farm status <run-id>` renders one run

### Manual Ollama Verification

Ran one real local model smoke test after unit tests passed:

```bash
python sift.py farm run .run/manual-farm-input-2 --output .run/manual-farm-results-2 --mode summarize --instructions "Keep this smoke test concise." --agent default
python sift.py farm list
python sift.py farm status farm-run-2026-08-23-191804-92de
```

The smoke test used `qwen3.5:4b` and completed successfully.

## Verification Plan

Before opening or merging the implementation PR, run:

```bash
python -m compileall sift.py examples src tests
python -m unittest discover -s tests -p "test_*.py"
```

Also verify the GitHub `ci` checks pass on the PR.

## Acceptance Checklist

- All acceptance criteria in [Farm MVP](../implemented/farm-mvp.md) are satisfied or explicitly deferred by a follow-up spec/change.
- Unit tests cover pure helpers and CLI parsing.
- Integration-style tests cover filesystem behavior without requiring Ollama.
- Manual Ollama verification is recorded in the PR body.
- User-facing docs show how to run and inspect farm work.
- AI-facing docs show when and how a primary AI should use the farm.
- The canonical spec moves from `accepted/` to `implemented/`.
- Change spec `0001` moves from `Accepted` to `Implemented`.
- The spec dashboard is updated.

## Risks

- Model JSON may be inconsistent; keep the outer farm envelope deterministic and preserve raw output.
- File discovery can accidentally include too much; keep skip rules conservative and test them.
- `sift.py` can become too large; keep farm logic in `src/` modules.
- Real model tests may be slow; keep CI model-free and record manual verification separately.
