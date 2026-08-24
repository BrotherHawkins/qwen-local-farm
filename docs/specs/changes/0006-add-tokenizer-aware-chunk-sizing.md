# 0006 Add Tokenizer-Aware Chunk Sizing

Status: Implemented
Type: Add

## WHY

The first summarize chunker deliberately used paragraph-aware character budgets. That was simple and model-free, but dogfood showed it can over-split real article inputs. Article 004 in the dogfood set was roughly 15,600 estimated tokens, yet it became 9 chunks because the farm was enforcing an 8,000 character body budget rather than sizing against the model context window.

That means the farm can spend extra local model calls on work a model could probably handle in fewer calls. For a primary AI that will read the farm output later, unnecessary chunking also creates more reduce work and more intermediate artifacts to inspect.

The next chunking step should let users opt into tokenizer-aware sizing through settings while keeping the current character-based path available and stable.

This change favors:

- opt-in tokenizer-aware chunk planning over changing defaults blindly
- local, reproducible behavior over runtime network downloads
- clear resolved settings over hidden heuristics
- fewer model calls when the context window allows it
- status/result metadata that explains why a file became N chunks
- dogfood comparison against the current character chunker before claiming improvement

## Scope

This change adds tokenizer-aware sizing for summarize chunking:

- add settings support for selecting the summarize chunk sizing strategy
- preserve the current character-based paragraph chunker as the default strategy
- add an opt-in token-aware strategy for summarize chunk planning
- infer or accept token budgets from resolved farm settings and agent/model context limits
- reserve space for prompt/header/output/safety margin before assigning source text to chunks
- keep paragraph-aware boundaries where practical while enforcing token budgets
- apply token-aware budget checks to reduce input batching or fail clearly when reduce input would exceed the configured budget
- add a local tokenizer probe/setup path for the supported Qwen/Ollama agents
- persist chunk strategy, budgets, character counts, and token counts in run/job artifacts
- document tokenizer setup, cache behavior, troubleshooting, new settings, and CLI behavior
- create and run a clean `dogfood_lite` comparison using articles 002, 004, 005, and 009

## Non-Goals

This change does not add:

- a historical benchmark dashboard outside the run folder
- automatic hardware probing or `farm doctor`
- runtime tokenizer downloads without explicit user setup
- tokenizer support for model families outside the supported Qwen/Ollama agents
- chunk-level parallelism
- semantic chunking or embedding-based splitting
- Markdown heading ancestry preservation
- chunk overlap
- retrying individual failed chunks
- automatic migration of existing user config files
- changing built-in profiles to token-aware mode by default

## Settings

The existing flat summarize settings remain valid:

```json
{
  "summarize": {
    "chunk_chars": 8000,
    "reduce_chars": 8000
  }
}
```

The new settings must make chunk sizing strategy explicit while preserving those existing fields. The user-facing config supports:

```json
{
  "summarize": {
    "chunk_strategy": "character",
    "chunk_chars": 8000,
    "reduce_chars": 8000
  }
}
```

and:

```json
{
  "summarize": {
    "chunk_strategy": "token",
    "chunk_tokens": 6500,
    "reduce_tokens": 6500,
    "token_safety_margin": 0.10
  }
}
```

`character` preserves the current behavior. `token` opts into tokenizer-aware behavior.

If token budgets are omitted, the farm may derive conservative defaults from the selected agent or model context limit. Derived budgets must be visible in resolved config artifacts.

CLI overrides should exist for power users and for AI skills that configure runs on behalf of less technical users. The exact flags can be chosen during planning, but they should cover:

- `--chunk-strategy character|token`
- `--chunk-tokens <positive-int>`
- `--reduce-tokens <positive-int>`
- `--token-safety-margin <number>`

## Behavior

### Character Strategy

The current paragraph-aware character chunker remains the default. Existing commands, profiles, tests, and config files keep working unless a caller opts into token-aware sizing.

### Token Strategy

When `chunk_strategy` is `token`, the farm chunks summarize inputs by token budget instead of character budget.

The planner should:

1. Resolve the effective model and context limit for the run.
2. Reserve tokens for prompt text, chunk headers, expected response room, and safety margin.
3. Split source text into paragraph units as it does today.
4. Pack paragraphs until adding the next unit would exceed the token budget.
5. Split an oversized paragraph by smaller boundaries when possible, and by hard token-safe slices when necessary.
6. Render chunk input artifacts that fit the resolved budget.

The budget check should account for the rendered chunk prompt/input, not only the raw source text body. This prevents headers and instructions from silently pushing a chunk beyond the intended window.

### Local Tokenizer Availability

Token-aware mode must not rely on downloading a tokenizer during normal test or CI runs.

The supported first-pass tokenizer path is Hugging Face `AutoTokenizer` with locally cached tokenizer assets. This requires the Python tokenizer dependencies to be installed locally, but it does not require PyTorch or model weights.

The implementation should map the built-in Ollama model aliases to tokenizer IDs:

| Ollama model | Tokenizer ID |
| --- | --- |
| `qwen3.5:4b` | `Qwen/Qwen3.5-4B` |
| `qwen3:4b` | `Qwen/Qwen3-4B` |
| `qwen3:8b` | `Qwen/Qwen3-8B` |
| `qwen3:14b` | `Qwen/Qwen3-14B` |

Setup/docs should include commands equivalent to:

```powershell
python -m pip install --user "transformers>=5.15" "tokenizers>=0.22"
```

and a probe command that downloads tokenizer assets into an ignored local cache, such as:

```text
.run/tokenizers/hf-cache/
```

The probe must verify that the tokenizer can be loaded again with offline/local-only settings before reporting success.

If token-aware mode is requested and the implementation cannot count tokens exactly for the selected model, the farm must fail before starting jobs with an error that names:

- the requested strategy
- the selected model
- the missing tokenizer capability
- the fallback command or setting to use character strategy

This first implementation should record `counts_are_estimated: false` for token-aware runs. Estimated token fallback is deferred.

### Documentation

The README and docs should make the tokenizer setup understandable for both power users and primary AIs helping less technical users.

Documentation updates include:

- root README quickstart or useful commands that mention the tokenizer probe/setup path
- `docs/platforms.md` notes for installing tokenizer dependencies and explaining the ignored local cache
- `docs/ai-usage.md` guidance for when a primary AI should enable token-aware chunking
- troubleshooting text for missing `transformers`/`tokenizers`, missing cache files, offline mode failures, and returning to `chunk_strategy: character`

The future `farm doctor` work should include tokenizer readiness in its setup report so a primary AI can tell a less technical user whether token-aware chunking is available and what command to run next.

### Reduce Budget

Token-aware mode should avoid building reduce prompts that exceed the reduce token budget.

For this spec, acceptable first-pass behavior is either:

- progressive reduce batching that keeps each reduce call under budget, or
- a clear pre-reduce failure that explains the reduce input exceeded the configured token budget

Silently sending an oversized reduce prompt is not acceptable in token-aware mode.

### Artifact Metadata

Resolved config artifacts include the effective summarize chunking settings:

```json
{
  "summarize": {
    "chunk_strategy": "token",
    "chunk_tokens": 6500,
    "reduce_tokens": 6500,
    "token_safety_margin": 0.1
  }
}
```

Chunked job `result.json` includes chunking metadata such as:

```json
{
  "chunking": {
    "strategy": "paragraph-token",
    "chunk_count": 3,
    "tokenizer": "qwen",
    "counts_are_estimated": false,
    "chunk_tokens": 6500,
    "reduce_tokens": 6500,
    "chunks": [
      {
        "chunk_id": "chunk-0001",
        "chars": 23142,
        "tokens": 5790,
        "input": "chunks/chunk-0001.txt",
        "result_json": "chunk-results/chunk-0001/result.json",
        "result_md": "chunk-results/chunk-0001/result.md"
      }
    ]
  }
}
```

For character strategy runs, metadata should still identify the strategy and character budget so primary AIs can tell which chunker produced the output.

## Dogfood Lite

The implementation must create a clean ignored dogfood sample under:

```text
.run/dogfood_lite/
```

The lite input set contains only these existing article text files from the dogfood corpus:

- `002-the-append-and-review-note-karpathy.txt`
- `004-tags-guide-obsidian-claude-code-karpathy-pkm-llm.txt`
- `005-karpathy-llm-wiki-starter-vault.txt`
- `009-qmd-query-markup-documents.txt`

The implementation must run a baseline before changing chunk behavior:

```text
.run/dogfood_lite/baseline/
```

After implementation, enable token-aware chunking in settings and run the same lite articles again:

```text
.run/dogfood_lite/token-aware/
```

Both runs should use the same articles, mode, instructions, agent, profile, and concurrency settings unless the spec implementation notes explain why a difference was necessary. Prefer `--parallel-jobs 1` for this comparison so chunking changes are easier to compare without backend contention noise.

The dogfood report is saved as:

```text
.run/dogfood_lite/DOGFOOD_LITE_REPORT.md
```

The report compares:

- run IDs and final statuses
- selected model and resolved context/budget settings
- article-level character counts and token counts
- chunk counts by article
- model call counts by article
- wall-clock duration by run and article
- aggregate map/reduce/single call durations
- warnings or failures
- whether summaries remain useful after fewer/larger chunks

## Acceptance Criteria

- Existing character-based summarize chunking remains the default.
- Existing `.qwen-farm.json` files with `summarize.chunk_chars` and `summarize.reduce_chars` remain valid.
- Settings can opt into tokenizer-aware summarize chunking.
- CLI overrides can opt into tokenizer-aware summarize chunking for one run.
- A tokenizer probe/setup path verifies exact local token counting for `qwen3.5:4b`, `qwen3:4b`, `qwen3:8b`, and `qwen3:14b`.
- The tokenizer probe verifies offline/local-only loading after the initial tokenizer asset cache is created.
- Resolved config artifacts show the effective chunk strategy and any effective token budgets.
- Token-aware chunk planning accounts for rendered chunk input, including chunk header/prompt overhead.
- Token-aware chunk planning keeps chunks within the resolved token budget or fails before model calls with a clear error.
- Token-aware reduce handling avoids silent over-budget reduce calls.
- Job `result.json` records strategy, budgets, token counts, character counts, and whether token counts are exact or estimated.
- `farm-status.json` exposes compact chunking strategy and chunk count metadata for primary AI inspection.
- `FARM_STATUS.md` shows the chunking strategy for chunked jobs without becoming noisy.
- Token-aware mode has deterministic unit tests that do not require Ollama, network access, or real model downloads.
- Config validation tests cover valid token settings, invalid strategy values, invalid token budgets, and backward-compatible character settings.
- Tokenizer availability tests cover supported model alias mapping and graceful unavailable behavior without requiring real tokenizer downloads.
- Chunk planning tests cover normal paragraphs, oversized paragraphs, prompt/header overhead, and expected lower chunk count for a representative long article-like input.
- README documents the tokenizer probe/setup path and how to verify token-aware chunking readiness.
- `docs/platforms.md` documents tokenizer dependency installation, local cache behavior, and troubleshooting.
- `docs/ai-usage.md` explains when a primary AI should use character strategy versus token strategy for a user.
- Backlog/roadmap doctor guidance includes tokenizer dependency/cache/readiness checks for less technical users.
- A clean `.run/dogfood_lite/` baseline is created before implementation changes.
- The same lite article files are rerun after token-aware chunking is enabled.
- `.run/dogfood_lite/DOGFOOD_LITE_REPORT.md` compares baseline versus token-aware runs.
- Backlog marks `BL-0014` implemented when this spec is implemented.

## Deferred To Roadmap

- Cross-run timing trend storage for dogfood benchmarks.
- Automatic selection of token-aware strategy by hardware profile.
- A `farm doctor` recommendation that writes ideal chunk settings for the user's system.
- Exact tokenizer adapters for additional model families beyond the first supported/local path.
- Estimated token fallback when exact local tokenization is unavailable.
- Token-per-second metrics from backend eval/generation fields.
- Progressive reduce quality tuning after first-pass budget safety exists.
- Token-aware chunking for non-summarize modes.
