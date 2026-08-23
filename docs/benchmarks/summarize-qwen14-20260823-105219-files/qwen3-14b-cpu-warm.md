# qwen3-14b-cpu warm

- Model: `qwen3:14b`
- Wall seconds: `66.926`
- Load seconds: `0.011`
- Prompt tokens/sec: `12408.3`
- Completion tokens/sec: `4.43`
- Completion tokens: `295`
- VRAM bytes: `0`

## Summary

- The LLM Wiki pattern builds a **persistent, compounding knowledge base** by having the LLM incrementally update a structured, interlinked collection of markdown files, rather than re-deriving knowledge from raw documents on each query.  
- Unlike RAG, which retrieves and synthesizes knowledge at query time, the LLM Wiki **maintains a persistent, evolving artifact** that accumulates and refines knowledge over time.  
- The LLM handles **summarizing, cross-referencing, and updating** the wiki, while the user focuses on sourcing, exploration, and asking the right questions.  
- The architecture includes **raw sources**, the **wiki** (LLM-generated markdown files), and a **schema** that defines the wiki’s structure and conventions for the LLM to follow.  
- **Ingest** involves adding new sources, and the LLM updates the wiki by creating summaries, updating entity and concept pages, and logging changes.  
- **Query** allows the LLM to search the wiki, synthesize answers with citations, and optionally file new insights back into the wiki as new pages.  
- **Lint** involves the LLM periodically checking for contradictions, stale information, and missing links to keep the wiki accurate and well-organized.  
- **index.md** and **log.md** are two key files: the former catalogs the wiki’s content, and the latter tracks the wiki’s evolution chronologically.
