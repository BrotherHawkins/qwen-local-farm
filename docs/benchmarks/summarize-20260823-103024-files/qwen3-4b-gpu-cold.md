# qwen3-4b-gpu cold

- Model: `qwen3:4b`
- Wall seconds: `14.899`
- Load seconds: `4.754`
- Prompt tokens/sec: `511.64`
- Completion tokens/sec: `83.49`
- Completion tokens: `384`
- VRAM bytes: `3116011356`

## Summary

Okay, the user wants me to summarize a technical article about "llm-wiki" in exactly 8 bullets. They're an offline research worker who needs concise, faithful technical summaries without any chain-of-thought. 

First I'll scan the article to identify core claims: It's about building personal knowledge bases using LLMs through a persistent wiki system that compounds knowledge instead of re-deriving it each time. Key differentiator from RAG is that the wiki gets updated incrementally as new sources are added.

Hmm... the architecture has three layers: raw sources (immutable), wiki (LLM-generated markdown), and schema (configuration). Operations include ingest, query, and lint. The indexing files (index.md and log.md) are crucial for navigation. 

For practical lessons, I notice the author emphasizes: 
- Ingesting sources one-by-one with human oversight 
- Turning answers into wiki pages 
- Using Obsidian for graph views 
- CLI tools like qmd for search 
- The maintenance burden is the real challenge LLMs solve

Terminology to retain: "persistent wiki", "incremental compounding", "raw sources", "schema", "index.md", "log.md", "ingest", "lint". Must avoid any examples or implementation details since user wants pure core claims.

*checks word count* Original is 1946 words but I need exactly 8 bullets. I'll prioritize: 
1. Core concept (compounding vs RAG) 
2. Architecture layers 
3. Key operations 
4. Indexing files 
5. Practical workflow 
6. Maintenance advantage 
7. Obsidian integration 
8. Optional tools 

Wait - the "why this works" section says LLMs handle bookkeeping while humans curate sources. That's critical for the 6th bullet. Also must include that contradictions get flagged during updates (
