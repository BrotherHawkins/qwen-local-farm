---
name: sift-operator
description: Run Sift farm jobs, inspect outputs, package results, and record dogfood evidence.
---

# Sift Operator

Use this skill when Sift is already available and the user wants to run local farm work over files, inspect outputs, package results, or compare dogfood runs.

The goal is reproducible local work. Prefer commands and artifacts that another AI or human can inspect later.

## Required Sift Commands

- `python sift.py farm doctor --json`
- `python sift.py farm run <input-folder> --output <output-folder> --mode summarize`
- `python sift.py farm run <input-folder> --output <output-folder> --mode prompt --instructions <instructions>`
- `python sift.py farm status <run-ref> --json`
- `python sift.py farm collect <run-ref> --output <output-folder> --label <label>`
- `python sift.py farm snippets pack <run-ref> --output <output-folder> --label <label>`
- `python sift.py farm synthesis bundle <run-ref> --output <output-folder> --label <label>`
- `python sift.py farm dogfood record <run-ref> --output <output-folder> --label <label>`
- `python sift.py farm dogfood timing record <run-ref> --output <output-folder> --label <label>`
- `python sift.py farm schema validate <path> --json`

## Operator Flow

1. Put transient inputs, downloaded/test artifacts, and outputs under `.run/`.
2. Use `python sift.py farm doctor --json` or inspect recent recommendation/config state before large jobs.
3. Choose `summarize` as the mature default mode unless the user gives a custom prompt.
4. Use `prompt` mode only when the user supplies clear instructions and accepts that outputs are less specialized than summarize mode.
5. Use `--include` and `--exclude` filters when the input folder needs reproducible file selection.
6. Use snippets or synthesis bundles when the output will feed a downstream frontier model.
7. Inspect `farm-status.json`, `FARM_STATUS.md`, `jobs/job-*/result.json`, `jobs/job-*/result.md`, raw response files when needed, and `timing-summary.json`.
8. Validate important JSON artifacts with `python sift.py farm schema validate <path> --json` before handing them to scripts or downstream AI workflows.
9. Use `farm collect` when the user wants ordinary per-file outputs gathered into one easier folder.
10. Use `farm snippets pack` when the user needs verified source evidence across files.
11. Use `farm synthesis bundle` when the user needs summaries plus evidence in one downstream-ready package.
12. Record dogfood quality or timing when the user is comparing changes across runs.
13. Report the run ID, final status, output path, counts, skipped files, rough timing, and any failures or warnings.

## Safety Boundaries

- Do not commit, push, or open PRs unless the user explicitly asks.
- Do not put downloaded article text, model outputs, or smoke artifacts in tracked files.
- Prefer simple, reproducible scripts and commands over manual browser or file work.
- Ask before changing `.sift-farm.json`, installing packages, downloading models, or changing long-lived environment settings.
- Preserve model-free CI assumptions.
- Treat Qwen as the tested default model family, while using Sift model metadata for other local models.

## Output Inspection Checklist

For a completed farm run, inspect:

- `farm-status.json`
- `FARM_STATUS.md`
- `farm-config.resolved.json`
- `timing-summary.json`
- `TIMING_SUMMARY.md`
- several `jobs/job-*/result.json`
- several `jobs/job-*/result.md`

For post-run packages, inspect both Markdown and JSON outputs. Prefer Markdown for human review and JSON for automation.

