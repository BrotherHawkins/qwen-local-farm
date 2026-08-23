from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / ".run" / "benchmarks" / "summarize-20260823-103024.json"
OUT_DIR = ROOT / ".run" / "benchmarks" / "summarize-20260823-103024-files"


REFERENCE = """# Reference Summary And Evaluation

## Reference Summary

- Karpathy's `llm-wiki` pattern replaces one-shot RAG with a persistent Markdown wiki that compounds knowledge over time.
- Raw sources remain immutable and serve as the source of truth; the LLM reads them but does not modify them.
- The wiki layer is LLM-authored: summaries, entity pages, concept pages, comparisons, cross-references, and synthesis pages.
- A schema file such as `AGENTS.md` or `CLAUDE.md` teaches the agent the directory structure, conventions, and workflows for this domain.
- Ingest means adding a source, having the LLM extract and discuss key takeaways, update many relevant pages, update `index.md`, and append `log.md`.
- Querying the wiki should synthesize answers from existing pages with citations, and valuable answers should be filed back into the wiki as durable pages.
- Linting is a maintenance pass for contradictions, stale claims, orphan pages, missing pages, weak cross-references, and data gaps.
- Obsidian, Git, Web Clipper, graph view, Dataview, Marp, and optional local search tools like `qmd` are supporting tools; the central insight is that LLMs make wiki maintenance cheap enough to actually sustain.

## Quality Opinion

`qwen3.5:4b` captured the article best among the small models. It included the architectural layers, ingest/query/lint loop, index/log distinction, tooling, Git/Obsidian framing, and the human-vs-LLM division of labor. It was slightly more verbose than the 8B summaries, but faithful and useful.

`qwen3:8b` on GPU gave the cleanest concise summary. It captured the main mechanism and maintenance loop well, but it omitted a few richer points from the article: the comparison to RAG as re-deriving knowledge, the human-in-the-loop role, Git/versioning, and the Memex analogy. For a fast offline worker, this was the best balance of speed and acceptable quality.

`qwen3:8b` on CPU produced essentially the same quality as the GPU version, as expected, because it is the same model and quantization. The difference is speed, not comprehension. Its cold run was very slow because prompt ingestion happened on CPU.

`qwen3:4b` failed the instruction-following test. It recognized the right concepts internally, but emitted reasoning/planning text instead of the requested summary and hit the output-token cap. I would not use this one for unattended summarization unless we make a dedicated no-thinking Modelfile/prompt path and retest.

Overall: keep `qwen3.5:4b` as the reliable default; use `qwen3:8b` GPU for higher-quality offline crunching when VRAM is free; use `qwen3:8b` CPU only when you want to preserve VRAM and are fine with much slower throughput.
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))

    for item in results:
        path = OUT_DIR / f"{item['id']}-{item['phase']}.md"
        lines = [
            f"# {item['id']} {item['phase']}",
            "",
            f"- Model: `{item['model']}`",
            f"- Wall seconds: `{item['wall_seconds']}`",
            f"- Load seconds: `{item['load_seconds']}`",
            f"- Prompt tokens/sec: `{item['prompt_tokens_per_second']}`",
            f"- Completion tokens/sec: `{item['completion_tokens_per_second']}`",
            f"- Completion tokens: `{item['completion_eval_count']}`",
            f"- VRAM bytes: `{item['loaded_size_vram']}`",
            "",
            "## Summary",
            "",
            item["summary"],
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")

    (OUT_DIR / "reference-current-codex-evaluation.md").write_text(REFERENCE, encoding="utf-8")

    print(OUT_DIR)
    for path in sorted(OUT_DIR.glob("*.md")):
        print(path.name)


if __name__ == "__main__":
    main()

