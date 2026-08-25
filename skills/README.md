# Sift Skills

Sift ships portable AI skill folders for assistants that can load repo-provided skills, such as Codex, Claude Code, or similar coding-agent environments.

These skills are plain Markdown instructions with small frontmatter blocks. They are not a universal installer and do not require a Sift-specific plugin.

## Included Skills

- `sift-setup`: guide a user through cloning, inspecting, configuring, and smoke-testing Sift.
- `sift-operator`: run Sift farm jobs, inspect outputs, package results, and record dogfood evidence.

## Suggested User Prompt

```text
Clone the Sift repo and install the skills found there, then walk me through getting set up.
```

## Installation

Install or register the folders under `skills/` according to the target AI app's skill mechanism.

If an AI app does not support skills directly, paste the relevant `SKILL.md` into the AI session as instructions:

- [sift-setup/SKILL.md](sift-setup/SKILL.md)
- [sift-operator/SKILL.md](sift-operator/SKILL.md)

The skills should guide the AI assistant to use Sift's existing safe rails:

- `python sift.py farm doctor`
- `python sift.py farm recommend`
- `python sift.py farm recommend apply`
- `python sift.py farm schema validate`
- tiny smoke runs under `.run/`

