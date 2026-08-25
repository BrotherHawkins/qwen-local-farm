from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src import qwen_farm_tokenizer


class FakeTokenizer:
    def encode(self, text: str, add_special_tokens: bool = False) -> list[str]:
        return text.split()


def fake_loader(*args: object, **kwargs: object) -> FakeTokenizer:
    return FakeTokenizer()


class FarmTokenizerTests(unittest.TestCase):
    def test_supported_qwen_model_aliases_map_to_tokenizers(self) -> None:
        self.assertEqual(qwen_farm_tokenizer.tokenizer_id_for_model("qwen3.5:4b"), "Qwen/Qwen3.5-4B")
        self.assertEqual(qwen_farm_tokenizer.tokenizer_id_for_model("qwen3:4b"), "Qwen/Qwen3-4B")
        self.assertEqual(qwen_farm_tokenizer.tokenizer_id_for_model("qwen3:8b"), "Qwen/Qwen3-8B")
        self.assertEqual(qwen_farm_tokenizer.tokenizer_id_for_model("qwen3:14b"), "Qwen/Qwen3-14B")

    def test_unknown_model_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(qwen_farm_tokenizer.TokenizerUnavailableError, "No exact tokenizer mapping"):
                qwen_farm_tokenizer.load_exact_token_counter(
                    root=Path(temp_dir),
                    model="other:1b",
                    tokenizer_loader=fake_loader,
                )

    def test_status_uses_fake_loader_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            status = qwen_farm_tokenizer.tokenizer_status(
                root=Path(temp_dir),
                models=["qwen3:4b"],
                download=True,
                tokenizer_loader=fake_loader,
            )

            self.assertTrue(status["ready"])
            self.assertFalse(status["counts_are_estimated"])
            self.assertEqual(status["models"][0]["model_metadata"]["family"], "qwen")
            self.assertEqual(status["models"][0]["model_metadata"]["tokenizer"]["strategy"], "huggingface")
            self.assertTrue(status["models"][0]["offline_verified"])
            self.assertGreater(status["models"][0]["tokens_for_probe"], 0)

    def test_explicit_model_metadata_can_provide_exact_tokenizer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            counter = qwen_farm_tokenizer.load_exact_token_counter(
                root=Path(temp_dir),
                model="llama3.1:8b",
                model_metadata={
                    "tokenizer": {
                        "strategy": "huggingface",
                        "id": "meta-llama/Llama-3.1-8B",
                        "exact": True,
                    }
                },
                tokenizer_loader=fake_loader,
            )

        self.assertEqual(counter.tokenizer_id, "meta-llama/Llama-3.1-8B")
        self.assertEqual(counter.count_tokens("hello world"), 2)

    def test_write_tokenizer_status_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status = qwen_farm_tokenizer.tokenizer_status(
                root=root,
                models=["qwen3:4b"],
                tokenizer_loader=fake_loader,
            )

            qwen_farm_tokenizer.write_tokenizer_status(root, status)

            json_path, md_path = qwen_farm_tokenizer.tokenizer_report_paths(root)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertIn("Tokenizer Status", md_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
