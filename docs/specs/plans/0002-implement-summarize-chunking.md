# 0002 Implement Summarize Chunking

Status: Implemented
Change Spec: [0002 Add Summarize Chunking](../changes/0002-add-summarize-chunking.md)

## WHY

Dogfooding the farm on article and README inputs showed that long files need complete coverage. The first bugfix made truncation visible, but the farm should process all text for summarize mode.

This plan implements the smallest useful map/reduce summarize path while preserving the file-based farm model and model-free CI.

## Scope

Planned:

- paragraph-aware chunk planning for summarize inputs
- per-chunk input and result artifacts
- reduce pass over chunk summaries
- final result metadata showing chunk coverage
- status metadata showing whether a job used chunking
- tests for chunking helpers and farm orchestration

## Non-Goals

Deferred:

- tokenizer-aware budgets
- Markdown heading chunker
- caller-configurable chunk flags
- chunking for prompt mode
- chunk retry policies independent from file retry
- status JSON CLI output

## Implementation Plan

### 1. Add Chunk Helpers

Add helpers for:

- chunk ID formatting
- paragraph-aware text splitting
- chunk context rendering
- chunk metadata objects

Keep helpers deterministic and unit-testable.

### 2. Extend Farm Orchestration

For summarize mode:

- read the input file
- if it fits the summarize budget, process as before
- if it exceeds the budget, create chunk artifacts
- summarize each chunk
- reduce chunk summaries into the final file result
- write final result artifacts and chunking metadata

For prompt mode:

- keep current single-pass behavior

### 3. Extend Result Envelopes

Add optional chunking metadata to result envelopes and job summaries.

### 4. Preserve Failure Behavior

Keep the existing file-level retry loop for this first version. If any chunk or reduce pass raises, the file attempt fails and existing retry/failure handling applies.

### 5. Test Plan

Automated tests:

- chunk planning produces multiple chunks under the target budget
- oversize paragraphs are hard-split
- short summarize files stay single-pass
- long summarize files produce chunk artifacts and final chunk metadata
- prompt mode does not chunk
- status/list behavior remains intact

Manual verification:

```bash
python -m unittest discover -s tests
python sift.py farm run <long-text-folder> --output .run/manual-chunking --mode summarize --agent default
python sift.py farm status <run-id>
```

## Verification Plan

Before PR:

```bash
python -m unittest discover -s tests
```

Optionally run a real local Ollama smoke test against `.run/dogfood2/articles-text`.

## Acceptance Checklist

- [x] Change spec exists.
- [x] Plan exists.
- [x] Human accepted the behavior target.
- [x] Human accepted the implementation plan.
- [x] Chunk helpers are tested.
- [x] Chunked summarize jobs write chunk artifacts.
- [x] Final result JSON includes chunk metadata.
- [x] Status JSON includes compact chunk metadata.
- [x] Existing prompt mode behavior is unchanged.
- [x] Unit tests pass.
