from __future__ import annotations

import unittest

from src import sift_farm_model_metadata


class ModelMetadataTests(unittest.TestCase):
    def test_resolves_qwen_metadata_from_bundled_shape(self) -> None:
        metadata = sift_farm_model_metadata.resolve_model_metadata(
            {
                "model": "qwen3.5:4b",
                "model_family": "qwen",
                "backend": "ollama",
                "support": "tested",
                "tokenizer": {
                    "strategy": "huggingface",
                    "id": "Qwen/Qwen3.5-4B",
                    "exact": True,
                },
                "options": {"num_ctx": 8192},
            }
        )

        self.assertEqual(metadata["family"], "qwen")
        self.assertEqual(metadata["backend"], "ollama")
        self.assertEqual(metadata["support"], "tested")
        self.assertEqual(metadata["tokenizer"]["id"], "Qwen/Qwen3.5-4B")
        self.assertTrue(metadata["tokenizer"]["exact"])
        self.assertEqual(metadata["context"], {"tokens": 8192, "source": "agent.options.num_ctx"})

    def test_unknown_model_gets_unknown_family_fallback(self) -> None:
        metadata = sift_farm_model_metadata.resolve_model_metadata(
            {
                "model": "local-custom:1b",
                "options": {},
            }
        )

        self.assertEqual(metadata["family"], "unknown")
        self.assertEqual(metadata["support"], "unknown")
        self.assertEqual(metadata["tokenizer"]["strategy"], "unknown")
        self.assertFalse(metadata["tokenizer"]["exact"])

    def test_experimental_non_qwen_agent_metadata(self) -> None:
        metadata = sift_farm_model_metadata.resolve_model_metadata(
            {
                "model": "llama3.1:8b",
                "model_family": "llama",
                "backend": "ollama",
                "support": "experimental",
                "tokenizer": {"strategy": "none"},
                "options": {"num_ctx": 4096},
            }
        )

        self.assertEqual(metadata["family"], "llama")
        self.assertEqual(metadata["support"], "experimental")
        self.assertEqual(metadata["tokenizer"]["strategy"], "none")
        self.assertEqual(metadata["context"]["tokens"], 4096)

    def test_invalid_metadata_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "model_family must be one of"):
            sift_farm_model_metadata.resolve_model_metadata(
                {
                    "model": "qwen3.5:4b",
                    "model_family": "surprise",
                    "options": {},
                }
            )

    def test_huggingface_tokenizer_requires_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "tokenizer.id is required"):
            sift_farm_model_metadata.resolve_model_metadata(
                {
                    "model": "llama3.1:8b",
                    "model_family": "llama",
                    "tokenizer": {"strategy": "huggingface"},
                    "options": {},
                }
            )

    def test_exact_tokenizer_id_respects_explicit_none_strategy(self) -> None:
        self.assertIsNone(
            sift_farm_model_metadata.exact_tokenizer_id(
                "qwen3.5:4b",
                {
                    "tokenizer": {
                        "strategy": "none",
                        "id": None,
                        "exact": False,
                    }
                },
            )
        )


if __name__ == "__main__":
    unittest.main()
