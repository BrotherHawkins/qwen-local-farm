# 0032 Implement AI Skills Library

Status: Implemented

Change Spec: [0032-add-ai-skills-library.md](../changes/0032-add-ai-skills-library.md)

## Goal

Add a portable repo-shipped AI skills library so Codex, Claude Code, or another skills-familiar AI assistant can guide users through Sift setup and operation using existing doctor, recommend, schema, smoke, and artifact-inspection rails.

## Implementation Steps

- [x] Add `skills/README.md` explaining the portable skill library and install/paste fallback.
- [x] Add `skills/index.json` as the repo-local manifest for shipped skills and required commands.
- [x] Add `skills/sift-setup/SKILL.md` for guided setup and first smoke tests.
- [x] Add `skills/sift-operator/SKILL.md` for running farm jobs and inspecting/package outputs.
- [x] Include stable required-command sections in each skill.
- [x] Add model-free skill sync tests covering manifest shape, skill frontmatter, stale names, approval boundaries, expected command/artifact coverage, manifest-vs-skill command sync, and parser-tested commands.
- [x] Link the skill library from README and AI usage docs.
- [x] Update spec/dashboard/backlog lifecycle state for the implementation PR.
- [x] Run focused skill tests, full tests, compile, spec guard, and whitespace checks.

## Test Plan

Run:

```powershell
python -m unittest tests.test_sift_skills tests.test_sift_cli
python -m unittest discover -s tests
python -m compileall sift.py examples src tests
python -m src.sift_spec_guard
git diff --check
```

Skill sync tests should remain model-free. They should not start Ollama, call local models, install packages, download tokenizers, write persistent user config, or require network access.

## Manual Verification

Use ignored artifacts only:

```text
.run/dogfood_0032/
```

Manual smoke should verify:

- `skills/README.md` explains installation and paste-as-instructions fallback.
- `skills/index.json` lists both shipped skills.
- Each `SKILL.md` is readable as plain Markdown.
- Required commands in each skill match the manifest.
- The setup skill gives a beginner-friendly flow through doctor, recommend, apply preview/write approval, tokenizer setup boundaries, and a tiny farm run.
- The operator skill gives a reproducible `.run/` workflow for farm runs, status/result inspection, package helpers, and dogfood records.

No real model run is required for this implementation because the behavior is a model-free skill/docs/test layer over already-smoked Sift commands.
