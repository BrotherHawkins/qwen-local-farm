# Dogfood Timing History

Dogfood timing history is a local-first way to compare farm run performance over time. It records compact timing metrics from existing run artifacts without making model calls and without copying article text, raw responses, full summaries, or full snippets.

Generated timing history lives under:

```text
.run/dogfood_timing/
```

## Record Timing

Record an existing farm run:

```powershell
python sift.py farm dogfood timing record <run-ref> --label 0019-lite-baseline
```

The default output folder is:

```text
.run/dogfood_timing/runs/
```

Timing records include:

- run ID, label, status, mode, agent, model, profile, and commit
- compact runtime settings, including concurrency and summarize sizing
- total duration, jobs, chunks, calls, queue wait, and model-call duration
- aggregate duration by call kind, such as `single`, `chunk_map`, and `reduce`
- per-job duration, queue wait, chunks, calls, call duration, warning count, and status
- slowest jobs and slowest calls

## Compare Timing

Compare two timing records:

```powershell
python sift.py farm dogfood timing compare .run/dogfood_timing/runs/0019-lite-baseline.json .run/dogfood_timing/runs/0019-lite-candidate.json
```

The default comparison output folder is:

```text
.run/dogfood_timing/comparisons/
```

Comparison output includes:

- JSON for scripts and primary AIs
- Markdown for quick human review
- total duration, queue, chunk, call, and call-kind deltas
- per-job timing deltas
- candidate slowest jobs and calls
- comparability notes when model, profile, commit, concurrency, chunk sizing, or snippet policy changed

## How To Read It

Use timing history when a run feels slower or after changing prompts, chunking, snippets, scheduling, profiles, or model settings.

Look first at comparability notes. A faster or slower candidate is less meaningful when the model, profile, chunk size, or concurrency changed.

Then inspect totals:

- higher `chunks` usually means more model calls
- higher `calls` means more backend work
- higher `queue_wait_ms` points at scheduler contention
- higher `chunk_map` duration means first-pass chunk work dominated
- higher `reduce` duration means synthesis/reduction dominated

Use `docs/dogfood-quality.md` separately when judging output usefulness. Timing history intentionally does not include quality scores.

## Privacy And Noise Rules

Timing records intentionally omit:

- raw article text
- raw model responses
- full summary Markdown
- full source snippet text
- snippet pack contents

Keep generated timing history in `.run/` unless the project explicitly decides to track aggregate benchmark files later.
