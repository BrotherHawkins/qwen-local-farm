# Backlog

This backlog captures deferred work from accepted and implemented specs. Roadmap sections describe broad direction; backlog items are durable follow-up candidates that should not be lost when a spec says "Deferred To Roadmap."

Status values:

- `Open`: not started.
- `Planned`: tied to an accepted spec or implementation plan.
- `Implemented`: landed in code/docs/tests.
- `Deprecated`: no longer desired.

## Spec-Deferred Items

| ID | Status | Source | Item | Notes |
| --- | --- | --- | --- | --- |
| BL-0001 | Open | 0000 | Linting and formatting checks | Add style gates only when they improve signal without slowing simple PRs too much. |
| BL-0002 | Open | 0000 | Generated spec/dashboard consistency checks | Could validate dashboard counts, status values, and missing plans/spec links. |
| BL-0003 | Open | 0000 | Run CI on Windows and macOS hosted runners | Keep hardware/model-free assumptions intact. |
| BL-0004 | Open | 0000 | Optional local Ollama/model integration tests | Should stay opt-in/local unless runner hardware is known. |
| BL-0005 | Open | 0000 | Scheduled benchmark checks on known hardware | Requires stable machine profile and benchmark corpus. |
| BL-0006 | Open | 0001 | CLI spelling for future non-MVP modes | Revisit before adding `extract`, `classify`, or `review`. |
| BL-0007 | Implemented | 0001, 0016 | Full schema files for status/result validation | 0016 implemented tracked schemas and model-free validation coverage for key farm JSON artifacts. |
| BL-0008 | Open | 0001 | Skip-list overrides | Include/exclude controls for farm file discovery. |
| BL-0009 | Open | 0001 | Caller-provided retry/timeout behavior | Make failure policy configurable per run/request. |
| BL-0010 | Open | 0001 | `farm collect` | Helper for gathering results after a run. |
| BL-0011 | Open | 0001 | Queue-only execution | Submit work without processing immediately. |
| BL-0012 | Open | 0001 | Drop-folder scanning | Manual `farm scan` first, watcher later. |
| BL-0013 | Implemented | 0001 | Chunking | Implemented first for summarize mode by 0002; broader chunking remains tracked separately. |
| BL-0014 | Implemented | 0002, 0003, 0006 | Tokenizer-aware chunk sizing | Implemented by 0006 as opt-in exact local tokenizer-aware summarize chunk sizing. |
| BL-0015 | Open | 0002 | Markdown heading ancestry preservation | Preserve heading context in chunk inputs and outputs. |
| BL-0016 | Implemented | 0002 | Configurable chunk sizes | Chunk and reduce sizing are configurable via runtime profiles in 0003. |
| BL-0017 | Open | 0002 | Chunk retries separate from file retries | Retry individual chunks without rerunning the whole file job. |
| BL-0018 | Open | 0002, 0010, 0011 | Cross-file synthesis | Add a reduce/synthesis layer across file-level results; 0010 and 0011 provide packaged inputs but do not synthesize. |
| BL-0019 | Implemented | 0002, 0013 | `farm status --json` | 0013 implemented machine-readable JSON output for farm overview and single-run inspection. |
| BL-0020 | Implemented | 0003, 0006, 0015 | `farm doctor` for machine, Ollama, and tokenizer inspection | 0015 implemented read-only human/JSON setup reports with tokenizer readiness and next-step guidance for less technical users. |
| BL-0021 | Open | 0003, 0006, 0015 | Benchmark-based profile recommendation | Recommend profiles and token-aware chunk settings from measured local performance; 0015 only reports conservative static guidance. |
| BL-0022 | Open | 0003, 0006, 0015 | Automatic config writing from doctor output | Let an assistant or user safely write `.qwen-farm.json`, including tokenizer-aware chunk settings when ready; 0015 remains read-only. |
| BL-0023 | Open | 0003, 0015 | Hardware-specific model installation guidance | Help users pick/install models for CPU/GPU capacity; 0015 only reports current setup and next commands. |
| BL-0024 | Open | 0003 | Per-mode profile fields beyond summarize and prompt | Extend runtime profiles as new modes become first-class. |
| BL-0025 | Open | 0003 | Dynamic concurrency adjustment after runtime failures | Back off after memory/timeouts or other resource failures. |
| BL-0026 | Open | 0003 | Remote/frontier model profiles | Allow profile-style config for non-local model execution if supported later. |
| BL-0027 | Implemented | 0004 | Bounded file-job scheduler concurrency | Implemented by 0004. |
| BL-0028 | Open | 0004, 0015 | Safe concurrency recommendation for `parallel_jobs` and `OLLAMA_NUM_PARALLEL` | Likely belongs with `farm doctor`; 0015 may include conservative static guidance but no benchmark-based recommendation. |
| BL-0029 | Open | 0004, 0015 | CLI helpers for starting Ollama with recommended concurrency env vars | Keep separate from scheduler behavior; 0015 does not start services or set environment variables. |
| BL-0030 | Open | 0004 | Dynamic scheduler backoff after memory or timeout failures | Related to BL-0025, but scheduler-specific. |
| BL-0031 | Open | 0004 | Cross-run scheduling and background workers | Coordinate work across multiple submitted runs. |
| BL-0032 | Open | 0004 | Chunk-level parallelism using `concurrency.chunks` | Run chunks concurrently after file-level concurrency is stable. |
| BL-0033 | Open | 0004 | Multiple Ollama server pools | Advanced manual/managed routing across multiple local servers. |
| BL-0034 | Open | 0004 | Per-agent or per-model routing across loaded models | Resource-aware model selection and scheduling. |
| BL-0035 | Open | 0002 | Chunk overlap | Add overlap between adjacent chunks where useful without bloating context. |
| BL-0036 | Implemented | 0004, 0005 | Farm timing metrics in run/job/chunk artifacts | Implemented by 0005 for runs, jobs, chunk map calls, reduce calls, and timing summary artifacts. |
| BL-0037 | Implemented | 0004, 0006, 0019 | Dogfood benchmark history for timing regressions | 0019 implemented local timing history records and comparisons so slower runs can be spotted across implementation changes. |
| BL-0038 | Open | 0005 | In-progress chunk and reduce timing/status visibility | Dogfood showed chunk artifacts appear while jobs run, but `farm-status.json` does not yet surface active chunk/reduce progress until job completion. |
| BL-0039 | Open | 0006 | Additional tokenizer adapters | Add exact tokenizer support for model families beyond the supported Qwen/Ollama aliases. |
| BL-0040 | Open | 0006 | Estimated token fallback | Provide clearly labeled estimated token counting when exact local tokenization is unavailable. |
| BL-0041 | Open | 0005, 0006 | Token-per-second metrics | Capture backend eval/generation token metrics when available. |
| BL-0042 | Open | 0006 | Progressive reduce quality tuning | Improve multi-batch reduce quality after first-pass token budget safety exists. |
| BL-0043 | Open | 0006 | Token-aware chunking for non-summarize modes | Extend token-aware sizing beyond summarize once those modes have chunk-safe contracts. |
| BL-0044 | Implemented | 0007, 0008 | Advanced snippet ranking | 0008 implemented deterministic scoring, diversity, and diagnostics; semantic ranking remains separate in BL-0047. |
| BL-0045 | Implemented | 0007, 0010 | Cross-file snippet packs | 0010 implemented deterministic Markdown/JSON snippet packs from existing summarize run artifacts for later synthesis workflows. |
| BL-0046 | Open | 0007, 0010 | Quote and citation export formats | Export verified snippets in formats useful for citation-heavy downstream writing; 0010 only proposes generic Markdown/JSON packs. |
| BL-0047 | Open | 0007, 0010 | Semantic snippet selection | Consider embedding-assisted or retrieval-assisted snippet selection after deterministic cross-file packs exist. |
| BL-0048 | Open | 0007, 0010 | Snippet review states | Add accepted/rejected/superseded review state if snippet curation becomes a workflow. |
| BL-0049 | Implemented | 0007, 0008, 0009 | Snippet quality benchmark history | 0009 implemented local dogfood history records and baseline/candidate comparisons under `.run/dogfood_history/`. |
| BL-0050 | Open | 0009 | Automatic frontier-model dogfood grading | Use a frontier model to assist scoring later, while keeping the first local history workflow manual and model-free. |
| BL-0051 | Open | 0009 | Tracked aggregate dogfood history | Decide whether selected aggregate history should live in tracked docs once local records prove useful. |
| BL-0052 | Open | 0009 | Dogfood quality dashboard or charts | Build charts or a small dashboard for quality and timing trends if JSON/Markdown comparisons become too hard to scan. |
| BL-0053 | Open | 0009 | Statistical quality thresholds or CI gates | Define objective thresholds before adding pass/fail gates for subjective quality measures. |
| BL-0054 | Open | 0009 | Cross-machine benchmark normalization | Normalize dogfood timing and quality history across different local hardware profiles. |
| BL-0055 | Open | 0009 | Broader dogfood mode support | Extend dogfood quality records beyond summarize/snippet workflows when additional farm modes mature. |
| BL-0056 | Open | 0010 | Cross-run snippet packs | Merge evidence across separate farm runs only after single-run snippet packs are stable. |
| BL-0057 | Open | 0010 | Snippet pack browsing UI | Add UI or dashboard support for browsing snippet packs if Markdown/JSON packs are not enough. |
| BL-0058 | Implemented | 0010, 0012 | Run-ID lookup for post-run helpers | 0012 implemented exact known run ID lookup for `farm snippets pack`, `farm synthesis bundle`, and `farm dogfood record` while preserving full path input. |
| BL-0059 | Implemented | 0010, 0011 | Summary-plus-snippet synthesis bundles | 0011 implemented post-run Markdown/JSON bundles that combine compact per-file summaries with selected verified snippets. |
| BL-0060 | Open | 0011 | Summary bundle field filters and templates | Let callers choose which summary fields appear in synthesis bundles. |
| BL-0061 | Implemented | 0011, 0014 | Bundle token or character budget planning | 0014 implemented size estimates plus optional character and estimated-token caps for synthesis bundles. |
| BL-0062 | Open | 0011 | Cross-run synthesis bundles | Merge summary/snippet evidence across separate farm runs after single-run bundles are stable. |
| BL-0063 | Open | 0014 | Exact downstream bundle tokenizer adapters | Add exact token counters for common downstream/frontier targets after estimated bundle budgets prove useful. |
| BL-0064 | Open | 0014 | Configurable bundle fitting policies | Let callers choose evidence-first, summary-first, or balanced budget fitting instead of one deterministic default. |
| BL-0065 | Open | 0014 | Reserved prompt-wrapper budget | Let callers reserve prompt space around a bundle so total downstream prompt size, not just bundle size, fits. |
| BL-0066 | Open | 0014 | Budget planning for snippet packs | Add similar size estimation and optional caps to snippet-only packs. |
| BL-0067 | Implemented | 0016, 0018 | Schemas for post-run package artifacts | 0018 implemented schemas and validator auto-detection for timing summaries, snippet packs, synthesis bundles, dogfood history, and comparison outputs. |
| BL-0068 | Implemented | 0016, 0017 | Public schema validation CLI | 0017 implemented `farm schema validate <path>` with explicit schema selection, auto-detection, JSON output, and script-friendly exit codes. |
| BL-0069 | Open | 0016 | Schema version migration guidance | Define compatibility and migration guidance across persisted farm artifact versions and newer CLI/report envelope versions. |
| BL-0070 | Open | 0016 | Generated schema documentation | Generate human-readable schema documentation from tracked schema files once contracts stabilize. |
| BL-0071 | Open | 0016 | Strict schema mode | Add a stricter validation mode that rejects unknown/additional fields after artifact contracts mature. |

## Notes

- If a new spec defers work, add or update backlog rows in the same PR.
- If a later spec implements an item, update its backlog status instead of leaving the old row stale.
- If several specs defer the same thing, reuse the existing backlog item and mention the additional source in notes.
