# 0032 Add AI Skills Library

Status: Implemented
Type: Add

## WHY

Sift is increasingly designed for a user experience where a primary AI assistant helps a less technical user get local workers running. The CLI already has much of the necessary machinery: doctor reports, recommendations, safe config apply, schema validation, status artifacts, and smokeable farm runs.

What is missing is a small library of AI-app instructions that tells Codex, Claude Code, or another skills-familiar AI environment how to use those rails without requiring the human to understand the full CLI first.

The target user sentence should be enough:

```text
Clone the Sift repo and install the skills found there, then walk me through getting set up.
```

The product principle is: Sift should be easy to delegate to. A human should be able to ask an AI assistant to install the repo-provided skills, inspect the local machine, and guide setup using Sift's existing safe, inspectable commands.

The tradeoff is that the first skill library should be documentation-and-instruction driven, not a new plugin system, installer, GUI, or platform-specific package manager.

## Scope

Add a tracked top-level `skills/` folder containing a platform-agnostic AI skills library.

The first pass should include:

- `skills/README.md`
- `skills/index.json`
- at least one setup/onboarding skill
- at least one farm/operator skill, unless planning finds one combined skill is clearer
- `SKILL.md` files in each skill folder
- portable instructions that work in skills-familiar environments without depending on a Sift-specific plugin
- docs links from the main README or AI usage docs

The skill library should teach an AI assistant how to:

- confirm it is operating in a Sift repo clone
- inspect README/docs before taking setup actions
- run `python sift.py farm doctor`
- inspect doctor JSON/Markdown output
- run `python sift.py farm recommend`
- optionally preview and apply `.sift-farm.json` recommendations only when the user approves
- set up tokenizers only when useful
- run a tiny smoke test before a large farm run
- inspect `farm-status.json`, job `result.json`, timing summaries, and post-run packages
- explain local model, Ollama, tokenizer, GPU/CPU, and artifact paths in beginner-friendly terms

The skills should be model-free as repo artifacts. They may instruct an AI to run local Sift commands, but they must not include downloaded model outputs, local machine artifacts, secrets, API keys, or user-specific paths except as examples.

The skill library should be treated as first-class software documentation with sync checks. Skill files should have enough structured metadata and command markers for model-free tests to catch stale CLI names, stale config names, missing skill files, missing approval boundaries, and command references that no longer parse.

## Non-Goals

- No new Sift runtime behavior.
- No new CLI command for installing skills.
- No platform-specific plugin bundle.
- No automatic editing of a user's global AI-app configuration.
- No remote service, account integration, or marketplace publishing.
- No generated app UI.
- No claim that every AI coding environment supports the same skill format.

## Behavior

### Skill Folder Shape

Each skill should live in a folder under `skills/`.

Each skill folder should contain a `SKILL.md` file with:

- a short skill name
- a short description of when the skill should be used
- direct, ordered instructions for the AI assistant
- safe setup behavior
- verification steps
- clear stop/ask-for-approval points
- a required command-reference section for parser-testable Sift commands

The preferred portable shape is Markdown with minimal YAML frontmatter:

```markdown
---
name: sift-setup
description: Guide a user through cloning, inspecting, configuring, and smoke-testing Sift.
---

# Sift Setup

...
```

The frontmatter is intended to be friendly to skills-aware tools while keeping the file readable as ordinary Markdown.

Each skill should include a stable command section similar to:

```markdown
## Required Sift Commands

- `python sift.py --help`
- `python sift.py farm doctor --json`
- `python sift.py farm schema validate <path> --json`
```

Commands in this section should be concrete enough for tests to normalize placeholders such as `<path>` and parse them with Sift's CLI parser without executing model work.

### Skill Manifest

`skills/index.json` should list the shipped skills in a small stable shape:

```json
{
  "schema_version": 1,
  "skills": [
    {
      "id": "sift-setup",
      "path": "skills/sift-setup/SKILL.md",
      "description": "Guide a user through Sift setup and first smoke test.",
      "required_commands": [
        "python sift.py --help",
        "python sift.py farm doctor --json"
      ]
    }
  ]
}
```

The manifest is not a universal skill installer. It is a repo-local contract that lets tests, docs, and AI assistants discover the skill library without scraping the folder tree.

### Initial Skills

The first pass should add a setup skill similar to:

```text
skills/sift-setup/SKILL.md
```

This skill should be used when the user wants help installing, configuring, diagnosing, or first-running Sift.

The first pass should add an operator skill similar to:

```text
skills/sift-operator/SKILL.md
```

This skill should be used when the user has Sift available and wants to run farm jobs over local inputs, inspect outputs, package results, compare dogfood runs, or prepare synthesis-ready artifacts.

If implementation finds that two skills duplicate too much instruction, one combined skill is acceptable only if the resulting skill stays short and easy for an AI assistant to follow.

### Setup Flow

The setup skill should instruct the AI assistant to prefer this flow:

1. Confirm the repo clone and current working directory.
2. Read `README.md`, `docs/platforms.md`, and `docs/ai-usage.md` as needed.
3. Run `python sift.py --help`.
4. Run `python sift.py farm doctor --json`.
5. Summarize doctor status in plain language.
6. If Ollama or the default model is missing, explain the next command before running anything that installs or downloads.
7. Run `python sift.py farm recommend --json` only after the local service/model state is ready enough for a probe.
8. Preview config changes with `python sift.py farm recommend apply`.
9. Ask before using `--write`.
10. Run a tiny smoke folder through `python sift.py farm run`.
11. Validate key JSON artifacts with `python sift.py farm schema validate`.
12. End with the current run ID, status, output path, and the next useful action.

### Operator Flow

The operator skill should instruct the AI assistant to prefer reproducible folder-based work:

1. Put transient inputs and outputs under `.run/`.
2. Use include/exclude filters instead of manually moving lots of files when practical.
3. Run `farm doctor` or inspect recent recommendation/config state before large jobs.
4. Choose `summarize` as the default mature mode unless the user gives a custom prompt.
5. Use snippets or synthesis bundles when downstream frontier-model synthesis is likely.
6. Inspect `farm-status.json`, `FARM_STATUS.md`, job results, `timing-summary.json`, and package artifacts before summarizing outcomes.
7. Record dogfood quality or timing when the user is comparing changes across runs.

### Installation Guidance

`skills/README.md` should explain that Sift ships portable skill folders, not a universal installer.

It should tell users or AI assistants to install by copying or registering the folders under `skills/` according to the target AI app's skill mechanism.

It should include the intended user prompt:

```text
Clone the Sift repo and install the skills found there, then walk me through getting set up.
```

It should also explain that if an AI app does not support skills directly, the user can paste the relevant `SKILL.md` into that AI session as setup instructions.

### Safety And Boundaries

The skills should make these boundaries explicit:

- Do not commit, push, or open PRs while helping a user set up Sift unless explicitly asked.
- Do not put downloaded/test artifacts in tracked files.
- Prefer `.run/` for smoke inputs, reports, and local artifacts.
- Ask before installing packages, downloading models, writing `.sift-farm.json`, or changing long-lived environment settings.
- Preserve model-free CI assumptions.
- Treat Qwen as the tested default model family, while using Sift's model metadata for other local models.

### Skill Sync Tests

Add model-free tests, likely `tests/test_sift_skills.py`, that treat the skill library as a tested artifact.

The tests should verify:

- `skills/index.json` exists and is valid JSON.
- Every skill listed in `skills/index.json` exists.
- Every listed skill has a `SKILL.md`.
- Every `SKILL.md` has valid minimal frontmatter with `name` and `description`.
- Skill IDs, folder names, and frontmatter names stay aligned.
- Skill docs do not contain stale renamed project references such as `qwen.py`, `qwen.ps1`, `.qwen-farm.json`, `qwen_farm`, `qwen_gateway`, `QWEN_MODEL`, `QWEN_GATEWAY_HOST`, or `QWEN_FARM_HOME`.
- Skill docs may mention Qwen only when referring to the actual tested model family, model IDs, or tokenizer IDs.
- Setup skill text includes approval boundaries for installs, model downloads, config writes, and long-lived environment changes.
- Setup skill text references doctor, recommendation, recommendation apply preview/write, schema validation, and a tiny smoke test.
- Operator skill text references `.run/`, farm status artifacts, job results, timing summaries, schema validation, and post-run package helpers.
- Required command lists in the manifest and skill files stay in sync.
- Required commands use current `python sift.py ...` spelling.
- Required commands are parser-tested against `sift.parse_args()` after substituting safe placeholder values for tokens such as `<path>`, `<input-folder>`, `<run-ref>`, and `<agent-id>`.

The tests should not install packages, download tokenizers, pull models, start Ollama, call the local model, write persistent user config, or require network access.

## Acceptance Criteria

- A tracked `skills/` folder exists at the repo root.
- `skills/README.md` explains what the skill library is and how a skills-familiar AI app should install or use it.
- `skills/index.json` exists and lists the shipped skills.
- At least one `SKILL.md` exists under `skills/`.
- The initial skill coverage includes setup/onboarding behavior.
- The initial skill coverage includes farm/operator behavior, either as a separate skill or as a clearly distinct section in a combined skill.
- Skill files are platform-agnostic Markdown and do not require a Sift-specific plugin.
- Skill files include beginner-friendly setup guidance using existing Sift commands.
- Skill files tell the AI assistant to use `farm doctor`, `farm recommend`, recommendation apply preview/write, schema validation, and smoke tests appropriately.
- Skill files include explicit approval boundaries for installs/downloads/config writes.
- Skill files include stable required-command sections.
- Required-command sections and `skills/index.json` required command lists are kept in sync.
- Required commands in skills are parser-tested without executing model work.
- Main docs link to the skill library.
- Tests or checks verify that expected skill files exist and include required frontmatter/instruction markers.
- Tests or checks verify that skills do not contain stale renamed project references except legitimate Qwen model-family references.
- Tests or checks verify setup/operator skill coverage of key commands, artifacts, and approval boundaries.
- `python -m unittest discover -s tests` passes.
- `python -m src.sift_spec_guard` passes.

## Deferred To Roadmap

- Platform-specific skill installation helpers or commands.
- Skill package publishing for Codex, Claude Code, or other AI apps.
- A first-run interactive setup wizard.
- Generated documentation from skill metadata.
- A JSON Schema file for `skills/index.json`, unless implementation finds it is needed immediately.
- Additional specialized skills for dogfood benchmarking, model extension, article ingestion, or advanced troubleshooting.
