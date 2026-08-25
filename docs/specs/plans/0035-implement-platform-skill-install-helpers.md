# 0035 Implement Platform-Specific Skill Install Helpers

Spec: [0035-add-platform-specific-skill-install-helpers.md](../changes/0035-add-platform-specific-skill-install-helpers.md)

## Outcome

Add a safe preview-first `skills install` helper so primary AI assistants can install repo-shipped Sift skills into Codex or Claude Code local skill folders after explicit user approval.

## Checklist

- [x] Add a reusable skill install helper module.
- [x] Add `python sift.py skills install` CLI parsing and execution.
- [x] Support Codex user/project and Claude Code user/project targets.
- [x] Keep preview mode write-free and require `--write` to copy files.
- [x] Detect `up_to_date`, `conflict`, `planned`, and copied states.
- [x] Add JSON report schema and schema auto-detection.
- [x] Update README, AI usage docs, and skills README.
- [x] Add model-free CLI, helper, schema, and docs tests.
- [x] Run runtime smoke under `.run/dogfood_0035/`.
- [x] Update spec dashboard and backlog lifecycle bookkeeping.

## Verification

Run:

```bash
python -m unittest tests.test_sift_cli tests.test_sift_skills tests.test_sift_farm_schema
python -m unittest discover -s tests
python -m compileall sift.py examples src tests
python -m src.sift_spec_guard
git diff --check
```

Runtime-style smoke:

```bash
python sift.py skills install --target codex-user --home .run/dogfood_0035/home --json --output .run/dogfood_0035/codex-preview.json
python sift.py skills install --target codex-user --home .run/dogfood_0035/home --write --json --output .run/dogfood_0035/codex-write.json
python sift.py skills install --target claude-project --repo-root .run/dogfood_0035/project --write --json --output .run/dogfood_0035/claude-project-write.json
python sift.py farm schema validate .run/dogfood_0035/codex-write.json --json
python sift.py farm schema validate .run/dogfood_0035/claude-project-write.json --json
```

No model calls, model pulls, package installs, tokenizer downloads, or network access are required.
