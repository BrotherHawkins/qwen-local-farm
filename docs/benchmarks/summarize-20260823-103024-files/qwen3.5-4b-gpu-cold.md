# qwen3.5-4b-gpu cold

- Model: `qwen3.5:4b`
- Wall seconds: `11.268`
- Load seconds: `5.761`
- Prompt tokens/sec: `2444.21`
- Completion tokens/sec: `79.0`
- Completion tokens: `340`
- VRAM bytes: `3074540174`

## Summary

- **Core Concept**: Shift from standard RAG (retrieval at query time) to an incremental, persistent wiki where an LLM agent continuously builds and maintains a structured Markdown knowledge base between raw sources and user queries.
- **Architecture Layers**: Utilize three distinct layers: immutable **Raw Sources** for truth; the **Wiki** (LLM-generated Markdown pages) for synthesized knowledge; and a **Schema** file defining structure, conventions, and workflows.
- **Operational Workflow**: Process new sources by having the LLM ingest them, update relevant entity/concept pages, flag contradictions, and log changes, rather than just indexing for later retrieval.
- **Query & Synthesis**: Ask questions to generate answers with citations, but immediately file valuable insights, comparisons, or analyses back into the wiki as new permanent pages.
- **Maintenance Routine**: Periodically run "lint" checks to identify contradictions, stale claims, orphaned pages, and missing cross-references to ensure knowledge consistency.
- **Navigation Tools**: Use an `index.md` for content-oriented cataloging and a `log.md` for chronological history; optionally employ local search engines like `qmd` for scalable retrieval.
- **Practical Integration**: Leverage Obsidian plugins (Web Clipper, Dataview, Marp) and Git version control to manage sources, generate slides, query frontmatter, and track changes efficiently.
- **Human vs. LLM Roles**: Humans curate sources, direct analysis, and ask strategic questions; the LLM handles all bookkeeping, cross-referencing, summarizing, and maintenance tasks that typically cause humans to abandon wikis.
