# qwen3-14b-hybrid cold

- Model: `qwen3:14b`
- Wall seconds: `90.729`
- Load seconds: `33.772`
- Prompt tokens/sec: `124.62`
- Completion tokens/sec: `7.78`
- Completion tokens: `266`
- VRAM bytes: `5817478676`

## Summary

- **LLM Wiki** is a method for building a persistent, structured knowledge base using LLMs, where the LLM incrementally updates and maintains a wiki of markdown files.  
- Unlike RAG, which retrieves documents at query time, the LLM Wiki compiles and keeps knowledge current, avoiding rediscovery on every query.  
- The LLM handles summarizing, cross-referencing, and updating pages, while the user focuses on sourcing, exploration, and asking questions.  
- The architecture includes **raw sources**, **the wiki** (LLM-generated markdown files), and a **schema** that defines how the wiki is structured and maintained.  
- **Ingest** involves adding new sources, and the LLM updates the wiki with summaries, entity pages, and cross-references.  
- **Query** allows users to ask questions, and the LLM synthesizes answers from the wiki, which can be saved back as new pages.  
- **Lint** is a periodic check for contradictions, stale claims, and missing links, helping maintain the wiki's accuracy and completeness.  
- Tools like **Obsidian**, **qmd**, and **Marp** support organizing, searching, and presenting wiki content, while **index.md** and **log.md** help navigate and track changes.
