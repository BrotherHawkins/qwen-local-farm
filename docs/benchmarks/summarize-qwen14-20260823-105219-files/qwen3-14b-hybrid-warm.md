# qwen3-14b-hybrid warm

- Model: `qwen3:14b`
- Wall seconds: `38.368`
- Load seconds: `0.01`
- Prompt tokens/sec: `21163.86`
- Completion tokens/sec: `7.81`
- Completion tokens: `298`
- VRAM bytes: `5817478676`

## Summary

- The LLM Wiki pattern builds a **persistent, compounding knowledge base** by having the LLM incrementally update a structured, interlinked collection of markdown files, rather than re-deriving knowledge from raw documents on every query.  
- The LLM **automatically summarizes, cross-references, and updates** the wiki with new sources, maintaining consistency and synthesis over time.  
- The system has three layers: **raw sources** (immutable documents), the **wiki** (LLM-generated markdown files), and the **schema** (a configuration file defining the wiki's structure and conventions).  
- **Ingest** involves adding a new source, and the LLM updates the wiki by creating summaries, updating entity/concept pages, and logging changes.  
- **Query** allows users to ask questions, and the LLM synthesizes answers from the wiki, which can be saved back as new pages to compound knowledge.  
- **Lint** is a periodic maintenance step where the LLM checks for contradictions, stale information, and missing links, ensuring the wiki remains accurate and organized.  
- **index.md** and **log.md** are special files that help navigate the wiki: the index catalogs all pages, while the log tracks the wiki's evolution chronologically.  
- Tools like **Obsidian**, **qmd**, **Marp**, and **Dataview** enhance the wiki's usability, enabling visualization, search, and dynamic content generation.
