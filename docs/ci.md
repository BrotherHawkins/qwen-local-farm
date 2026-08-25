# CI And PR Gating

This project uses a small GitHub Actions check as the first gated PR build.

The gate is intentionally lightweight:

- compile Python files
- run fast unit tests
- check spec dashboard consistency
- avoid Ollama, model pulls, GPU checks, or long benchmarks

That keeps public PR validation predictable on GitHub-hosted runners while local machines remain responsible for model and hardware-specific verification.

## Workflow

The workflow lives at:

```text
.github/workflows/ci.yml
```

It runs on:

- every pull request
- every push to `main`

It currently tests Python:

```text
3.10
3.12
3.13
```

## Local Equivalent

Run these before pushing when touching Python:

```bash
python -m compileall sift.py examples src tests
python -m unittest discover -s tests -p "test_*.py"
python -m src.qwen_spec_guard
```

## GitHub Required Check Setup

After the workflow has run at least once on GitHub, protect `main` with a branch rule or ruleset.

Recommended minimum:

- require a pull request before merging
- require status checks to pass
- select the `ci` workflow jobs as required checks

GitHub only offers a status check for selection after that check has reported at least once.

## Out Of Scope For The Gate

Do not add these to the default PR gate without a separate spec/change:

- downloading models
- starting Ollama
- testing GPU or VRAM behavior
- running benchmark scripts
- calling external paid services
- requiring platform-specific tools beyond Python and GitHub Actions
