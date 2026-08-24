# 0026 Add Markdown Heading Ancestry And Chunk Overlap

Status: Implemented
Type: Add

## WHY

The farm can now process long article-like inputs with character or token-aware chunking, but chunks still lose some useful document context at boundaries.

Two problems show up in real summarization:

- a chunk may start in the middle of a Markdown section and the worker no longer knows the parent heading path
- an important idea may straddle a chunk boundary, so neither adjacent chunk gets enough surrounding text

For a human, headings and nearby paragraphs make this easy to understand. For a local worker model, each chunk is a smaller isolated prompt. The farm should carry a little structural context forward so local summaries become more coherent before a frontier model sees the compact outputs.

This change combines:

- BL-0015: Markdown heading ancestry preservation
- BL-0035: chunk overlap

The goal is not semantic chunking yet. The goal is a small, deterministic improvement to chunk inputs and chunk metadata that preserves useful source structure without changing the overall map/reduce architecture.

## Scope

This change adds:

- Markdown heading detection for summarize chunk planning
- heading ancestry metadata on chunk records
- heading context rendered into chunk input files/prompts
- opt-in chunk overlap for character chunking
- opt-in chunk overlap for token-aware chunking when an exact token counter is available
- resolved runtime config fields for heading ancestry and overlap settings
- CLI overrides for heading ancestry and overlap settings
- status/result/chunk metadata that makes heading ancestry and overlap inspectable
- model-free tests for heading ancestry extraction, chunk input rendering, overlap sizing, config validation, and CLI parsing
- docs updates for users and AI callers
- backlog lifecycle updates for BL-0015 and BL-0035 as lifecycle advances

Proposed config shape:

```json
{
  "summarize": {
    "preserve_heading_ancestry": true,
    "chunk_overlap_chars": 0,
    "chunk_overlap_tokens": 0
  }
}
```

Proposed CLI overrides:

```powershell
python qwen.py farm run notes --mode summarize --preserve-heading-ancestry
python qwen.py farm run notes --mode summarize --no-preserve-heading-ancestry
python qwen.py farm run notes --mode summarize --chunk-overlap-chars 500
python qwen.py farm run notes --mode summarize --chunk-strategy token --chunk-overlap-tokens 200
```

Default behavior:

- `preserve_heading_ancestry`: `true`
- `chunk_overlap_chars`: `0`
- `chunk_overlap_tokens`: `0`

Heading ancestry should be default-on because it is compact document context. Overlap should be default-off because it adds prompt budget and can duplicate content unless the caller deliberately opts in.

## Non-Goals

This change does not add:

- semantic chunking
- embedding-assisted chunking
- code-aware chunking
- PDF/Office/document ingestion
- chunk-level parallelism
- cross-run chunk resume
- failed-file retry from a prior run
- partial reduce over missing chunks
- UI for visualizing chunks
- automatic overlap tuning from quality scores
- a new summarize result schema
- first-class `extract`, `classify`, or `review` mode chunking
- model calls in CI

## Behavior

### Heading Detection

For readable Markdown-like text files, the farm should detect ATX Markdown headings:

```markdown
# Title
## Section
### Subsection
```

The first implementation only needs ATX headings. It does not need Setext headings, HTML headings, wiki syntax, or frontmatter-aware heading detection.

Heading detection should:

- ignore headings inside fenced code blocks
- preserve heading level
- preserve heading text
- preserve source line number when available
- maintain the active heading path for each chunk

For non-Markdown files or files without headings, heading ancestry should be an empty list.

### Chunk Metadata

Each chunk record should include heading ancestry when enabled:

```json
{
  "chunk_id": "chunk-0002",
  "heading_ancestry": [
    {"level": 1, "text": "Article Title", "line": 1},
    {"level": 2, "text": "Why It Matters", "line": 38}
  ],
  "overlap": {
    "before_chars": 0,
    "before_tokens": null,
    "source": "none"
  }
}
```

If heading ancestry is disabled, chunk records may omit `heading_ancestry` or set it to an empty list, but the choice must be stable and covered by schema/tests if persisted.

### Chunk Input Rendering

Chunk input files and model prompts should include heading context before the chunk body when heading ancestry is available.

Example:

```text
Source: article.md
Chunk: 2/6

Heading context:
- # Article Title
- ## Why It Matters

Chunk text:
...
```

The prompt text should make the heading context clearly metadata, not source prose that should be quoted as if it appeared at the chunk boundary.

### Overlap Policy

Overlap is opt-in.

For character chunking:

- `chunk_overlap_chars` controls the maximum number of prior-source characters included before a chunk body
- overlap applies only between adjacent chunks from the same file
- overlap does not create an extra chunk
- overlap text is marked as context in the chunk input
- overlap text should not count as new primary coverage in chunk metadata

For token-aware chunking:

- `chunk_overlap_tokens` controls the maximum number of prior-source tokens included before a chunk body
- token-aware overlap requires the exact token counter already needed by token chunking
- the farm must keep total chunk prompt input within the configured chunk token budget after adding heading context and overlap

If overlap is too large for the configured chunk budget, validation should fail before model calls rather than silently producing oversized prompts.

### Config Resolution

The new summarize settings follow existing precedence:

```text
built-in profile -> .qwen-farm.json -> CLI
```

Validation:

- `preserve_heading_ancestry` must be boolean
- `chunk_overlap_chars` must be a non-negative integer
- `chunk_overlap_tokens` must be a non-negative integer
- unknown config fields still fail validation
- overlap settings may be zero

### Status And Artifacts

Resolved settings should appear in:

- `farm-config.resolved.json`
- `farm-status.json` under `runtime.summarize`
- `FARM_STATUS.md`

Chunk-level artifacts should expose:

- whether heading ancestry was enabled
- the chunk's heading ancestry
- whether overlap was used
- overlap size for the chunk

The final file-level result does not need to cite heading ancestry in prose, but `result.json` should preserve enough chunk metadata for a primary AI to inspect where summaries came from.

### Dogfood Expectation

The implementation should dogfood a small Markdown/article-like folder with:

- baseline no-overlap behavior
- heading ancestry enabled
- a small overlap setting

Dogfood should inspect whether:

- chunk inputs are easier to understand
- summaries refer to sections more accurately
- overlap creates useful continuity or annoying duplication
- prompt/call timing changes are acceptable

Use `.run/` for dogfood artifacts.

## Acceptance Criteria

- `.qwen-farm.json` accepts `summarize.preserve_heading_ancestry`.
- `.qwen-farm.json` accepts `summarize.chunk_overlap_chars`.
- `.qwen-farm.json` accepts `summarize.chunk_overlap_tokens`.
- CLI accepts heading ancestry and overlap overrides.
- Unknown or invalid config values fail before creating a run folder.
- Heading extraction ignores fenced code block headings.
- Chunk records include heading ancestry for Markdown chunks when enabled.
- Chunk input files render heading context before chunk text.
- Character chunking can add bounded prior-chunk overlap when `chunk_overlap_chars > 0`.
- Token-aware chunking can add bounded prior-chunk overlap when `chunk_overlap_tokens > 0`.
- Token-aware chunking keeps the final rendered chunk input within the configured token budget.
- Overlap metadata distinguishes overlap context from primary chunk coverage.
- `farm-config.resolved.json`, `farm-status.json`, and `FARM_STATUS.md` show the effective settings.
- Existing summarize behavior remains compatible when overlap is `0`.
- Existing token-aware and character chunking tests remain green.
- BL-0015 and BL-0035 are marked implemented as lifecycle advances.
- Deferred related items remain in backlog.

## Test Plan

Model-free tests should cover:

- heading ancestry extraction across nested headings
- heading-like lines inside fenced code blocks are ignored
- chunk input rendering with and without heading ancestry
- character overlap size and metadata
- token overlap size and metadata with a fake exact token counter
- validation for boolean and non-negative integer settings
- CLI parsing for heading/overlap overrides
- persisted runtime/status fields
- no-overlap compatibility with existing chunk counts where expected

Manual/runtime dogfood should cover:

- a short Markdown fixture with nested headings
- at least one chunk boundary inside a section
- comparison of no-overlap versus small-overlap summaries
- timing inspection for added overhead

## Deferred To Roadmap

- Semantic chunking.
- Code-aware chunking.
- Frontmatter-aware note splitting.
- UI/dashboard chunk visualization.
- Automatic overlap tuning.
- Cross-run chunk resume.
- Failed-file retry from a previous run.
- Partial reduce over missing chunks.
- First-class extract/classify/review chunking.
