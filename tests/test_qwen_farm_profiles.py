from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.qwen_farm_profiles import (
    PROFILE_NAMES,
    RuntimeOverrides,
    derive_token_budget,
    resolve_runtime_config,
)


class FarmRuntimeProfileTests(unittest.TestCase):
    def test_default_resolution_uses_local_8gb(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(root=Path(temp_dir), default_model="qwen-test:1b")

            self.assertEqual(config["profile"], "local-8gb")
            self.assertEqual(config["model"], "qwen-test:1b")
            self.assertEqual(config["summarize"]["chunk_strategy"], "character")
            self.assertEqual(config["summarize"]["chunk_chars"], 8000)
            self.assertEqual(config["summarize"]["token_safety_margin"], 0.10)
            self.assertEqual(config["concurrency"]["jobs"], 1)

    def test_all_built_in_profiles_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            for profile in PROFILE_NAMES:
                with self.subTest(profile=profile):
                    config = resolve_runtime_config(
                        root=root,
                        default_model="qwen-test:1b",
                        overrides=RuntimeOverrides(profile=profile),
                    )
                    self.assertEqual(config["profile"], profile)
                    self.assertGreater(config["summarize"]["chunk_chars"], 0)

    def test_config_file_overrides_profile_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps(
                    {
                        "profile": "local-12gb",
                        "model": "qwen-test:8b",
                        "summarize": {"chunk_chars": 18000},
                        "concurrency": {"jobs": 2},
                    }
                ),
                encoding="utf-8",
            )

            config = resolve_runtime_config(root=root, default_model="qwen-test:1b")

            self.assertEqual(config["profile"], "local-12gb")
            self.assertEqual(config["model"], "qwen-test:8b")
            self.assertEqual(config["summarize"]["chunk_chars"], 18000)
            self.assertEqual(config["summarize"]["reduce_chars"], 12000)
            self.assertEqual(config["concurrency"]["jobs"], 2)
            self.assertEqual(config["concurrency"]["chunks"], 1)
            self.assertEqual(config["provenance"]["config_fields"], ["concurrency.jobs", "model", "profile", "summarize.chunk_chars"])

    def test_cli_overrides_beat_config_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "farm.json"
            config_path.write_text(
                json.dumps(
                    {
                        "profile": "local-4gb",
                        "model": "qwen-test:4b",
                        "summarize": {"chunk_chars": 6000},
                    }
                ),
                encoding="utf-8",
            )

            config = resolve_runtime_config(
                root=root,
                default_model="qwen-test:1b",
                config_path=config_path,
                overrides=RuntimeOverrides(
                    profile="local-24gb",
                    model="qwen-test:14b",
                    chunk_chars=21000,
                    parallel_jobs=3,
                ),
            )

            self.assertEqual(config["profile"], "local-24gb")
            self.assertEqual(config["model"], "qwen-test:14b")
            self.assertEqual(config["summarize"]["chunk_chars"], 21000)
            self.assertEqual(config["summarize"]["reduce_chars"], 20000)
            self.assertEqual(config["concurrency"]["jobs"], 3)
            self.assertIn("model", config["provenance"]["cli_override_fields"])

    def test_invalid_json_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "broken.json"
            config_path.write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid farm config JSON"):
                resolve_runtime_config(root=root, default_model="qwen-test:1b", config_path=config_path)

    def test_unknown_fields_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(json.dumps({"surprise": True}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unknown config field"):
                resolve_runtime_config(root=root, default_model="qwen-test:1b")

    def test_unknown_profile_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "Unknown farm profile"):
                resolve_runtime_config(
                    root=Path(temp_dir),
                    default_model="qwen-test:1b",
                    overrides=RuntimeOverrides(profile="giant-cloud"),
                )

    def test_token_strategy_config_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps(
                    {
                        "summarize": {
                            "chunk_strategy": "token",
                            "chunk_tokens": 6500,
                            "reduce_tokens": 6400,
                            "token_safety_margin": 0.2,
                        }
                    }
                ),
                encoding="utf-8",
            )

            config = resolve_runtime_config(root=root, default_model="qwen-test:1b")

            self.assertEqual(config["summarize"]["chunk_strategy"], "token")
            self.assertEqual(config["summarize"]["chunk_tokens"], 6500)
            self.assertEqual(config["summarize"]["reduce_tokens"], 6400)
            self.assertEqual(config["summarize"]["token_safety_margin"], 0.2)

    def test_cli_token_overrides_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(
                root=Path(temp_dir),
                default_model="qwen-test:1b",
                overrides=RuntimeOverrides(
                    chunk_strategy="token",
                    chunk_tokens=4000,
                    reduce_tokens=3500,
                    token_safety_margin=0.15,
                ),
            )

            self.assertEqual(config["summarize"]["chunk_strategy"], "token")
            self.assertEqual(config["summarize"]["chunk_tokens"], 4000)
            self.assertEqual(config["summarize"]["reduce_tokens"], 3500)
            self.assertEqual(config["summarize"]["token_safety_margin"], 0.15)

    def test_invalid_chunk_strategy_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps({"summarize": {"chunk_strategy": "semantic-ish"}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "chunk_strategy"):
                resolve_runtime_config(root=root, default_model="qwen-test:1b")

    def test_invalid_token_budget_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "--chunk-tokens"):
                resolve_runtime_config(
                    root=Path(temp_dir),
                    default_model="qwen-test:1b",
                    overrides=RuntimeOverrides(chunk_tokens=0),
                )

    def test_derived_token_budget_is_capped_for_summary_quality(self) -> None:
        self.assertEqual(derive_token_budget(8192, 0.10), 4096)
        self.assertEqual(derive_token_budget(4096, 0.10), 2662)


if __name__ == "__main__":
    unittest.main()
