# 0006 Implement Tokenizer-Aware Chunk Sizing

Status: Implemented
Change Spec: [0006 Add Tokenizer-Aware Chunk Sizing](../changes/0006-add-tokenizer-aware-chunk-sizing.md)

## WHY

Dogfood showed that the current paragraph-character chunker can over-split real article inputs. The clearest example was article 004: roughly 15,600 estimated tokens became 9 chunks because the farm enforced an 8,000 character body budget instead of planning against the model context window.

This plan adds exact local token counting for the supported Qwen/Ollama agents, then makes tokenizer-aware summarize chunking an opt-in setting. The implementation should reduce unnecessary map/reduce calls without changing the default character-based behavior.

## Scope

Planned:

- clean `dogfood_lite` baseline before behavior changes
- local tokenizer setup/probe command for supported Qwen/Ollama agents
- exact cached Hugging Face tokenizer loading for supported aliases
- backward-compatible summarize config validation
- CLI overrides for token-aware chunk settings
- token-aware paragraph chunk planning
- token-aware oversized paragraph splitting
- token-aware reduce budget protection
- chunk/result/status metadata for strategy, budgets, chars, tokens, and exact-count status
- docs for README, platform setup, and primary AI usage
- dogfood_lite token-aware rerun and comparison report
- backlog/spec/dashboard lifecycle updates in the implementation PR
- model-free tests

Deferred:

- defaulting built-in profiles to token-aware chunking
- automatic hardware/profile selection of token chunk settings
- `farm doctor` implementation
- tokenizer adapters beyond the supported Qwen/Ollama model aliases
- estimated token fallback
- token/sec backend metrics
- progressive reduce quality tuning beyond first-pass budget safety
- token-aware chunking for non-summarize modes

## Implementation Plan

### 1. Capture Dogfood Lite Baseline

Before changing farm chunk behavior, create:

```powershell
.run/dogfood_lite/
.run/dogfood_lite/articles-text/
.run/dogfood_lite/baseline/
```

Copy the same article text files from the existing dogfood corpus:

- `002-the-append-and-review-note-karpathy.txt`
- `004-tags-guide-obsidian-claude-code-karpathy-pkm-llm.txt`
- `005-karpathy-llm-wiki-starter-vault.txt`
- `009-qmd-query-markup-documents.txt`

Run the current character chunker with stable settings:

```powershell
python sift.py farm run .run/dogfood_lite/articles-text --output .run/dogfood_lite/baseline/farm-results --mode summarize --instructions "Summarize the article for later synthesis. Capture thesis, key claims, useful examples, and open questions." --agent default --parallel-jobs 1
```

Record:

- run ID and status
- resolved model/profile/settings
- chunk counts by article
- model call counts by article
- run/job/call timings
- warnings or failures
- summary quality notes

If local Ollama is unavailable, record that blocker and continue with model-free implementation/tests.

### 2. Add Tokenizer Support Module

Add a small module, likely `src/qwen_farm_tokenizer.py`, that provides:

- supported Ollama alias to Hugging Face tokenizer ID mapping
- tokenizer dependency availability check
- local cache path resolution
- exact token counter loading with `local_files_only=True` during normal counting
- optional setup/probe path that is allowed to populate the local ignored cache
- clear unavailable errors with next-step guidance

Supported first-pass mapping:

| Ollama model | Tokenizer ID |
| --- | --- |
| `qwen3.5:4b` | `Qwen/Qwen3.5-4B` |
| `qwen3:4b` | `Qwen/Qwen3-4B` |
| `qwen3:8b` | `Qwen/Qwen3-8B` |
| `qwen3:14b` | `Qwen/Qwen3-14B` |

Keep tokenizer cache files under `.run/tokenizers/` or another ignored path.

### 3. Add Tokenizer Probe CLI

Add a command such as:

```powershell
python sift.py farm tokenizer setup
python sift.py farm tokenizer status
```

or an equivalently clear command shape chosen during implementation.

The setup/probe command should:

- explain required Python packages if missing
- download/cache tokenizer assets only when explicitly invoked
- verify online setup succeeded
- verify offline/local-only reload succeeds
- print human-readable status
- write an AI-readable report under `.run/`, if simple

Do not require this command in GitHub CI.

### 4. Extend Runtime Config

Update `src/qwen_farm_profiles.py` and CLI override plumbing to support:

- `summarize.chunk_strategy`: `character` or `token`
- `summarize.chunk_tokens`
- `summarize.reduce_tokens`
- `summarize.token_safety_margin`

Preserve:

- existing flat `chunk_chars` / `reduce_chars`
- existing profile defaults
- existing CLI behavior when no token flags are passed

Add validation for strategy values, positive token budgets, and safety margin bounds.

### 5. Resolve Token Budgets

When token strategy is selected:

- get the effective model from the resolved runtime config
- get the effective model context limit from agent options when available
- derive conservative token budgets when explicit budgets are absent
- reserve room for farm prompt text, chunk headers, expected output, and safety margin
- persist the resolved strategy and budgets in runtime config artifacts

Do not silently use model marketing context length if the agent config has a smaller `num_ctx`; the runtime `num_ctx` is the practical limit.

### 6. Implement Token-Aware Chunk Planning

Extend `src/qwen_farm_chunks.py` with a tokenizer-aware planning path while leaving the character path intact.

The token planner should:

- keep paragraph-aware packing where practical
- count rendered chunk input, including source path/chunk header overhead
- split oversized paragraphs by smaller boundaries when possible
- fall back to hard token-safe slices only when necessary
- guarantee planned chunk input stays within the resolved token budget
- produce chunk metadata with chars and tokens

Avoid changing chunk artifact paths unless necessary.

### 7. Protect Reduce Calls

Update reduce input construction so token-aware runs do not silently exceed `reduce_tokens`.

First-pass acceptable behavior:

- progressive reduce batching under budget, or
- a clear pre-reduce failure before sending an oversized reduce prompt

Prefer progressive batching if it stays simple; otherwise fail clearly and leave quality tuning for follow-up.

### 8. Persist Metadata In Artifacts

Update result/status writers so primary AIs can inspect chunking behavior without reverse engineering file names.

Add compact metadata to:

- per-job `result.json`
- `farm-status.json`
- `FARM_STATUS.md`
- chunk result JSON where useful

Include:

- strategy
- tokenizer ID
- `counts_are_estimated: false`
- character budget or token budget
- chunk count
- per-chunk character count
- per-chunk token count

Keep existing consumers compatible with added fields.

### 9. Update Docs And Backlog

Update:

- `README.md`: tokenizer setup/probe command and token-aware chunking quick note
- `docs/platforms.md`: dependency installation, cache location, offline verification, troubleshooting
- `docs/ai-usage.md`: when a primary AI should enable token-aware chunking and how to inspect readiness
- `docs/backlog.md`: mark `BL-0014` implemented when behavior lands; keep doctor-related items open
- `docs/roadmap.md`: note tokenizer-aware chunking status and doctor follow-ups
- spec/dashboard statuses when the implementation PR is ready

### 10. Run Dogfood Lite Token-Aware Comparison

After implementation, enable token-aware chunking in settings or CLI and run:

```powershell
python sift.py farm run .run/dogfood_lite/articles-text --output .run/dogfood_lite/token-aware/farm-results --mode summarize --instructions "Summarize the article for later synthesis. Capture thesis, key claims, useful examples, and open questions." --agent default --parallel-jobs 1 --chunk-strategy token
```

Write:

```powershell
.run/dogfood_lite/DOGFOOD_LITE_REPORT.md
```

Compare baseline versus token-aware:

- run IDs and final statuses
- model/profile/settings
- chunks by article
- calls by article
- run/job/call timings
- warnings/failures
- summary usefulness

## Test Plan

Automated tests:

- existing character config remains valid
- invalid chunk strategy is rejected
- invalid token budgets and safety margin are rejected
- CLI token overrides affect resolved config
- supported model aliases map to expected tokenizer IDs
- tokenizer unavailable errors are clear and model-free
- tokenizer setup/status code can be tested with fake tokenizer loader/cache
- token-aware chunk planning counts rendered chunk input overhead
- token-aware planner keeps chunks under token budget
- token-aware oversized paragraph splitting works
- representative article-like text produces fewer token chunks than character chunks
- reduce budget overflow does not silently call the model
- result/status metadata includes strategy, budgets, chars, tokens, and exact-count status
- existing summarize chunk tests still pass

Verification before PR:

```powershell
python -m unittest discover -s tests
python -m compileall sift.py src tests
git diff --check
```

Local tokenizer verification:

```powershell
python sift.py farm tokenizer setup
python sift.py farm tokenizer status
```

Dogfood verification:

```powershell
python sift.py farm list
python sift.py farm status <baseline-run-id>
python sift.py farm status <token-aware-run-id>
```

Inspect:

- `.run/dogfood_lite/baseline/farm-results/farm-status.json`
- `.run/dogfood_lite/token-aware/farm-results/farm-status.json`
- `.run/dogfood_lite/token-aware/farm-results/FARM_STATUS.md`
- several per-job `result.json` files
- `.run/dogfood_lite/DOGFOOD_LITE_REPORT.md`

## Acceptance Checklist

- [x] Change spec exists.
- [x] Human accepted the behavior target.
- [x] Implementation plan exists.
- [x] Human accepted the implementation plan.
- [x] Dogfood_lite baseline is captured before behavior changes.
- [x] Local tokenizer setup/probe path exists.
- [x] Exact local token counting works for supported Qwen/Ollama agents.
- [x] Token-aware chunking is opt-in through settings.
- [x] Token-aware chunking is opt-in through CLI overrides.
- [x] Character chunking remains the default.
- [x] Existing character settings remain backward compatible.
- [x] Token-aware planner accounts for rendered input overhead.
- [x] Token-aware planner keeps chunk inputs under budget.
- [x] Reduce budget handling avoids silent over-budget calls.
- [x] Result/status artifacts expose chunk strategy and token metadata.
- [x] README documents tokenizer setup and readiness verification.
- [x] Platform docs document dependencies, cache behavior, and troubleshooting.
- [x] AI usage docs explain when to enable token-aware chunking.
- [x] `BL-0014` is marked implemented when behavior lands.
- [x] Doctor-related backlog items remain open.
- [x] Model-free unit tests cover the tokenization/chunking contract.
- [x] Compile check passes.
- [x] Dogfood_lite token-aware rerun and comparison report are recorded.
