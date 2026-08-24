# 0002 Add Summarize Chunking

Status: Implemented
Type: Add

## WHY

The worker farm can now summarize real article inputs safely, but long files still lose coverage because summarize mode clips oversized content to fit the default local model context.

The next step is to make summarize mode useful for long articles and README-style inputs without requiring the caller to manually split files first.

This change favors:

- complete source coverage over silent clipping
- visible intermediate artifacts over hidden model calls
- simple character-based chunking over tokenizer dependencies
- model-free CI tests over live-model assumptions

## Scope

This change adds the first chunk-safe summarize flow:

- automatic chunking for oversized `summarize` inputs
- paragraph-aware text chunking
- per-chunk input artifacts
- per-chunk summary artifacts
- a reduce pass that combines chunk summaries into one file-level summary
- final result metadata showing chunk count and coverage

## Non-Goals

This change does not add:

- chunking for `prompt` mode
- chunking for future `extract`, `classify`, or `review` modes
- tokenizer-aware chunk sizing
- semantic chunking
- cross-file reduce
- resumable chunk retries
- caller-facing chunk configuration flags
- JSON Schema files

## Behavior

### Chunk Trigger

In `summarize` mode, if a file exceeds the safe summary character budget, the farm splits it into chunks and processes every chunk.

Short files continue through the existing single-pass summarize path.

### Chunk Strategy

The first implementation uses character budgets:

1. Split by blank-line paragraphs where possible.
2. Keep chunks under the summary input budget.
3. Hard-split an individual paragraph only when it is too large to fit.
4. Prefix each chunk with source path and chunk ordinal context.

### Chunk Artifacts

For a chunked job, write:

```text
jobs/job-0001/chunks/chunk-0001.txt
jobs/job-0001/chunks/chunk-0002.txt
jobs/job-0001/chunk-results/chunk-0001/result.md
jobs/job-0001/chunk-results/chunk-0001/result.json
jobs/job-0001/chunk-results/chunk-0001/raw-response.txt
```

The normal file-level result artifacts still exist:

```text
jobs/job-0001/result.md
jobs/job-0001/result.json
jobs/job-0001/raw-response.txt
```

### Reduce Pass

After all chunk summaries complete, the farm sends the chunk summaries through a reduce prompt and writes that reduce output as the file-level result.

If all chunks and the reduce pass complete, the job is considered complete unless warnings are present.

### Result Metadata

Chunked `result.json` includes a `chunking` object:

```json
{
  "enabled": true,
  "strategy": "paragraph-character",
  "chunk_count": 3,
  "coverage": "full",
  "chunks": [
    {
      "chunk_id": "chunk-0001",
      "input": "chunks/chunk-0001.txt",
      "result_json": "chunk-results/chunk-0001/result.json",
      "result_md": "chunk-results/chunk-0001/result.md"
    }
  ]
}
```

Single-pass results include:

```json
{
  "enabled": false,
  "strategy": "single-pass",
  "chunk_count": 1,
  "coverage": "full"
}
```

### Status

The embedded job summary in `farm-status.json` includes the same compact chunking metadata so a primary AI can see whether a file was chunked without opening every result file.

## Acceptance Criteria

- Oversized summarize inputs are chunked instead of clipped.
- Short summarize inputs continue to use one model call.
- Prompt mode behavior is unchanged.
- Chunked jobs write chunk input artifacts.
- Chunked jobs write chunk result Markdown, JSON, and raw-response artifacts.
- Chunked jobs write normal file-level result Markdown, JSON, and raw-response artifacts.
- Final job `result.json` includes chunking metadata.
- Job summaries in `farm-status.json` include compact chunking metadata.
- A chunked job with successful chunk and reduce passes has full coverage metadata.
- The run status reflects warnings or failures from chunk or reduce work.
- Unit tests cover chunk planning, artifact metadata, and map/reduce orchestration without requiring Ollama.

## Deferred To Roadmap

- Tokenizer-aware chunk sizing.
- Markdown heading ancestry preservation.
- Configurable chunk sizes and overlap.
- Chunk retries separate from file retries.
- Cross-file synthesis.
- `farm status --json`.
