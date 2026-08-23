# qwen3-8b-gpu warm

- Model: `qwen3:8b`
- Wall seconds: `3.683`
- Load seconds: `0.002`
- Prompt tokens/sec: `167605.05`
- Completion tokens/sec: `52.86`
- Completion tokens: `192`
- VRAM bytes: `5499550433`

## Summary

- The LLM Wiki is a persistent, compounding knowledge base built and maintained by the LLM, not re-derived on every query.  
- It integrates new sources by extracting key info, updating entity pages, and flagging contradictions.  
- The wiki is structured into raw sources, the wiki itself, and a schema that defines conventions and workflows.  
- Ingest involves processing new sources, generating summaries, and updating relevant pages in the wiki.  
- Queries are answered by synthesizing information from the wiki, with results optionally added as new pages.  
- Linting checks for contradictions, stale claims, and missing cross-references to keep the wiki healthy.  
- Index.md and log.md help navigate and track the wiki’s evolution, with index.md listing all pages and log.md recording events.  
- Tools like Obsidian, qmd, and Dataview enhance wiki management, while the LLM handles most of the maintenance.
