# qwen3-8b-gpu cold

- Model: `qwen3:8b`
- Wall seconds: `14.644`
- Load seconds: `6.38`
- Prompt tokens/sec: `715.96`
- Completion tokens/sec: `50.9`
- Completion tokens: `218`
- VRAM bytes: `5499550433`

## Summary

- **LLM Wiki** is a persistent, compounding knowledge base built and maintained by an LLM, not re-derived on every query.  
- The LLM **integrates new sources** into an evolving, structured markdown wiki with cross-references and synthesis.  
- The **wiki is maintained automatically** by the LLM, which updates summaries, flags contradictions, and keeps content current.  
- The **architecture** includes raw sources, the wiki itself, and a schema that defines structure and workflows for the LLM.  
- **Ingest** involves adding sources and letting the LLM process them, updating relevant wiki pages and maintaining consistency.  
- **Queries** against the wiki can generate answers, tables, slides, or charts, which can be saved as new wiki pages.  
- **Linting** ensures the wiki remains healthy by checking for contradictions, stale data, and missing links.  
- **Index.md** and **log.md** help navigate and track the wiki’s evolution, with the index serving as a catalog and the log as a timeline.
