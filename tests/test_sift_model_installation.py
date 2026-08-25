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
from src import sift_farm_schema
from src.sift_farm_profiles import PROFILE_NAMES, RESOURCE_MODES
from src.sift_model_installation import CATALOG_PATH, GUIDE_PATH, SCHEMA_PATH, load_guidance_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / CATALOG_PATH
GUIDE = ROOT / GUIDE_PATH
SCHEMA = ROOT / SCHEMA_PATH

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


def load_agent(agent_id: str) -> dict:
    path = ROOT / "agents" / f"{agent_id}.json"
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    return data


def sift_commands_from_catalog(catalog: dict) -> list[str]:
    commands: list[str] = []
    for band in catalog["hardware_bands"]:
        commands.extend(str(command) for command in band["setup_commands"])
        commands.extend(str(command) for command in band["smoke_test_commands"])
    return [command for command in commands if command.startswith("python sift.py ")]


def parser_args_for_command(command: str) -> list[str]:
    parts = shlex.split(command)
    if len(parts) < 2 or parts[:2] != ["python", "sift.py"]:
        raise AssertionError(f"Command must start with `python sift.py`: {command}")
    return ["sift.py", *parts[2:]]


class ModelInstallationGuidanceTests(unittest.TestCase):
    def test_catalog_validates_against_schema(self) -> None:
        result = sift_farm_schema.validate_artifact(ROOT, CATALOG)

        self.assertTrue(result["valid"], "\n".join(result["errors"]))
        self.assertEqual(result["schema"]["path"], SCHEMA_PATH)
        self.assertTrue(result["schema"]["detected"])

    def test_schema_index_lists_model_installation_schema(self) -> None:
        index = sift_farm_schema.load_json_object(ROOT / "schemas" / "index.json")

        paths = [record["path"] for record in index["schemas"]]
        self.assertIn(SCHEMA_PATH, paths)

    def test_catalog_agents_profiles_models_and_resource_modes_stay_in_sync(self) -> None:
        catalog = load_guidance_catalog(ROOT)
        agent_ids = {path.stem for path in (ROOT / "agents").glob("*.json")}
        band_ids = {band["id"] for band in catalog["hardware_bands"]}

        self.assertIn(catalog["default_band"], band_ids)
        for band in catalog["hardware_bands"]:
            with self.subTest(band=band["id"]):
                self.assertIn(band["recommended_profile"], PROFILE_NAMES)
                self.assertIn(band["recommended_agent"], agent_ids)
                self.assertIn(band["resource_mode"], RESOURCE_MODES)
                agent = load_agent(band["recommended_agent"])
                self.assertEqual(band["recommended_model"], agent["model"])
                self.assertGreaterEqual(len(band["install_commands"]), 1)
                for install in band["install_commands"]:
                    self.assertTrue(install["approval_required"])
                    self.assertTrue(str(install["command"]).startswith("ollama pull "))

    def test_catalog_sift_commands_parse_with_current_cli(self) -> None:
        catalog = load_guidance_catalog(ROOT)

        for command in sift_commands_from_catalog(catalog):
            with self.subTest(command=command):
                argv = parser_args_for_command(command)
                with patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                    args = sift.parse_args()
                self.assertIsNotNone(args.command)

    def test_docs_and_skills_link_to_model_installation_guidance(self) -> None:
        paths = [
            ROOT / "README.md",
            ROOT / "docs" / "platforms.md",
            ROOT / "docs" / "ai-usage.md",
            ROOT / "skills" / "sift-setup" / "SKILL.md",
            ROOT / "skills" / "sift-operator" / "SKILL.md",
        ]

        for path in paths:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("model-installation.md", text)

    def test_guidance_docs_do_not_contain_stale_renamed_references(self) -> None:
        texts = [
            GUIDE.read_text(encoding="utf-8"),
            CATALOG.read_text(encoding="utf-8"),
        ]

        for text in texts:
            for stale in STALE_REFERENCES:
                with self.subTest(stale=stale):
                    self.assertNotIn(stale, text)

    def test_guide_mentions_approval_required_actions(self) -> None:
        guide = GUIDE.read_text(encoding="utf-8")

        for phrase in [
            "Ask before downloading",
            "Only write config after review and approval",
            "download model weights",
            "farm recommend apply --write",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)


if __name__ == "__main__":
    unittest.main()
