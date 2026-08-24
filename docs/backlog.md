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
| BL-0007 | Open | 0001 | Full schema files for status/result validation | Could support stricter primary-AI consumption and CI validation. |
| BL-0008 | Open | 0001 | Skip-list overrides | Include/exclude controls for farm file discovery. |
| BL-0009 | Open | 0001 | Caller-provided retry/timeout behavior | Make failure policy configurable per run/request. |
| BL-0010 | Open | 0001 | `farm collect` | Helper for gathering results after a run. |
| BL-0011 | Open | 0001 | Queue-only execution | Submit work without processing immediately. |
| BL-0012 | Open | 0001 | Drop-folder scanning | Manual `farm scan` first, watcher later. |
| BL-0013 | Implemented | 0001 | Chunking | Implemented first for summarize mode by 0002; broader chunking remains tracked separately. |
| BL-0014 | Open | 0002, 0003 | Tokenizer-aware chunk sizing | Replace/augment character budgets with model-aware sizing. |
| BL-0015 | Open | 0002 | Markdown heading ancestry preservation | Preserve heading context in chunk inputs and outputs. |
| BL-0016 | Implemented | 0002 | Configurable chunk sizes | Chunk and reduce sizing are configurable via runtime profiles in 0003. |
| BL-0017 | Open | 0002 | Chunk retries separate from file retries | Retry individual chunks without rerunning the whole file job. |
| BL-0018 | Open | 0002 | Cross-file synthesis | Add a reduce/synthesis layer across file-level results. |
| BL-0019 | Open | 0002 | `farm status --json` | Machine-oriented status command for primary AI inspection. |
| BL-0020 | Open | 0003 | `farm doctor` for machine and Ollama inspection | Should produce human-readable and AI-readable setup reports. |
| BL-0021 | Open | 0003 | Benchmark-based profile recommendation | Recommend profiles from measured local performance. |
| BL-0022 | Open | 0003 | Automatic config writing from doctor output | Let an assistant or user safely write `.qwen-farm.json`. |
| BL-0023 | Open | 0003 | Hardware-specific model installation guidance | Help users pick/install models for CPU/GPU capacity. |
| BL-0024 | Open | 0003 | Per-mode profile fields beyond summarize and prompt | Extend runtime profiles as new modes become first-class. |
| BL-0025 | Open | 0003 | Dynamic concurrency adjustment after runtime failures | Back off after memory/timeouts or other resource failures. |
| BL-0026 | Open | 0003 | Remote/frontier model profiles | Allow profile-style config for non-local model execution if supported later. |
| BL-0027 | Implemented | 0004 | Bounded file-job scheduler concurrency | Implemented by 0004. |
| BL-0028 | Open | 0004 | Safe concurrency recommendation for `parallel_jobs` and `OLLAMA_NUM_PARALLEL` | Likely belongs with `farm doctor`. |
| BL-0029 | Open | 0004 | CLI helpers for starting Ollama with recommended concurrency env vars | Keep separate from scheduler behavior. |
| BL-0030 | Open | 0004 | Dynamic scheduler backoff after memory or timeout failures | Related to BL-0025, but scheduler-specific. |
| BL-0031 | Open | 0004 | Cross-run scheduling and background workers | Coordinate work across multiple submitted runs. |
| BL-0032 | Open | 0004 | Chunk-level parallelism using `concurrency.chunks` | Run chunks concurrently after file-level concurrency is stable. |
| BL-0033 | Open | 0004 | Multiple Ollama server pools | Advanced manual/managed routing across multiple local servers. |
| BL-0034 | Open | 0004 | Per-agent or per-model routing across loaded models | Resource-aware model selection and scheduling. |
| BL-0035 | Open | 0002 | Chunk overlap | Add overlap between adjacent chunks where useful without bloating context. |
| BL-0036 | Open | 0004 | Farm timing metrics in run/job/chunk artifacts | Record created/started/completed timestamps plus durations for runs, jobs, chunk map calls, and reduce calls. |
| BL-0037 | Open | 0004 | Dogfood benchmark history for timing regressions | Save comparable dogfood run summaries so slower runs can be spotted across implementation changes. |

## Notes

- If a new spec defers work, add or update backlog rows in the same PR.
- If a later spec implements an item, update its backlog status instead of leaving the old row stale.
- If several specs defer the same thing, reuse the existing backlog item and mention the additional source in notes.
