# qwen3-8b-cpu cold

- Model: `qwen3:8b`
- Wall seconds: `94.63`
- Load seconds: `5.828`
- Prompt tokens/sec: `45.17`
- Completion tokens/sec: `8.72`
- Completion tokens: `228`
- VRAM bytes: `0`

## Summary

- The LLM Wiki is a persistent, compounding knowledge base built and maintained by an LLM, not re-derived on every query.  
- The core idea is to incrementally integrate new sources into a structured, interlinked markdown wiki rather than using traditional RAG methods.  
- The wiki includes summaries, entity pages, concept pages, and cross-references, with the LLM handling updates and consistency.  
- The schema defines the wiki structure, conventions, and workflows, guiding the LLM as a disciplined knowledge maintainer.  
- Ingestion involves adding sources, discussing key points, and updating the wiki with summaries, entity pages, and cross-references.  
- Queries against the wiki allow for synthesized answers, which can be saved as new pages, enhancing the knowledge base over time.  
- Linting checks for contradictions, stale claims, orphan pages, and missing references, ensuring the wiki remains accurate and up-to-date.  
- Tools like Obsidian, qmd, and Dataview help organize, search, and visualize the wiki, while the LLM handles the bulk of maintenance and synthesis.
