# qwen3-14b-cpu cold

- Model: `qwen3:14b`
- Wall seconds: `270.177`
- Load seconds: `17.729`
- Prompt tokens/sec: `15.47`
- Completion tokens/sec: `4.28`
- Completion tokens: `298`
- VRAM bytes: `0`

## Summary

- The LLM Wiki pattern builds a **persistent, compounding knowledge base** by having the LLM incrementally update a structured wiki of markdown files, rather than re-deriving knowledge from raw documents on each query.  
- The wiki is a **centralized, interlinked collection** of summaries, entity pages, and concept pages, maintained by the LLM and updated as new sources are added.  
- The LLM handles **summarizing, cross-referencing, and maintaining consistency**, while the user curates sources, asks questions, and guides the process.  
- The architecture includes **three layers**: raw sources (immutable), the wiki (LLM-generated markdown), and a **schema** that defines the wiki’s structure and conventions for the LLM to follow.  
- **Ingest** involves adding new sources, and the LLM updates the wiki by creating summaries, updating entity pages, and appending to a log.  
- **Query** allows the user to ask questions, and the LLM synthesizes answers from the wiki, which can be saved back as new pages for compounding knowledge.  
- **Lint** is a periodic maintenance step where the LLM checks for contradictions, stale information, and missing links, ensuring the wiki remains accurate and well-organized.  
- Tools like **Obsidian** and **qmd** help manage the wiki, with Obsidian providing a visual interface and qmd enabling efficient search over markdown files.
