# Chunking Roadmap

Chunking is the farm's answer to context blowups: callers should be able to hand the farm large files or folders without first knowing whether everything fits in the selected model context.

This is a sub-feature roadmap, not an implementation spec.

## Goal

Let the farm process large text inputs by splitting them into manageable chunks, processing those chunks safely, and combining the results into useful final artifacts.

Chunking should be automatic only when the selected mode can tolerate it.

## Core Policy

Auto-chunk by default for modes where independent chunk processing is usually safe:

| Mode | Default Chunking Policy | Why |
| --- | --- | --- |
| `summarize` | Auto-chunk allowed | Summaries can be built from partial summaries. |
| `extract` | Auto-chunk allowed | Entities, facts, tasks, links, and claims can usually be extracted per chunk. |
| `classify` | Auto-chunk sometimes allowed | Folder/file classification is natural; chunk-level classification needs aggregation. |
| `transform` | Mode-specific | Some transforms are chunk-safe; others require full context. |

Do not blindly auto-chunk by default for:

| Mode | Default Chunking Policy | Why |
| --- | --- | --- |
| `review` | Ask or fail clearly | Review may need cross-file or whole-file reasoning. |
| `compare` | Needs explicit flow | Comparison needs pairing and alignment strategy. |
| `decision` | Ask or fail clearly | Decisions may depend on global tradeoffs. |
| code architecture analysis | Ask or fail clearly | Important relationships may span distant files. |

When a mode is not chunk-safe, the farm should explain what happened and suggest a next action that an AI caller can understand.

## First Useful Version

The first useful version now supports:

- readable text files
- size/context detection
- fallback paragraph splitting
- per-chunk outputs
- a reduce pass for final summary/extraction output
- token-aware chunk sizing for supported Qwen/Ollama tokenizers
- timing metrics and configurable retries for chunk map and reduce calls

Still missing from the first useful version:

- Markdown-aware splitting by headings
- heading ancestry preserved in chunk inputs and outputs
- optional overlap between adjacent chunks
- richer provenance from final results back to source chunks
- in-progress status updates at chunk and reduce level

Example output:

```text
results/
  farm-run-2026-08-23-001/
    FARM_STATUS.md
    farm-status.json
    outputs/
      big-file.summary.md
      big-file.summary.json
    chunks/
      big-file/
        chunk-001.md
        chunk-002.md
        chunk-003.md
    chunk-results/
      big-file/
        chunk-001.summary.json
        chunk-002.summary.json
        chunk-003.summary.json
```

## Status Shape

Chunk-aware status should show both file progress and chunk progress.

Example:

```json
{
  "farm_run_id": "farm-run-2026-08-23-001",
  "status": "running",
  "current_file": "big-file.md",
  "files": [
    {
      "path": "big-file.md",
      "status": "running",
      "chunking": {
        "enabled": true,
        "strategy": "markdown-headings",
        "total_chunks": 7,
        "completed_chunks": 3,
        "current_chunk": 4
      }
    }
  ]
}
```

## Chunking Strategies

Current strategy:

1. Preserve source path and chunk ordinal.
2. Keep chunks under a target character or token budget.
3. Use paragraph splitting when possible.
4. Fall back to hard splitting only as a last resort.

Next strategy improvements:

1. Split Markdown by headings where possible.
2. Preserve heading ancestry in every chunk.
3. Add optional chunk overlap with explicit metadata.
4. Keep tokenizer-aware budgets compatible with heading and overlap behavior.

Later strategies:

- code-aware splitting by symbols/functions/classes
- frontmatter-aware note splitting
- semantic chunking
- repository-aware grouping

## Map/Reduce Shape

For chunk-safe modes, use a map/reduce pattern:

1. **Map**: process each chunk independently.
2. **Reduce**: combine chunk outputs into a file-level result.
3. **Refine**: optionally run a second pass over the aggregate to remove duplicates, resolve contradictions, and improve readability.

Example:

```text
file.md
  -> chunk-001.md
  -> chunk-002.md
  -> chunk-003.md
  -> chunk result JSON files
  -> final file result.md
  -> final file result.json
```

## Provenance

Final outputs should know where claims came from.

Minimum provenance:

```json
{
  "source_file": "input/big-file.md",
  "source_chunks": ["chunk-001", "chunk-003"],
  "source_headings": ["Background", "Implementation Notes"]
}
```

Later provenance:

- line ranges
- byte offsets
- section anchors
- confidence per extracted item
- citation-like links into chunk artifacts

## Failure Handling

Chunk failures should not automatically fail the whole run.

Default policy:

- retry failed chunk
- preserve raw failed output
- mark chunk failed if retry fails
- current implementation fails the file attempt when a required chunk or reduce call exhausts retries
- continue remaining chunks and produce partial file output only after a partial-output contract is specified
- mark run `partial` if any file is partial or failed

Caller-provided fixed retry policies now exist. Dynamic recovery, cross-run chunk resume, and partial reduce remain backlog work.

## Open Questions

1. Should heading ancestry and overlap ship together or as separate changes?
2. How much overlap should chunks have by default, and should default overlap be off?
3. Should chunk artifacts stay under job internals or become easier to collect/export?
4. Should in-progress status expose every chunk, or only compact current/completed/failed counts?
5. Should chunking behavior be configured per mode, per agent, or per request?
6. Should review mode ever auto-chunk, or should it require explicit caller instructions?

## Likely Implementation PRs

1. Add Markdown heading ancestry.
2. Add optional chunk overlap.
3. Add in-progress chunk/reduce status visibility.
4. Add failed-file retry from prior runs.
5. Add cross-run chunk resume after failed-file retry is stable.
6. Add extract/classify chunk support.
7. Explore code-aware and semantic chunking.
