# 0015 Implement Farm Doctor

Status: Implemented
Spec: [0015 Add Farm Doctor](../changes/0015-add-farm-doctor.md)

## Plan

Implement `farm doctor` as a read-only setup/capability report:

1. Add `src/qwen_farm_doctor.py`.
   - build a JSON report with environment, Ollama, agent, runtime, tokenizers, recent runs, checks, recommendations, and report paths
   - render a Markdown report from the same data
   - write `.run/reports/setup-doctor.json` and `.run/reports/setup-doctor.md`
   - keep probes injectable for model-free tests
2. Reuse existing helpers where practical.
   - `qwen.find_ollama` / `qwen.request_json` style probes passed in from CLI
   - `qwen_farm.load_agent`
   - `qwen_farm.resolve_run_agent_and_config`
   - `qwen_farm.load_runs`
   - `qwen_farm_tokenizer.tokenizer_status` without download
3. Add CLI support.
   - `python sift.py farm doctor`
   - `python sift.py farm doctor --json`
   - `--output`
   - `--agent`
   - `--profile`
   - Markdown stdout by default, JSON stdout with `--json`
4. Keep the command read-only.
   - no model pulls
   - no tokenizer downloads
   - no config writes
   - no service starts/stops
   - no model calls
5. Update docs and lifecycle records.
   - README quick command
   - AI usage setup guidance
   - roadmap command sketch from `python sift.py doctor` to `python sift.py farm doctor`
   - 0015 spec and plan status to implemented in the implementation PR
   - BL-0020 implemented while keeping BL-0021, BL-0022, BL-0023, BL-0028, and BL-0029 open
6. Add model-free tests.
   - JSON shape and report status calculation
   - Markdown rendering
   - missing Ollama executable
   - unreachable Ollama endpoint
   - installed model detection with fake tags
   - tokenizer readiness with fake status
   - report writing under a temporary root
   - CLI parsing and handler output

## Report Status Rules

Use conservative status calculation:

- `needs_setup` if Python is too old, Ollama executable is missing, or runtime config/agent loading fails.
- `ready_with_warnings` if core setup is present but Ollama is not reachable, default model installation is unknown/missing, tokenizer setup is incomplete, or conservative performance guidance applies.
- `ready` if core setup is present, Ollama is reachable, the selected model is installed, and no warnings are present.
- `unknown` only when a probe fails in a way the command cannot classify.

## Non-Goals

This implementation will not add benchmark-based profile recommendations, automatic config writing, hardware-specific model install selection, GPU/VRAM probing, Ollama service management, tokenizer downloads, model pulls, or top-level `python sift.py doctor`.

## Verification

Implemented with:

- `src/qwen_farm_doctor.py`
- `python sift.py farm doctor`
- `python sift.py farm doctor --json`
- report writing under `.run/reports/`
- read-only checks for environment, Ollama, selected agent/model, runtime config, tokenizer readiness, and recent runs
- README, AI usage, and roadmap docs
- model-free unit and CLI tests

Checks:

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

```text
.run/reports/setup-doctor.md
.run/reports/setup-doctor.json
```
