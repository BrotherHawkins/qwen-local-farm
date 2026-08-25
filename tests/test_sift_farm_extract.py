from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src import sift_farm
from src.sift_farm_extract import dedupe_items, parse_tagged_extract
from src.sift_farm_model import FarmModelResult


def extract_processor(**kwargs: object) -> FarmModelResult:
    file_path = str(kwargs["file_path"])
    content = str(kwargs["content"])
    preset = str(kwargs.get("extract_preset") or "research")
    focus = kwargs.get("extract_focus")
    source_text = str(kwargs.get("extract_source_text") or content)
    source_offset = int(kwargs.get("extract_source_offset") or 0)
    chunk_id = kwargs.get("extract_chunk_id")
    if "fail" in file_path:
        raise RuntimeError("extract boom")
    if preset == "work":
        raw = "TASK | Update docs | Update docs before release\nRISK | Slow CPU fallback | Slow CPU fallback can surprise users"
    else:
        raw = (
            "CLAIM | Local workers help frontier models | Local workers help frontier models\n"
            "ENTITY | model | qwen3.5:4b | family=Qwen; role=default worker | qwen3.5:4b\n"
            "LINK | https://example.com | Example link | https://example.com\n"
            "BROKEN LINE | nope"
        )
    candidates, diagnostics = parse_tagged_extract(
        raw,
        preset=preset,
        source_path=file_path.split("#", 1)[0],
        source_text=source_text,
        chunk_id=str(chunk_id) if chunk_id else None,
        source_offset=source_offset,
    )
    items, dedupe = dedupe_items(candidates, max_items=int(kwargs.get("extract_max_items") or 40))
    diagnostics["dedupe"] = dedupe
    payload = {
        "preset": preset,
        "focus": focus,
        "items": items,
        "counts": {"items": len(items), "by_type": {}},
        "limits": {"max_items": 40, "snippet_max_chars": 240},
        "diagnostics": diagnostics,
        "source_files": [file_path.split("#", 1)[0]],
    }
    return FarmModelResult(
        payload=payload,
        markdown="# Extract Results\n",
        raw_response=raw,
        structured_valid=True,
        warnings=["extract_invalid_tagged_lines"] if diagnostics["invalid_line_count"] else [],
    )


class ExtractParserTests(unittest.TestCase):
    def test_parse_tagged_extract_keeps_valid_lines_and_warns_on_invalid(self) -> None:
        source = "Local workers help frontier models. qwen3.5:4b is the default."
        items, diagnostics = parse_tagged_extract(
            "CLAIM | Local workers help frontier models | Local workers help frontier models\n"
            "ENTITY | model | qwen3.5:4b | family=Qwen; role=default | qwen3.5:4b\n"
            "SURPRISE | nope",
            preset="research",
            source_path="article.txt",
            source_text=source,
        )

        self.assertEqual(len(items), 2)
        self.assertEqual(diagnostics["invalid_line_count"], 1)
        self.assertEqual(items[0]["sources"][0]["char_start"], 0)
        self.assertEqual(items[1]["entity_type"], "model")
        self.assertEqual(items[1]["attributes"]["family"], "Qwen")

    def test_dedupe_merges_sources(self) -> None:
        left = {
            "type": "claim",
            "text": "Same claim",
            "rank_score": 0.7,
            "source_support": "snippet_verified",
            "dedupe_key": "claim:same-claim",
            "sources": [{"file": "a.txt", "chunk_id": "chunk-0001", "snippet": "Same claim", "source_support": "snippet_verified", "char_start": 0, "char_end": 10}],
        }
        right = {
            **left,
            "sources": [{"file": "b.txt", "chunk_id": "chunk-0002", "snippet": "Same claim", "source_support": "snippet_verified", "char_start": 20, "char_end": 30}],
        }

        items, diagnostics = dedupe_items([left, right], max_items=10)

        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0]["sources"]), 2)
        self.assertEqual(diagnostics["duplicate_count"], 1)


class ExtractFarmRunTests(unittest.TestCase):
    def test_extract_run_writes_job_and_run_level_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.txt").write_text(
                "Local workers help frontier models. qwen3.5:4b is the default. https://example.com",
                encoding="utf-8",
            )

            status = sift_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=root / "results",
                mode="extract",
                instructions=None,
                extract_focus="Capture models.",
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=extract_processor,
            )

            run_dir = Path(status["output"]["path"])
            self.assertEqual(status["status"], "complete_with_warnings")
            self.assertEqual(status["request"]["extract_preset"], "research")
            self.assertEqual(status["request"]["extract_focus"], "Capture models.")
            self.assertTrue((run_dir / "extract-results.json").exists())
            self.assertTrue((run_dir / "EXTRACT_RESULTS.md").exists())
            result = sift_farm.read_json(run_dir / "jobs" / "job-0001" / "result.json")
            aggregate = sift_farm.read_json(run_dir / "extract-results.json")
            self.assertEqual(result["mode"], "extract")
            self.assertGreaterEqual(len(result["result"]["items"]), 2)
            self.assertEqual(aggregate["mode"], "extract")
            self.assertEqual(aggregate["coverage"]["status"], "complete")

    def test_chunked_extract_uses_map_only_and_merges_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "long.txt").write_text(
                "Local workers help frontier models.\n\n" * 20 + "qwen3.5:4b is the default.",
                encoding="utf-8",
            )

            status = sift_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=root / "results",
                mode="extract",
                instructions=None,
                chunk_chars=120,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=extract_processor,
            )

            run_dir = Path(status["output"]["path"])
            result = sift_farm.read_json(run_dir / "jobs" / "job-0001" / "result.json")
            self.assertTrue(result["chunking"]["enabled"])
            self.assertGreater(result["chunking"]["chunk_count"], 1)
            kinds = [call["kind"] for call in result["timing"]["calls"]]
            self.assertTrue(kinds)
            self.assertTrue(all(kind == "chunk_map" for kind in kinds))
            self.assertTrue((run_dir / "jobs" / "job-0001" / "chunk-results" / "chunk-0001" / "raw-response.txt").exists())

    def test_extract_partial_run_aggregate_includes_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.txt").write_text("Local workers help frontier models.", encoding="utf-8")
            (root / "input" / "fail.txt").write_text("fail", encoding="utf-8")

            status = sift_farm.run_farm(
                root=root,
                input_folder=root / "input",
                output_dir=root / "results",
                mode="extract",
                instructions=None,
                agent_id="default",
                default_model="qwen-test:1b",
                ollama_base_url="http://127.0.0.1:11434",
                model_processor=extract_processor,
            )

            aggregate = sift_farm.read_json(Path(status["output"]["path"]) / "extract-results.json")
            self.assertEqual(status["status"], "partial")
            self.assertEqual(aggregate["coverage"]["status"], "partial")
            self.assertEqual(len(aggregate["failures"]), 1)

    def test_extract_rejects_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents").mkdir()
            (root / "input").mkdir()
            (root / "input" / "a.txt").write_text("A", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "extract-focus"):
                sift_farm.run_farm(
                    root=root,
                    input_folder=root / "input",
                    output_dir=root / "results",
                    mode="extract",
                    instructions="Do this.",
                    agent_id="default",
                    default_model="qwen-test:1b",
                    ollama_base_url="http://127.0.0.1:11434",
                    model_processor=extract_processor,
                )
