# 0000 Add Minimal PR Gate

Status: Implemented
Type: Add

## WHY

Sift is meant to become a tool that both humans and primary AIs can change over time. That only works if future changes have a small, reliable safety rail before merge.

This change adds the first gated PR check without tying public CI to local hardware, Ollama installation, downloaded model state, or long-running benchmarks.

The design favors:

- fast feedback over exhaustive validation
- pure unit tests over hardware-dependent integration tests
- GitHub-hosted repeatability over local machine assumptions
- a documented gate that non-power-users can ask an AI to set up or inspect

## Scope

This change adds a minimal GitHub Actions CI gate.

It covers:

- Python compilation checks
- fast unit test discovery
- GitHub Actions workflow setup
- documentation for enabling required checks on `main`

## Non-Goals

This change does not add:

- Ollama startup in CI
- model downloads in CI
- GPU/VRAM checks in CI
- benchmark execution in CI
- linting or formatting gates
- release packaging
- cross-platform runner coverage

## Behavior

### Workflow

Add a GitHub Actions workflow:

```text
.github/workflows/ci.yml
```

The workflow runs on:

- pull requests
- pushes to `main`

The workflow checks supported Python versions without installing project-specific dependencies.

### Checks

The gate runs:

```bash
python -m compileall sift.py examples src tests
python -m unittest discover -s tests -p "test_*.py"
```

The gate is expected to remain fast and deterministic.

### Required Check Setup

The repository owner can make this gate mandatory through GitHub branch protection or rulesets after the workflow reports at least once.

Recommended protection behavior:

- require a pull request before merging to `main`
- require the CI status checks to pass before merging

## Acceptance Criteria

- A GitHub Actions workflow exists at `.github/workflows/ci.yml`.
- The workflow runs on pull requests.
- The workflow runs on pushes to `main`.
- The workflow compiles `sift.py`, `examples`, `src`, and `tests`.
- The workflow runs stdlib `unittest` discovery under `tests`.
- The workflow does not start Ollama.
- The workflow does not download models.
- The workflow does not require GPU hardware.
- At least one unit test module exists so the gate validates more than compilation.
- Documentation explains how to make the workflow a required PR check in GitHub.

## Deferred To Roadmap

- Linting and formatting checks.
- Generated spec/dashboard consistency checks.
- Running the gate on Windows and macOS hosted runners.
- Optional local integration tests for Ollama and installed models.
- Optional scheduled benchmark checks on a machine with known hardware.
