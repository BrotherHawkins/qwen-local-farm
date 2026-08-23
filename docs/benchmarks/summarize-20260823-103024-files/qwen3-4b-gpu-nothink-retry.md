# qwen3-4b-gpu nothink retry

- Wall seconds: 10.533
- Completion tokens/sec: 79.63

## Summary

Okay, the user wants me to summarize this Markdown article about "llm-wiki" in exactly 8 bullets. They specified focusing on core claims, practical lessons, and terminology. And I need to output only the bullets - no extra text.

First, I'll read through the article carefully to understand what it's about. It's from Andrej Karpathy's GitHub Gist about a pattern for building personal knowledge bases using LLMs. The key idea is that instead of traditional RAG systems where LLMs rediscover knowledge on every query, this approach creates a persistent wiki that accumulates knowledge incrementally.

Let me identify the core claims first. The article says that most LLMs work with RAG where they retrieve chunks at query time but don't build up knowledge. The LLM-wiki pattern has the LLM incrementally build and maintain a persistent wiki - a structured markdown collection that gets richer with each new source. The wiki is a compounding artifact where cross-references exist, contradictions are flagged, and synthesis is updated. 

For practical lessons, I see several: you drop new sources into a raw collection and tell the LLM to process them (ingest), you can query the wiki and have answers filed back as new pages, there's a lint process to keep the wiki healthy, and they use index.md and log.md for navigation. Also, tools like Obsidian Web Clipper and Dataview are mentioned as helpful.

Terminology is important too. The article uses terms like "raw sources" (immutable documents), "wiki" (LLM-generated markdown files), "schema" (configuration file), "ingest", "query", "lint", "index.md" (content catalog), "log.md" (chronological log), and mentions tools like qmd for search.

I need to condense this into exactly 8 bullets. Let me brainstorm
