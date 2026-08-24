from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.qwen_farm_profiles import (
    PROFILE_NAMES,
    RuntimeOverrides,
    derive_token_budget,
    finalize_runtime_config_for_agent,
    resolve_runtime_config,
)


class FarmRuntimeProfileTests(unittest.TestCase):
    def test_default_resolution_uses_local_8gb(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(root=Path(temp_dir), default_model="qwen-test:1b")

            self.assertEqual(config["profile"], "local-8gb")
            self.assertEqual(config["resource_mode"], "auto")
            self.assertEqual(config["model"], "qwen-test:1b")
            self.assertEqual(config["summarize"]["chunk_strategy"], "character")
            self.assertEqual(config["summarize"]["chunk_chars"], 8000)
            self.assertEqual(config["summarize"]["token_safety_margin"], 0.10)
            self.assertTrue(config["summarize"]["preserve_heading_ancestry"])
            self.assertEqual(config["summarize"]["chunk_overlap_chars"], 0)
            self.assertEqual(config["summarize"]["chunk_overlap_tokens"], 0)
            self.assertEqual(config["summarize"]["snippet_policy"], "off")
            self.assertIsNone(config["summarize"]["snippet_count"])
            self.assertEqual(config["concurrency"]["jobs"], 1)
            self.assertEqual(
                config["failure_policy"],
                {
                    "max_attempts": 2,
                    "per_file_timeout_seconds": 600,
                    "chunk_max_attempts": 2,
                    "reduce_max_attempts": 2,
                },
            )

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
                    self.assertIn(config["resource_mode"], {"auto", "cpu"})
                    self.assertGreater(config["summarize"]["chunk_chars"], 0)

    def test_config_file_overrides_profile_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps(
                    {
                        "profile": "local-12gb",
                        "resource_mode": "cpu",
                        "model": "qwen-test:8b",
                        "summarize": {
                            "chunk_chars": 18000,
                            "preserve_heading_ancestry": False,
                            "chunk_overlap_chars": 250,
                        },
                        "concurrency": {"jobs": 2},
                        "failure_policy": {"max_attempts": 3, "per_file_timeout_seconds": 900},
                    }
                ),
                encoding="utf-8",
            )

            config = resolve_runtime_config(root=root, default_model="qwen-test:1b")

            self.assertEqual(config["profile"], "local-12gb")
            self.assertEqual(config["resource_mode"], "cpu")
            self.assertEqual(config["model"], "qwen-test:8b")
            self.assertEqual(config["summarize"]["chunk_chars"], 18000)
            self.assertEqual(config["summarize"]["reduce_chars"], 12000)
            self.assertFalse(config["summarize"]["preserve_heading_ancestry"])
            self.assertEqual(config["summarize"]["chunk_overlap_chars"], 250)
            self.assertEqual(config["summarize"]["chunk_overlap_tokens"], 0)
            self.assertEqual(config["concurrency"]["jobs"], 2)
            self.assertEqual(config["concurrency"]["chunks"], 1)
            self.assertEqual(config["failure_policy"]["max_attempts"], 3)
            self.assertEqual(config["failure_policy"]["per_file_timeout_seconds"], 900)
            self.assertEqual(config["failure_policy"]["chunk_max_attempts"], 2)
            self.assertEqual(
                config["provenance"]["config_fields"],
                [
                    "concurrency.jobs",
                    "failure_policy.max_attempts",
                    "failure_policy.per_file_timeout_seconds",
                    "model",
                    "profile",
                    "resource_mode",
                    "summarize.chunk_chars",
                    "summarize.chunk_overlap_chars",
                    "summarize.preserve_heading_ancestry",
                ],
            )

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
                    resource_mode="gpu",
                    model="qwen-test:14b",
                    chunk_chars=21000,
                    preserve_heading_ancestry=False,
                    chunk_overlap_chars=300,
                    chunk_overlap_tokens=25,
                    parallel_jobs=3,
                    max_attempts=4,
                    per_file_timeout_seconds=1200,
                    chunk_max_attempts=5,
                    reduce_max_attempts=1,
                ),
            )

            self.assertEqual(config["profile"], "local-24gb")
            self.assertEqual(config["resource_mode"], "gpu")
            self.assertEqual(config["model"], "qwen-test:14b")
            self.assertEqual(config["summarize"]["chunk_chars"], 21000)
            self.assertEqual(config["summarize"]["reduce_chars"], 20000)
            self.assertFalse(config["summarize"]["preserve_heading_ancestry"])
            self.assertEqual(config["summarize"]["chunk_overlap_chars"], 300)
            self.assertEqual(config["summarize"]["chunk_overlap_tokens"], 25)
            self.assertEqual(config["concurrency"]["jobs"], 3)
            self.assertEqual(config["failure_policy"]["max_attempts"], 4)
            self.assertEqual(config["failure_policy"]["per_file_timeout_seconds"], 1200)
            self.assertEqual(config["failure_policy"]["chunk_max_attempts"], 5)
            self.assertEqual(config["failure_policy"]["reduce_max_attempts"], 1)
            self.assertIn("model", config["provenance"]["cli_override_fields"])
            self.assertIn("resource_mode", config["provenance"]["cli_override_fields"])
            self.assertIn("summarize.chunk_overlap_chars", config["provenance"]["cli_override_fields"])
            self.assertIn("failure_policy.max_attempts", config["provenance"]["cli_override_fields"])

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

    def test_unknown_resource_mode_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(json.dumps({"resource_mode": "rocket"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "resource_mode"):
                resolve_runtime_config(root=root, default_model="qwen-test:1b")

    def test_cpu_mode_forces_num_gpu_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(
                root=Path(temp_dir),
                default_model="qwen-test:1b",
                overrides=RuntimeOverrides(resource_mode="cpu"),
            )
            agent = {"id": "default", "model": "qwen-test:1b", "options": {"num_gpu": 30}}

            finalized = finalize_runtime_config_for_agent(config, agent)

            self.assertEqual(finalized["resource_mode"]["requested"], "cpu")
            self.assertEqual(finalized["resource_mode"]["effective"], "cpu")
            self.assertEqual(agent["options"]["num_gpu"], 0)
            self.assertEqual(finalized["resource_mode"]["agent_option_override"]["before"], 30)

    def test_gpu_mode_rejects_cpu_forced_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(
                root=Path(temp_dir),
                default_model="qwen-test:1b",
                overrides=RuntimeOverrides(resource_mode="gpu"),
            )
            agent = {"id": "qwen8-cpu", "model": "qwen-test:8b", "options": {"num_gpu": 0}}

            with self.assertRaisesRegex(ValueError, "conflicts"):
                finalize_runtime_config_for_agent(config, agent)

    def test_hybrid_mode_rejects_cpu_forced_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(
                root=Path(temp_dir),
                default_model="qwen-test:1b",
                overrides=RuntimeOverrides(resource_mode="hybrid"),
            )
            agent = {"id": "qwen8-cpu", "model": "qwen-test:8b", "options": {"num_gpu": 0}}

            with self.assertRaisesRegex(ValueError, "conflicts"):
                finalize_runtime_config_for_agent(config, agent)

    def test_auto_cpu_small_resolves_to_cpu(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(
                root=Path(temp_dir),
                default_model="qwen-test:1b",
                overrides=RuntimeOverrides(profile="cpu-small"),
            )
            agent = {"id": "default", "model": "qwen-test:1b", "options": {}}

            finalized = finalize_runtime_config_for_agent(config, agent)

            self.assertEqual(finalized["resource_mode"]["requested"], "cpu")
            self.assertEqual(finalized["resource_mode"]["effective"], "cpu")
            self.assertEqual(agent["options"]["num_gpu"], 0)

    def test_auto_cpu_forced_agent_resolves_to_cpu(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(root=Path(temp_dir), default_model="qwen-test:1b")
            agent = {"id": "qwen8-cpu", "model": "qwen-test:8b", "options": {"num_gpu": 0}}

            finalized = finalize_runtime_config_for_agent(config, agent)

            self.assertEqual(finalized["resource_mode"]["requested"], "auto")
            self.assertEqual(finalized["resource_mode"]["effective"], "cpu")

    def test_auto_positive_num_gpu_resolves_to_hybrid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(root=Path(temp_dir), default_model="qwen-test:1b")
            agent = {"id": "qwen14-hybrid", "model": "qwen-test:14b", "options": {"num_gpu": 24}}

            finalized = finalize_runtime_config_for_agent(config, agent)

            self.assertEqual(finalized["resource_mode"]["requested"], "auto")
            self.assertEqual(finalized["resource_mode"]["effective"], "hybrid")

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

    def test_snippet_auto_config_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps(
                    {
                        "summarize": {
                            "snippet_policy": "auto",
                            "snippet_count": None,
                            "snippet_min_count": 2,
                            "snippet_max_count": 6,
                            "snippet_max_chars": 500,
                        }
                    }
                ),
                encoding="utf-8",
            )

            config = resolve_runtime_config(root=root, default_model="qwen-test:1b")

            self.assertEqual(config["summarize"]["snippet_policy"], "auto")
            self.assertIsNone(config["summarize"]["snippet_count"])
            self.assertEqual(config["summarize"]["snippet_max_count"], 6)
            self.assertEqual(config["summarize"]["snippet_max_chars"], 500)

    def test_snippets_override_can_disable_project_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps({"summarize": {"snippet_policy": "fixed", "snippet_count": 4}}),
                encoding="utf-8",
            )

            config = resolve_runtime_config(
                root=root,
                default_model="qwen-test:1b",
                overrides=RuntimeOverrides(snippets="off"),
            )

            self.assertEqual(config["summarize"]["snippet_policy"], "off")
            self.assertIsNone(config["summarize"]["snippet_count"])

    def test_snippets_override_accepts_fixed_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = resolve_runtime_config(
                root=Path(temp_dir),
                default_model="qwen-test:1b",
                overrides=RuntimeOverrides(snippets="3"),
            )

            self.assertEqual(config["summarize"]["snippet_policy"], "fixed")
            self.assertEqual(config["summarize"]["snippet_count"], 3)

    def test_invalid_snippet_policy_count_combination_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps({"summarize": {"snippet_policy": "auto", "snippet_count": 3}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "snippet_count"):
                resolve_runtime_config(root=root, default_model="qwen-test:1b")

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

    def test_invalid_heading_ancestry_config_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps({"summarize": {"preserve_heading_ancestry": "yes"}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "preserve_heading_ancestry"):
                resolve_runtime_config(root=root, default_model="qwen-test:1b")

    def test_invalid_chunk_overlap_config_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps({"summarize": {"chunk_overlap_chars": -1}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "chunk_overlap_chars"):
                resolve_runtime_config(root=root, default_model="qwen-test:1b")

    def test_cli_chunk_overlap_override_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "--chunk-overlap-tokens"):
                resolve_runtime_config(
                    root=Path(temp_dir),
                    default_model="qwen-test:1b",
                    overrides=RuntimeOverrides(chunk_overlap_tokens=-1),
                )

    def test_unknown_failure_policy_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps({"failure_policy": {"surprise": 1}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Unknown failure_policy field"):
                resolve_runtime_config(root=root, default_model="qwen-test:1b")

    def test_non_positive_failure_policy_value_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".qwen-farm.json").write_text(
                json.dumps({"failure_policy": {"chunk_max_attempts": 0}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "failure_policy.chunk_max_attempts"):
                resolve_runtime_config(root=root, default_model="qwen-test:1b")

    def test_cli_failure_policy_override_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "--reduce-max-attempts"):
                resolve_runtime_config(
                    root=Path(temp_dir),
                    default_model="qwen-test:1b",
                    overrides=RuntimeOverrides(reduce_max_attempts=0),
                )

    def test_derived_token_budget_is_capped_for_summary_quality(self) -> None:
        self.assertEqual(derive_token_budget(8192, 0.10), 4096)
        self.assertEqual(derive_token_budget(4096, 0.10), 2662)


if __name__ == "__main__":
    unittest.main()
