from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import shlex
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import sift


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
MANIFEST = SKILLS / "index.json"

STALE_REFERENCES = [
    "qwen.py",
    "qwen.ps1",
    ".qwen-farm.json",
    "qwen_farm",
    "qwen_gateway",
    "QWEN_MODEL",
    "QWEN_GATEWAY_HOST",
    "QWEN_FARM_HOME",
]

PLACEHOLDER_VALUES = {
    "<path>": ".run/example.json",
    "<input-folder>": ".run/input",
    "<output-folder>": ".run/output",
    "<run-ref>": "farm-run-2026-08-24-221116-0a70",
    "<agent-id>": "default",
    "<label>": "smoke",
    "<instructions>": "summarize",
}


def read_manifest() -> dict:
    with MANIFEST.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    return data


def read_skill(skill: dict) -> str:
    path = ROOT / str(skill["path"])
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AssertionError("Skill file must start with frontmatter.")
    try:
        end = lines[1:].index("---") + 1
    except ValueError as exc:
        raise AssertionError("Skill frontmatter must end with `---`.") from exc
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise AssertionError(f"Invalid frontmatter line: {line}")
        fields[key.strip()] = value.strip()
    return fields


def required_commands_from_skill(text: str) -> list[str]:
    lines = text.splitlines()
    try:
        start = lines.index("## Required Sift Commands") + 1
    except ValueError as exc:
        raise AssertionError("Skill must include `## Required Sift Commands`.") from exc

    commands: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- `") and stripped.endswith("`"):
            commands.append(stripped[3:-1])
    return commands


def parser_args_for_command(command: str) -> list[str]:
    normalized = command
    for placeholder, value in PLACEHOLDER_VALUES.items():
        normalized = normalized.replace(placeholder, value)
    parts = shlex.split(normalized)
    if len(parts) < 2 or parts[:2] != ["python", "sift.py"]:
        raise AssertionError(f"Command must start with `python sift.py`: {command}")
    return ["sift.py", *parts[2:]]


class SkillManifestTests(unittest.TestCase):
    def test_manifest_lists_expected_skills(self) -> None:
        manifest = read_manifest()

        self.assertEqual(manifest["schema_version"], 1)
        skills = manifest["skills"]
        self.assertIsInstance(skills, list)
        self.assertEqual({skill["id"] for skill in skills}, {"sift-setup", "sift-operator"})

    def test_manifest_paths_exist_and_align_with_frontmatter(self) -> None:
        for skill in read_manifest()["skills"]:
            with self.subTest(skill=skill["id"]):
                path = ROOT / skill["path"]
                self.assertTrue(path.exists(), skill["path"])
                self.assertEqual(path.parent.name, skill["id"])
                self.assertEqual(path.name, "SKILL.md")

                fields = parse_frontmatter(path.read_text(encoding="utf-8"))
                self.assertEqual(fields.get("name"), skill["id"])
                self.assertEqual(fields.get("description"), skill["description"])

    def test_manifest_required_commands_match_skill_sections(self) -> None:
        for skill in read_manifest()["skills"]:
            with self.subTest(skill=skill["id"]):
                skill_commands = required_commands_from_skill(read_skill(skill))
                self.assertEqual(skill_commands, skill["required_commands"])

    def test_required_commands_parse_with_current_cli(self) -> None:
        for skill in read_manifest()["skills"]:
            for command in skill["required_commands"]:
                with self.subTest(skill=skill["id"], command=command):
                    argv = parser_args_for_command(command)
                    with patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                        if "--help" in argv:
                            with self.assertRaises(SystemExit) as raised:
                                sift.parse_args()
                            self.assertEqual(raised.exception.code, 0)
                        else:
                            args = sift.parse_args()
                            self.assertIsNotNone(args.command)


class SkillContentTests(unittest.TestCase):
    def test_skill_docs_do_not_contain_stale_renamed_references(self) -> None:
        for skill in read_manifest()["skills"]:
            text = read_skill(skill)
            for stale in STALE_REFERENCES:
                with self.subTest(skill=skill["id"], stale=stale):
                    self.assertNotIn(stale, text)

    def test_setup_skill_contains_expected_rails_and_approval_boundaries(self) -> None:
        setup = (SKILLS / "sift-setup" / "SKILL.md").read_text(encoding="utf-8")

        required_phrases = [
            "python sift.py farm doctor --json",
            "python sift.py farm recommend --json",
            "python sift.py farm recommend apply --json",
            "python sift.py farm recommend apply --write --json",
            "python sift.py farm schema validate <path> --json",
            "tiny smoke-test",
            ".run/",
            "Ask before installing packages",
            "Ask before downloading models or tokenizer assets",
            "Ask before writing `.sift-farm.json`",
            "Ask before changing long-lived environment variables",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, setup)

    def test_operator_skill_contains_expected_artifacts_and_helpers(self) -> None:
        operator = (SKILLS / "sift-operator" / "SKILL.md").read_text(encoding="utf-8")

        required_phrases = [
            ".run/",
            "farm-status.json",
            "FARM_STATUS.md",
            "jobs/job-*/result.json",
            "jobs/job-*/result.md",
            "timing-summary.json",
            "python sift.py farm collect",
            "python sift.py farm snippets pack",
            "python sift.py farm synthesis bundle",
            "python sift.py farm dogfood record",
            "python sift.py farm dogfood timing record",
            "python sift.py farm schema validate <path> --json",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, operator)

    def test_skills_readme_explains_install_and_paste_fallback(self) -> None:
        readme = (SKILLS / "README.md").read_text(encoding="utf-8")

        required_phrases = [
            "Clone the Sift repo and install the skills found there",
            "according to the target AI app's skill mechanism",
            "paste the relevant `SKILL.md`",
            "sift-setup",
            "sift-operator",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme)


if __name__ == "__main__":
    unittest.main()
