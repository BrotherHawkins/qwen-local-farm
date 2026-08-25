# 0035 Add Platform-Specific Skill Install Helpers

Status: Implemented
Type: Add

## WHY

Sift now ships portable AI skills, and the intended beginner experience is:

```text
Clone the Sift repo and install the skills found there, then walk me through getting set up.
```

The current `skills/README.md` explains the idea, but it still leaves too much platform-specific interpretation to the user or primary AI. Codex and Claude Code both support local skill folders, but they use different project/user locations and different invocation styles. A less technical user should not need to know those details.

BL-0107 should turn the repo-shipped skills into something easier to install safely: a primary AI can preview where skills would go, ask for approval, then perform a deterministic copy into the selected AI app's local skill folder.

## Scope

Add platform-specific skill installation helpers for the existing repo-shipped Sift skills.

The first pass should include:

- a `python sift.py skills install` command
- preview-by-default behavior
- explicit `--write` to copy skills
- platform targets for Codex and Claude Code project/user skill locations
- machine-readable JSON output for AI assistants and scripts
- a tracked JSON Schema for the helper report
- documentation for Codex and Claude Code skill installation paths
- updates to `skills/README.md`, README, and AI usage docs
- model-free tests that use temporary directories only
- sync tests that keep helper target docs aligned with official path assumptions and shipped skill metadata

The helper should install the existing `skills/sift-setup` and `skills/sift-operator` folders. It should not create new Sift skills.

## Non-Goals

This change does not add:

- plugin publishing or marketplace packaging
- automatic use of Codex `$skill-installer`
- automatic use of Claude Code plugin marketplaces
- automatic editing of `~/.codex/config.toml`, `.claude/settings.json`, or `.claude/settings.local.json`
- automatic disabling/enabling of skills in host app settings
- automatic install of Codex, Claude Code, Ollama, Python packages, tokenizers, or models
- a GUI or interactive setup wizard
- support for every AI app that may eventually understand the Agent Skills standard
- skill sync from remote marketplaces or account-level cloud settings

## Behavior

### CLI Shape

Add a top-level skills helper:

```powershell
python sift.py skills install --target codex-user
python sift.py skills install --target codex-project
python sift.py skills install --target claude-user
python sift.py skills install --target claude-project
```

Default behavior should be preview-only. It should print planned actions and write nothing.

To actually copy files:

```powershell
python sift.py skills install --target codex-user --write
```

To emit machine-readable output:

```powershell
python sift.py skills install --target claude-project --json
```

Optional flags:

- `--output <path>`: write the JSON report to a file.
- `--repo-root <path>`: override source repo root for tests and advanced scripts.
- `--home <path>`: override home directory resolution for tests and dry-run examples.
- `--replace`: allow replacing an existing installed Sift skill when the source differs.

### Targets

Supported first-pass targets:

| Target | Destination |
| --- | --- |
| `codex-user` | `<home>/.agents/skills/<skill-id>/SKILL.md` |
| `codex-project` | `<repo-root>/.agents/skills/<skill-id>/SKILL.md` |
| `claude-user` | `<home>/.claude/skills/<skill-id>/SKILL.md` |
| `claude-project` | `<repo-root>/.claude/skills/<skill-id>/SKILL.md` |

The helper should copy whole skill directories, not only `SKILL.md`, so future supporting files remain installable without redesigning the command.

### Safety

The command must be safe by default:

- preview-only unless `--write` is supplied
- never writes outside the resolved target root
- never deletes target files
- never overwrites differing existing skill files unless `--replace` is supplied
- reports conflicts with enough detail for a primary AI to explain them
- creates destination directories only during `--write`
- writes only skill folders listed in `skills/index.json`
- does not install packages, call models, start services, or require network access

If a target skill exists with identical files, report `up_to_date`.

If a target skill exists and differs, report `conflict` and skip it unless `--replace` is supplied.

If `--replace` is supplied with `--write`, replace only the selected Sift skill directory. The helper should still verify that the resolved destination remains inside the selected target root before writing.

### JSON Report

The helper should return a stable report shape:

```json
{
  "schema_version": 1,
  "command": "skills install",
  "target": "codex-user",
  "dry_run": true,
  "write": false,
  "replace": false,
  "source_root": "C:/Github/GHE/sift/skills",
  "destination_root": "C:/Users/name/.agents/skills",
  "skills": [
    {
      "id": "sift-setup",
      "source": "skills/sift-setup",
      "destination": "C:/Users/name/.agents/skills/sift-setup",
      "action": "copy",
      "status": "planned",
      "reason": "missing"
    }
  ],
  "summary": {
    "planned": 2,
    "copied": 0,
    "up_to_date": 0,
    "conflicts": 0,
    "skipped": 0,
    "errors": 0
  },
  "warnings": [],
  "next_steps": [
    "Restart Codex if the installed skills do not appear."
  ]
}
```

Allowed per-skill `action` values:

- `copy`
- `replace`
- `skip`

Allowed per-skill `status` values:

- `planned`
- `copied`
- `up_to_date`
- `conflict`
- `skipped`
- `error`

The schema should live under:

```text
schemas/skill-install-report.schema.json
```

and be registered in `schemas/index.json`.

### Human Output

Non-JSON output should be short and copyable:

```text
Skill install preview: codex-user
Destination: C:\Users\name\.agents\skills

- sift-setup: copy planned
- sift-operator: up to date

No files written. Re-run with --write to apply.
```

When `--write` succeeds, it should clearly state which skills were copied and where they landed.

### Documentation

Add or update docs so a primary AI can guide a user without guessing:

- `skills/README.md`: add platform-specific quickstart commands.
- README: point to the skill install helper near the skills section.
- `docs/ai-usage.md`: tell AI assistants to preview first, ask before `--write`, then run `farm doctor`.
- Optional dedicated doc, likely `docs/skill-installation.md`, if the README would otherwise get crowded.

Docs should explain:

- Codex repo/user targets use `.agents/skills`.
- Claude Code repo/user targets use `.claude/skills`.
- Project installs may dirty a working tree if the generated platform folder is not ignored.
- User installs affect future sessions across projects.
- If the host app does not pick up newly copied skills, restart or reload according to the host app's behavior.

### Tests

Model-free tests should cover:

- CLI parser accepts all skill install flags.
- Preview mode writes no files.
- `--write` copies both shipped skill folders to a temp target.
- Existing identical install reports `up_to_date`.
- Existing differing install reports `conflict` and does not overwrite by default.
- `--replace --write` replaces only selected Sift skill folders.
- Path safety prevents writes outside the selected target root.
- JSON report validates against `schemas/skill-install-report.schema.json`.
- Human output includes destination, per-skill action/status, and write/no-write state.
- Docs mention Codex and Claude Code targets.
- Skill install target metadata remains in sync with `skills/index.json`.

## Acceptance Criteria

- `python sift.py skills install --target codex-user` previews installing Sift skills into the Codex user skill folder.
- `python sift.py skills install --target codex-project` previews installing Sift skills into the Codex project skill folder.
- `python sift.py skills install --target claude-user` previews installing Sift skills into the Claude Code user skill folder.
- `python sift.py skills install --target claude-project` previews installing Sift skills into the Claude Code project skill folder.
- Preview mode does not create, modify, or delete files.
- `--write` copies every skill listed in `skills/index.json` into the selected target.
- The helper copies whole skill directories.
- The helper does not overwrite differing existing files unless `--replace` is supplied.
- The helper reports identical existing skills as `up_to_date`.
- JSON output is available with `--json`.
- JSON report files can be written with `--output`.
- A tracked JSON Schema validates generated reports.
- `schemas/index.json` includes the new schema.
- README, AI usage docs, and skills README explain the helper and approval boundary.
- Tests stay model-free and avoid writing to the real user home directory.
- `python -m unittest discover -s tests` passes.
- `python -m src.sift_spec_guard` passes.

## Test Plan

Automated:

```powershell
python -m unittest tests.test_sift_cli tests.test_sift_skills tests.test_sift_farm_schema
python -m unittest discover -s tests
python -m compileall sift.py examples src tests
python -m src.sift_spec_guard
git diff --check
```

Runtime-style local smoke using temporary folders under `.run/`:

```powershell
python sift.py skills install --target codex-user --home .run/dogfood_0035/home --json --output .run/dogfood_0035/codex-preview.json
python sift.py skills install --target codex-user --home .run/dogfood_0035/home --write --json --output .run/dogfood_0035/codex-write.json
python sift.py skills install --target claude-project --repo-root .run/dogfood_0035/project --write --json --output .run/dogfood_0035/claude-project-write.json
python sift.py farm schema validate .run/dogfood_0035/codex-write.json --json
python sift.py farm schema validate .run/dogfood_0035/claude-project-write.json --json
```

Inspect:

- copied `SKILL.md` files exist in the expected temp target folders
- preview report did not create target files
- schema validation passes
- human output is understandable enough for a primary AI to relay

## Deferred To Roadmap

- Published AI skill packages remain BL-0108.
- First-run interactive setup wizard remains BL-0109.
- Generated skill metadata documentation remains BL-0110.
- Specialized Sift skills remain BL-0111.
- Broader skill manifest JSON Schema remains BL-0112 unless needed by implementation.
- Automatic Ollama/model installation helpers remain BL-0113.
