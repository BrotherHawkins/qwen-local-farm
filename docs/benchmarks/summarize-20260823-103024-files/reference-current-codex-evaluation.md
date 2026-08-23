# Reference Summary And Evaluation

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

`qwen3:14b` hybrid produced the strongest summaries in the benchmark set. The best 14B hybrid run captured the persistent-knowledge-base framing, the contrast with RAG as repeated re-derivation, the raw/wiki/schema architecture, ingest/query/lint workflows, `index.md` and `log.md`, and the supporting toolchain. Compared with the 8B runs, it was a little better at preserving the article's system-design framing rather than reducing it to generic "summarize and organize notes" language.

`qwen3:14b` CPU/RAM produced similar content quality to the 14B hybrid run, which is expected because it is the same model and quantization. The CPU warm summary was especially faithful on the RAG contrast and the persistent evolving artifact idea. The tradeoff is speed: CPU-only 14B is workable for unattended batch jobs, but it is too slow to feel interactive.

`qwen3:4b` failed the instruction-following test. It recognized the right concepts internally, but emitted reasoning/planning text instead of the requested summary and hit the output-token cap. I would not use this one for unattended summarization unless we make a dedicated no-thinking Modelfile/prompt path and retest.

## 14B Benchmark Findings

The 14B benchmark used the same source file, same 8-bullet summary task, same `4096` token context, and same `384` max output-token budget as the earlier 4B/8B benchmark.

| Run | Cold wall | Model load | Load share | Same-prompt warm | Kept-warm estimate for a new file | Output speed | VRAM used |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `qwen3:14b` hybrid | 90.73s | 33.77s | 37% | 38.37s | ~56.96s | ~7.8 tok/s | ~5.82 GB |
| `qwen3:14b` CPU/RAM | 270.18s | 17.73s | 7% | 66.93s | ~252.45s | ~4.4 tok/s | 0 GB |

The hybrid profile is the practical 14B choice on this machine. It uses partial GPU offload with `num_gpu: 24`, stayed within the 8GB VRAM card, and generated roughly 1.8x faster than CPU-only. Its cold run was about 3x faster than CPU-only overall.

The CPU/RAM-only profile is still valuable as an overflow/offline mode. It protects VRAM completely and can run as a background worker, but on this document it should be planned in minutes per file rather than seconds per file.

Overall: keep `qwen3.5:4b` as the reliable default; use `qwen3:8b` GPU for faster higher-quality offline crunching; use `qwen3:14b` hybrid when quality matters more than speed; use CPU/RAM-only profiles only when preserving VRAM matters or the job can run unattended.
