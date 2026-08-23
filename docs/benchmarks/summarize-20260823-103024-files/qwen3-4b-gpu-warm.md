# qwen3-4b-gpu warm

- Model: `qwen3:4b`
- Wall seconds: `4.619`
- Load seconds: `0.002`
- Prompt tokens/sec: `166401.32`
- Completion tokens/sec: `83.78`
- Completion tokens: `384`
- VRAM bytes: `3116011356`

## Summary

Okay, the user wants me to summarize a technical article about "llm-wiki" in exactly 8 bullets. They need it to be concise and faithful to the core claims, practical lessons, and key terminology for a local-LLM user. No chain-of-thought allowed - just the bullets.

First, I'll scan the article to identify the absolute essentials. The title is "llm-wiki" by Andrej Karpathy on GitHub. The core idea is about building a persistent knowledge base where LLMs incrementally maintain a wiki instead of just doing RAG-style retrieval. 

Hmm... the key differences from traditional RAG are crucial: no re-deriving knowledge on every query, compounding knowledge over time, and the wiki being a living artifact. The architecture has three layers: raw sources (immutable), wiki (LLM-generated markdown), and schema (configuration). 

For practical lessons, the operations section stands out: ingest (processing new sources), query (getting answers that can become wiki pages), and lint (health checks). The indexing files (index.md and log.md) seem vital too - they're the navigation tools. 

Terminology to retain: "raw sources", "wiki", "schema", "ingest", "query", "lint", "index.md", "log.md". The article mentions tools like Obsidian and qmd but those are optional - better to focus on universal concepts. 

I should avoid examples (like Tolkien Gateway) since the user wants core claims. The "why this works" section explains the human-LLM division of labor - that's a key practical lesson. Also the note about it being intentionally abstract - important for local-LLM users to adapt it.

Let me structure 8 bullets:
1. Core concept (persistent compounding wiki vs RAG)
2. Key difference from RAG (no re-der
