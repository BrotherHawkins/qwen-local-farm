---
name: sift-setup
description: Guide a user through Sift setup, diagnosis, configuration, and a first smoke test.
---

# Sift Setup

Use this skill when a user wants help cloning, installing, diagnosing, configuring, or first-running Sift.

The goal is to make setup feel guided and beginner-friendly. Prefer Sift's read-only reports and preview commands before changing the user's machine.

## Required Sift Commands

- `python sift.py --help`
- `python sift.py farm doctor --json`
- `python sift.py farm recommend --json`
- `python sift.py farm recommend apply --json`
- `python sift.py farm recommend apply --write --json`
- `python sift.py farm tokenizer status`
- `python sift.py farm tokenizer setup`
- `python sift.py farm run <input-folder> --mode summarize --output <output-folder>`
- `python sift.py farm status <run-ref> --json`
- `python sift.py farm schema validate <path> --json`

## Setup Flow

1. Confirm the user has cloned Sift and that your current working directory is the Sift repo root.
2. Read `README.md`, `docs/platforms.md`, and `docs/ai-usage.md` as needed.
3. Run `python sift.py --help` to confirm the entrypoint works.
4. Run `python sift.py farm doctor --json` and inspect the JSON before summarizing.
5. Explain doctor status in plain language: Python, Ollama, selected model, tokenizer readiness, runtime profile, and recent runs.
6. If Ollama, Python, or the selected model is missing, explain the next command before running anything that installs software or downloads a model.
7. Run `python sift.py farm recommend --json` only after the local service/model state is ready enough for the tiny probe.
8. Preview config changes with `python sift.py farm recommend apply --json`.
9. Ask before running `python sift.py farm recommend apply --write --json` because it writes `.sift-farm.json`.
10. Run tokenizer setup only when useful for token-aware chunking, and ask before downloading tokenizer assets.
11. Create tiny smoke-test inputs and outputs under `.run/`, then run a small `farm run`.
12. Inspect `farm-status.json`, `FARM_STATUS.md`, job `result.json`, job `result.md`, and `timing-summary.json`.
13. Validate important JSON artifacts with `python sift.py farm schema validate <path> --json`.
14. End with the current run ID, final status, output path, and the next useful action.

## Safety Boundaries

- Do not commit, push, or open PRs unless the user explicitly asks.
- Do not put smoke inputs, downloaded text, model outputs, or local reports in tracked files.
- Prefer `.run/` for all temporary setup, smoke, and report artifacts.
- Ask before installing packages.
- Ask before downloading models or tokenizer assets.
- Ask before writing `.sift-farm.json`.
- Ask before changing long-lived environment variables or shell profiles.
- Preserve Sift's model-free CI assumptions.

## Beginner Explanation Style

Use plain language. Translate local model terms into practical meaning:

- Ollama is the local model runner.
- Qwen is Sift's tested default model family.
- Tokenizers help Sift split long files more accurately.
- Doctor checks the current setup without changing it.
- Recommend measures a tiny local probe and suggests conservative settings.
- `.run/` is where local experiments and generated artifacts should go.

