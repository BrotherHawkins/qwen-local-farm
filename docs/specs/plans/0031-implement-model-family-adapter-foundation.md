# 0031 Implement Model Family Adapter Foundation

Status: Implemented
Change Spec: [0031-add-model-family-adapter-foundation.md](../changes/0031-add-model-family-adapter-foundation.md)

## Plan

- [x] Add a small model-family metadata resolver/registry for backend, family, support, tokenizer, and context metadata.
- [x] Update bundled Qwen agents to declare the new metadata cleanly.
- [x] Route tokenizer status/loading through the metadata resolver instead of a Qwen-only table.
- [x] Add normalized model metadata to loaded agents, resolved runtime config, status artifacts, result envelopes, doctor reports, and recommendation reports.
- [x] Update Markdown renderers, JSON schemas, README, and AI usage docs for the new model-family posture.
- [x] Add model-free tests for Qwen metadata, unknown-family fallback, invalid metadata validation, tokenizer behavior, doctor/recommend output, status/runtime persistence, and schema coverage.
- [x] Run focused tests, the full suite, compile checks, diff whitespace checks, and spec guard.
- [x] Run a real filesystem smoke under `.run/dogfood_0031/` that exercises bundled Qwen metadata plus an experimental unknown/non-Qwen agent with character and token chunking paths.

## Notes

- This is a clean private-repo refactor. Preserve the current user-facing command spelling, but do not preserve older internal agent/config/status shapes solely because they existed before.
- Qwen remains the tested default. Unknown or non-Qwen Ollama families should be clearly labeled experimental/unknown and should use character chunking unless exact tokenizer metadata is available.
- No tests should require Ollama, local model weights, tokenizer downloads, or network access.
