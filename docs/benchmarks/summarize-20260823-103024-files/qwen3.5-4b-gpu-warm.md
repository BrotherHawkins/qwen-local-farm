# qwen3.5-4b-gpu warm

- Model: `qwen3.5:4b`
- Wall seconds: `4.869`
- Load seconds: `0.003`
- Prompt tokens/sec: `63155.57`
- Completion tokens/sec: `79.91`
- Completion tokens: `383`
- VRAM bytes: `3074540174`

## Summary

- **Core Concept**: Shift from reactive Retrieval-Augmented Generation (RAG) to an active, persistent wiki where an LLM agent incrementally builds and maintains a structured Markdown knowledge base between raw sources and user queries.
- **Three-Layer Architecture**: Utilize immutable **Raw Sources** for truth, an LLM-owned **Wiki** layer for synthesized summaries and cross-references, and a **Schema** file to define structural conventions and workflows.
- **Operational Workflow**: Process new sources by having the LLM ingest them into the wiki (updating pages, logs, and indices), answer queries by synthesizing existing wiki content (optionally filing answers back as new pages), and periodically run **Lint** checks for contradictions or gaps.
- **Navigation Tools**: Maintain two critical files: an **index.md** cataloging all pages for fast retrieval without embeddings, and a **log.md** append-only timeline of ingests and queries to track evolution.
- **Practical Tooling**: Integrate Obsidian plugins like **Dataview** for querying frontmatter, **Marp** for generating slides, and **qmd** for local search; use the Web Clipper to convert web articles into Markdown sources.
- **Maintenance Advantage**: LLMs handle the tedious bookkeeping (cross-referencing, consistency checks, updates) that causes humans to abandon wikis, keeping the knowledge base current with near-zero marginal cost.
- **User Role vs. Agent Role**: The human curates sources, directs analysis, and asks high-level questions, while the LLM handles all summarization, filing, cross-referencing, and maintenance tasks.
- **Modular Implementation**: Treat the wiki as a Git repository of Markdown files; the pattern is abstract and domain-specific, allowing users to adapt directory structures, output formats, and tooling to their specific needs.
