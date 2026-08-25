# 0015 Add Farm Doctor

Status: Implemented
Type: Add

## WHY

The farm now has enough moving parts that setup and resource-fit diagnosis is a real workflow: Python, Ollama, installed local models, runtime profiles, tokenizer readiness, concurrency choices, config files, and generated status artifacts. Power users can inspect those pieces manually, but less technical users need a primary AI to do the hard part: run one command, inspect a durable report, explain what is ready, and recommend the next safe command.

The farm should provide a first `doctor` command that creates a read-only setup and capability report for humans, scripts, and primary AIs.

This change favors:

- read-only inspection over automatic mutation
- local, model-free diagnostics
- durable Markdown and JSON reports under `.run/`
- clear next commands for setup gaps
- conservative recommendations for non-technical users
- preserving CI/model-free assumptions

## Scope

This change adds a first farm doctor command:

- add `python sift.py farm doctor`
- add `python sift.py farm doctor --json`
- inspect OS, Python version, repo root, and key local paths
- inspect whether the Ollama executable is discoverable
- inspect whether the configured Ollama endpoint responds
- inspect installed Ollama model names when the endpoint is reachable
- inspect configured/default agents and their model names
- inspect resolved farm runtime config for the default agent/profile
- inspect tokenizer dependency and cache readiness for supported Qwen/Ollama aliases
- inspect whether the configured/default model appears installed when Ollama is reachable
- report recent known farm runs using existing run discovery
- produce a human-readable Markdown report
- produce a machine-readable JSON report
- write reports under `.run/reports/` by default
- include compact recommendations and next commands
- update BL-0020 from open to planned/implemented as lifecycle progresses

## Non-Goals

This change does not add:

- automatic config writing
- benchmark-based profile selection
- model pulls or installs
- tokenizer downloads
- starting or stopping Ollama
- GPU/VRAM probing beyond fields that are already cheap and reliable in standard Python
- changing `.sift-farm.json`
- changing agent files
- CI checks that require Ollama or a model
- exact performance prediction
- multiple Ollama server pool management

## Behavior

### CLI Shape

Human-readable default:

```powershell
python sift.py farm doctor
```

Machine-readable output:

```powershell
python sift.py farm doctor --json
```

Suggested options:

```powershell
python sift.py farm doctor --output .run/reports
python sift.py farm doctor --agent default
python sift.py farm doctor --profile local-8gb
```

The first implementation should prefer `farm doctor` over the older roadmap sketch of top-level `python sift.py doctor`, keeping farm diagnostics under the existing farm command group.

### Output Files

By default, the command writes:

```text
.run/reports/setup-doctor.md
.run/reports/setup-doctor.json
```

`farm doctor` prints the Markdown report to stdout after writing the files.

`farm doctor --json` prints the JSON report to stdout after writing the files. JSON stdout should contain no Markdown or explanatory prose.

### JSON Shape

The first report shape should be stable enough for primary AI inspection:

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-24T18:30:00Z",
  "status": "ready_with_warnings",
  "root": "C:/Github/GHE/sift",
  "environment": {
    "os": "Windows",
    "python": "3.13.5",
    "python_ok": true
  },
  "ollama": {
    "executable": "C:/Users/.../ollama.exe",
    "found": true,
    "base_url": "http://127.0.0.1:11434",
    "endpoint_ready": true,
    "models": ["qwen3.5:4b"],
    "error": null
  },
  "agent": {
    "id": "default",
    "model": "qwen3.5:4b",
    "model_installed": true
  },
  "runtime": {
    "profile": "local-8gb",
    "model": "qwen3.5:4b",
    "summarize": {},
    "concurrency": {}
  },
  "tokenizers": {
    "ready": false,
    "cache_dir": ".run/tokenizers/hf-cache",
    "models": []
  },
  "runs": {
    "known_count": 3,
    "latest": []
  },
  "checks": [
    {
      "id": "ollama.executable",
      "status": "ok",
      "message": "Ollama executable found."
    }
  ],
  "recommendations": [
    {
      "id": "tokenizer.setup",
      "priority": "optional",
      "message": "Run tokenizer setup before enabling token-aware chunking.",
      "command": "python sift.py farm tokenizer setup"
    }
  ],
  "report_paths": {
    "markdown": ".run/reports/setup-doctor.md",
    "json": ".run/reports/setup-doctor.json"
  }
}
```

Exact field names can be refined during planning, but the report must keep a clear split between observed facts, checks, and recommendations.

### Status

The report-level `status` should be conservative:

- `ready`: core farm prerequisites look available
- `ready_with_warnings`: the farm can likely run, but optional or performance-related checks need attention
- `needs_setup`: required setup is missing, such as Python version too old or no Ollama executable
- `unknown`: checks could not run reliably

Doctor should not fail just because Ollama is not running. It should record the condition and recommend a next command.

### Recommendations

Recommendations should be concrete and low-risk. Examples:

- install Ollama if missing
- run `python sift.py setup`
- start Ollama / run `python sift.py start`
- pull or configure the default model
- run `python sift.py farm tokenizer setup` before token-aware chunking
- use `local-8gb` or `cpu-small` as conservative starting profiles
- run a tiny smoke farm job before increasing concurrency

Doctor may mention benchmark/profile and auto-config follow-ups, but must not implement them in this first slice.

## Acceptance Criteria

- `python sift.py farm doctor` runs without requiring Ollama to be installed or running.
- `python sift.py farm doctor` writes `.run/reports/setup-doctor.md` and `.run/reports/setup-doctor.json` by default.
- `python sift.py farm doctor` prints human-readable Markdown to stdout.
- `python sift.py farm doctor --json` prints valid JSON to stdout with no Markdown/prose.
- The JSON report includes schema version, generated timestamp, report status, environment, Ollama, agent, runtime, tokenizer, recent-run, check, recommendation, and report-path sections.
- The Markdown report includes the same major sections in a form a non-technical user can read with a primary AI.
- Missing Ollama executable is reported as setup-needed with an install/setup recommendation instead of crashing.
- Unreachable Ollama endpoint is reported with a start/setup recommendation instead of crashing.
- Installed model inspection is attempted only when the Ollama endpoint is reachable.
- Default/configured agent model installation status is reported as true, false, or unknown.
- Tokenizer readiness is reported without downloading tokenizer assets.
- Runtime config is resolved read-only and included in compact form.
- Recent known farm runs are summarized using existing run discovery.
- The command does not write config, install packages, pull models, start services, stop services, or call a model.
- Docs explain that doctor is safe/read-only and intended for primary-AI setup guidance.
- BL-0020 is marked planned/implemented as appropriate.
- Deferred related items remain backlogged.
- Model-free tests cover JSON shape, Markdown rendering, missing Ollama, unreachable Ollama, installed-model detection with fake responses, tokenizer readiness with fake status, CLI parsing, report writing, and no-mutation behavior.

## Test Plan

Automated:

- unit tests for report status calculation
- unit tests for recommendation generation
- unit tests for Markdown rendering
- unit tests for JSON shape
- unit tests for missing Ollama executable
- unit tests for unreachable Ollama endpoint
- unit tests for installed model detection with fake Ollama tags
- unit tests for tokenizer readiness with fake tokenizer status
- CLI parser tests for `farm doctor`, `farm doctor --json`, `--output`, `--agent`, and `--profile`
- report-writing tests under a temporary root
- full model-free test suite

Verification:

```powershell
python -m unittest tests.test_qwen_farm_doctor tests.test_qwen_cli
python -m unittest discover -s tests
git diff --check
```

Manual smoke:

```powershell
python sift.py farm doctor
python sift.py farm doctor --json
```

Inspect:

- `.run/reports/setup-doctor.md`
- `.run/reports/setup-doctor.json`

## Deferred To Roadmap

- BL-0021 benchmark-based profile recommendation.
- BL-0022 automatic config writing from doctor output.
- BL-0023 hardware-specific model installation guidance.
- BL-0028 safe concurrency recommendation for `parallel_jobs` and `OLLAMA_NUM_PARALLEL`.
- BL-0029 CLI helpers for starting Ollama with recommended concurrency environment variables.
- GPU/VRAM probing through platform-specific helpers.
- Top-level `python sift.py doctor` alias, if the command proves useful enough outside `farm`.
