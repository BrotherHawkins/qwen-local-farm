# qwen3-8b-cpu warm

- Model: `qwen3:8b`
- Wall seconds: `23.402`
- Load seconds: `0.004`
- Prompt tokens/sec: `24561.4`
- Completion tokens/sec: `8.77`
- Completion tokens: `204`
- VRAM bytes: `0`

## Summary

- The LLM Wiki is a persistent, compounding knowledge base built and maintained by the LLM, not re-derived on every query.  
- It integrates new sources by extracting key info, updating entity pages, and flagging contradictions.  
- The wiki is structured with raw sources, a markdown-based knowledge layer, and a schema guiding the LLM's operations.  
- Ingestion involves processing new sources, updating summaries, and maintaining cross-references across the wiki.  
- Queries can generate answers in various formats, which can be saved back into the wiki for future use.  
- Linting checks for contradictions, stale claims, and missing links to keep the wiki healthy and up-to-date.  
- `index.md` and `log.md` help navigate and track the wiki's evolution, with the former listing pages and the latter recording events.  
- Tools like Obsidian, qmd, and Dataview enhance wiki management, while the LLM handles the bulk of the work.
