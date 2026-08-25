# Backlog

This backlog captures open deferred work from accepted and implemented specs. Roadmap sections describe broad direction; backlog items are durable follow-up candidates that should not be lost when a spec says "Deferred To Roadmap."

Status values:

- `Open`: not started.

Implemented or deprecated items should be removed from this file once the PR that resolves them lands. The implemented spec, plan, PR, and git history are the durable record for completed work.

## Groomed Near-Term Punchlist

This section is advisory. Specs and accepted plans still define what gets implemented, but this shortlist keeps the next product conversation from starting cold.

| Rank | Backlog | Candidate Next Work | Why Now |
| ---: | --- | --- | --- |
| 1 | BL-0099 | Skip non-retryable jobs by default in `retry-failed` | Builds directly on the new failure guidance after a little dogfood confidence. |
| 2 | BL-0065 | Reserved prompt-wrapper budget | Builds naturally on the new package budget controls by budgeting for surrounding downstream prompt text. |
| 3 | BL-0108 | Published AI skill packages | Builds on repo-local skill install helpers once they are reviewed. |

## Spec-Deferred Items

| ID | Status | Source | Item | Notes |
| --- | --- | --- | --- | --- |
| BL-0001 | Open | 0000, 0023 | Linting and formatting checks | Add style, Markdown, or prose gates only when they improve signal without slowing simple PRs too much. |
| BL-0003 | Open | 0000 | Run CI on Windows and macOS hosted runners | Keep hardware/model-free assumptions intact. |
| BL-0004 | Open | 0000 | Optional local Ollama/model integration tests | Should stay opt-in/local unless runner hardware is known. |
| BL-0005 | Open | 0000 | Scheduled benchmark checks on known hardware | Requires stable machine profile and benchmark corpus. |
| BL-0011 | Open | 0001 | Queue-only execution | Submit work without processing immediately. |
| BL-0012 | Open | 0001 | Drop-folder scanning | Manual `farm scan` first, watcher later. |
| BL-0018 | Open | 0002, 0010, 0011 | Cross-file synthesis | Add a reduce/synthesis layer across file-level results; 0010 and 0011 provide packaged inputs but do not synthesize. |
| BL-0025 | Open | 0003, 0025 | Dynamic concurrency adjustment after runtime failures | Back off after memory/timeouts or other resource failures; 0025 only drafts fixed retry policy knobs. |
| BL-0026 | Open | 0003 | Remote/frontier model profiles | Allow profile-style config for non-local model execution if supported later. |
| BL-0029 | Open | 0004, 0015 | CLI helpers for starting Ollama with recommended concurrency env vars | Keep separate from scheduler behavior; 0015 does not start services or set environment variables. |
| BL-0030 | Open | 0004, 0025 | Dynamic scheduler backoff after memory or timeout failures | Related to BL-0025, but scheduler-specific; 0025 keeps dynamic backoff deferred. |
| BL-0031 | Open | 0004 | Cross-run scheduling and background workers | Coordinate work across multiple submitted runs. |
| BL-0032 | Open | 0004, 0027 | Chunk-level parallelism using `concurrency.chunks` | Run chunks concurrently after file-level concurrency and in-progress chunk status are stable. |
| BL-0033 | Open | 0004 | Multiple Ollama server pools | Advanced manual/managed routing across multiple local servers. |
| BL-0034 | Open | 0004 | Per-agent or per-model routing across loaded models | Resource-aware model selection and scheduling. |
| BL-0039 | Open | 0006 | Additional tokenizer adapters | Add exact tokenizer support for model families beyond the supported Qwen/Ollama aliases. |
| BL-0040 | Open | 0006 | Estimated token fallback | Provide clearly labeled estimated token counting when exact local tokenization is unavailable. |
| BL-0041 | Open | 0005, 0006, 0027 | Token-per-second metrics | Capture backend eval/generation token metrics when available. |
| BL-0042 | Open | 0006 | Progressive reduce quality tuning | Improve multi-batch reduce quality after first-pass token budget safety exists. |
| BL-0046 | Open | 0007, 0010 | Quote and citation export formats | Export verified snippets in formats useful for citation-heavy downstream writing; 0010 only proposes generic Markdown/JSON packs. |
| BL-0047 | Open | 0007, 0010 | Semantic snippet selection | Consider embedding-assisted or retrieval-assisted snippet selection after deterministic cross-file packs exist. |
| BL-0048 | Open | 0007, 0010 | Snippet review states | Add accepted/rejected/superseded review state if snippet curation becomes a workflow. |
| BL-0050 | Open | 0009 | Automatic frontier-model dogfood grading | Use a frontier model to assist scoring later, while keeping the first local history workflow manual and model-free. |
| BL-0051 | Open | 0009 | Tracked aggregate dogfood history | Decide whether selected aggregate history should live in tracked docs once local records prove useful. |
| BL-0052 | Open | 0009 | Dogfood quality dashboard or charts | Build charts or a small dashboard for quality and timing trends if JSON/Markdown comparisons become too hard to scan. |
| BL-0053 | Open | 0009 | Statistical quality thresholds or CI gates | Define objective thresholds before adding pass/fail gates for subjective quality measures. |
| BL-0054 | Open | 0009, 0033 | Cross-machine benchmark normalization | Normalize dogfood timing and quality history across different local hardware profiles; 0033 keeps hardware recommendations conservative until this exists. |
| BL-0055 | Open | 0009, 0036 | Broader dogfood mode support | Extend dogfood quality records beyond summarize/snippet workflows now that extract mode exists. |
| BL-0056 | Open | 0010, 0034 | Cross-run snippet packs | Merge evidence across separate farm runs only after single-run snippet packs are stable; 0034 keeps the package-shaping work single-run only. |
| BL-0057 | Open | 0010, 0034 | Snippet pack browsing UI | Add UI or dashboard support for browsing snippet packs if Markdown/JSON packs are not enough; 0034 keeps browser/UI support deferred. |
| BL-0062 | Open | 0011, 0034 | Cross-run synthesis bundles | Merge summary/snippet evidence across separate farm runs after single-run bundles are stable; 0034 keeps package shaping scoped to one run. |
| BL-0063 | Open | 0014, 0034 | Exact downstream bundle tokenizer adapters | Add exact token counters for common downstream/frontier targets after estimated bundle budgets prove useful; 0034 continues using deterministic estimates. |
| BL-0065 | Open | 0014, 0034 | Reserved prompt-wrapper budget | Let callers reserve prompt space around a bundle so total downstream prompt size, not just bundle size, fits; 0034 leaves wrapper budgets deferred. |
| BL-0069 | Open | 0016 | Schema version migration guidance | Define compatibility and migration guidance across persisted farm artifact versions and newer CLI/report envelope versions. |
| BL-0070 | Open | 0016, 0034 | Generated schema documentation | Generate human-readable schema documentation from tracked schema files once contracts stabilize; 0034 updates schemas but does not generate prose from them. |
| BL-0071 | Open | 0016 | Strict schema mode | Add a stricter validation mode that rejects unknown/additional fields after artifact contracts mature. |
| BL-0073 | Open | 0022, 0033 | Automatic model-size upgrades or downgrades | Keep model id explicit until quality/performance tradeoffs are better specified. |
| BL-0074 | Open | 0022, 0033 | Automatic agent switching based on resource mode | Route from resource intent to a different agent only after explicit-agent preservation proves too manual. |
| BL-0075 | Open | 0022, 0025, 0028, 0029 | Runtime retry on a different resource mode after failure | Consider retrying CPU/hybrid after memory or placement failures once failure classes are reliable. |
| BL-0076 | Open | 0022, 0033 | GPU memory reservation or exact VRAM fit checks | Add stronger VRAM fit checks only when they can be measured without brittle platform assumptions. |
| BL-0077 | Open | 0023 | Generated dashboard rewriting | Generate or rewrite `SPEC_DASHBOARD.md` after the audit-only checker proves stable. |
| BL-0078 | Open | 0023 | Deferred-to-backlog semantic audits | Detect deferred follow-up bullets that are missing backlog rows beyond simple process documentation. |
| BL-0079 | Open | 0023 | Cross-file documentation link checking | Check broader docs links outside the spec/plans/dashboard surface. |
| BL-0080 | Open | 0024 | Farm collection archive export | Add zip or archive output after folder-based collections prove useful. |
| BL-0081 | Open | 0024 | Explicit raw/source artifact collection | Add opt-in flags for raw model responses, logs, source input files, or chunk artifacts once privacy and size tradeoffs are clear. |
| BL-0082 | Open | 0024 | Collection filters and templates | Let callers choose artifact types or manifest fields after the first fixed collection shape is stable. |
| BL-0083 | Open | 0024 | Cross-run collections | Merge collected outputs across multiple farm runs after single-run collection behavior is stable. |
| BL-0084 | Open | 0025, 0027 | Whole-run timeout enforcement | Add run-level deadline handling after first-pass fixed model-call timeout policy and in-progress visibility are stable. |
| BL-0085 | Open | 0025, 0027 | True wall-clock whole-file timeout | Separate whole-file elapsed deadline from the current per-model-call timeout behavior. |
| BL-0086 | Open | 0025, 0028, 0029 | Retry delay and backoff policy | Add retry delays, jitter, or exponential backoff only when fixed retry attempts are not enough. |
| BL-0088 | Open | 0025, 0026, 0028 | Cross-run chunk resume | Reuse successful chunk artifacts from a prior failed run when retrying chunked jobs. |
| BL-0089 | Open | 0025, 0026, 0028 | Partial reduce over missing chunks | Allow best-effort reduce over successful chunks only when the output contract can clearly mark partial coverage. |
| BL-0090 | Open | 0026 | Semantic chunking | Use semantic boundaries or retrieval-style grouping only after deterministic heading/overlap chunking is stable. |
| BL-0091 | Open | 0026 | Code-aware chunking | Split code by symbols, functions, classes, or language-aware units rather than generic paragraphs. |
| BL-0092 | Open | 0026 | Frontmatter-aware note splitting | Treat note metadata/frontmatter as structured context when chunking Markdown-like notes. |
| BL-0093 | Open | 0026, 0027 | Chunk visualization UI or dashboard | Make chunk boundaries, heading ancestry, overlap, live progress, and reduce flow easier to inspect visually if artifacts are not enough. |
| BL-0094 | Open | 0026 | Automatic overlap tuning | Adjust overlap from quality/timing evidence only after fixed overlap settings prove useful. |
| BL-0095 | Open | 0026, 0036 | First-class chunking for extract/classify/review modes | 0036 implemented first-class chunking for extract; classify and review still need mode-specific chunk safety, aggregation, and output contracts. |
| BL-0096 | Open | 0027 | `farm status --watch` or live polling helpers | Add a user-friendly watch/polling surface after stable in-progress status fields exist. |
| BL-0097 | Open | 0027, 0028, 0029 | Stale/interrupted run detection and repair | Detect or repair runs left `running` after process termination without confusing genuinely active runs. |
| BL-0099 | Open | 0029 | Skip non-retryable jobs by default in `retry-failed` | After failure classification is dogfooded, consider making `retry-failed` skip non-retryable jobs unless an explicit override is supplied. |
| BL-0100 | Open | 0030 | `.qwenignore` or repo-local ignore files | Add repo-local ignore files only after CLI/config include/exclude patterns prove useful. |
| BL-0101 | Open | 0030 | Force-include normally skipped text files from generated/vendor folders | Consider an explicit escape hatch for vendor/generated text files after first-pass safety semantics are dogfooded. |
| BL-0102 | Open | 0030 | Include/exclude controls for post-run helpers | Extend filtering to collection/package helpers only after farm-run discovery controls are stable. |
| BL-0103 | Open | 0030 | Richer structured discovery diagnostics and reason codes | Expand skipped-file diagnostics beyond the first-pass metadata if flat `skipped_files` remains too opaque. |
| BL-0105 | Open | 0031 | Non-Qwen dogfood benchmark matrix | Add quality/performance dogfood runs for selected non-Qwen local families only after adapter metadata exists. |
| BL-0106 | Open | 0031 | Product naming and CLI alias review | Revisit Qwen-centered naming only if broader model-family support becomes a real product promise. |
| BL-0108 | Open | 0032, 0035 | Published AI skill packages | Package or publish Sift skills for Codex, Claude Code, or other app ecosystems after local repo-shipped skills are stable; 0035 keeps publishing deferred. |
| BL-0109 | Open | 0032, 0033, 0035 | First-run interactive setup wizard | Add a guided setup wizard only if skill-driven doctor/recommend/apply/model-install guidance still feels too manual for less technical users. |
| BL-0110 | Open | 0032, 0035 | Generated skill metadata documentation | Generate docs from skill frontmatter if the skill library grows beyond a few hand-maintained skills; 0035 keeps docs hand-authored. |
| BL-0111 | Open | 0032, 0035 | Specialized Sift skills | Add focused skills for dogfood benchmarking, model extension, article ingestion, or advanced troubleshooting after the initial setup/operator skills are dogfooded. |
| BL-0112 | Open | 0032, 0035 | Skill manifest JSON Schema | Add a tracked schema for `skills/index.json` if the manifest starts being consumed by automation beyond the first model-free sync tests. |
| BL-0113 | Open | 0033, 0035 | Automatic Ollama/model installation helpers | Add explicit user-approved helper commands only after hardware-specific guidance proves accurate; 0035 installs AI skill folders only, not models. |
| BL-0114 | Open | 0036 | Model-assisted extract dedupe and ranking | Add an optional second-pass local model reduce for near-duplicate clustering and ranking after deterministic extract dedupe is dogfooded. |
| BL-0115 | Open | 0036 | Custom extraction schemas | Let callers define custom extraction fields or item types only after preset-based extract proves stable. |
| BL-0116 | Open | 0036 | First-class extract package helper | Add a post-run extract package helper if automatic `extract-results.json` and `farm collect` are not enough for frontier handoff. |
| BL-0117 | Open | 0036 | Semantic extract grouping | Consider embeddings, retrieval, or semantic clustering for extract only after deterministic grouping hits a clear quality ceiling. |
| BL-0118 | Open | 0036 | Source-offset citation exports | Export extract or snippet source references into citation-friendly formats using verified snippets and original-file character offsets. |

## Notes

- If a new spec defers work, add or update backlog rows in the same PR.
- If a later spec implements an item, remove that row from this backlog in the implementation PR.
- If several specs defer the same thing, reuse the existing backlog item and mention the additional source in notes.
- Treat the groomed punchlist as a living conversation aid, not a second source of truth.
