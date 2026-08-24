# 0007 Add Source Snippets For Summarize

Status: Implemented
Type: Add

## WHY

Dogfooding after 0006 showed that the fast summarize path is now quick enough for real use, but long technical articles can become terse after chunking and reduce. That terseness is acceptable for the first-pass summary, but a primary frontier model often benefits from a few true source passages when it later synthesizes, compares, or cites the material.

The farm should be able to preserve a small number of high-value verbatim snippets alongside the summary without returning to slow JSON grammar mode or bloating every summary by default.

This change favors:

- opt-in source evidence over longer default summaries
- configurable default snippet policy for assistant-operated use, with per-request overrides, per-file auto sizing, and fixed counts for reproducible power-user runs
- exact source verification over trusting quote-like model output
- one-pass summarize calls over extra extraction calls where practical
- compact snippets useful to a later frontier model
- stable JSON result shape for primary AI consumption
- visible warnings when strict requested snippets cannot be verified

## Scope

This change adds optional source snippet extraction to `summarize` mode:

- add summarize settings for snippet count and maximum snippet length
- add an automatic snippet count policy based on source size and/or chunk count
- add CLI overrides for one-off snippet extraction
- keep snippets disabled by default
- ask the local model to include candidate snippets in the same summarize call when snippets are requested
- validate every snippet against the source text before including it in final artifacts
- include snippets in `result.json` and `result.md`
- include snippet provenance such as source path and line/character location when practical
- support both single-pass summaries and chunked map/reduce summaries
- preserve the fast labeled-text summarize path and deterministic outer JSON envelope
- document when primary AIs should request snippets
- dogfood with the lite article set, focusing especially on article 005 as a small single-pass input and 009 as a chunked input

## Non-Goals

This change does not add:

- a new standalone extraction mode
- citation management across multiple files
- semantic search or embedding-based snippet retrieval
- generated paraphrase excerpts
- long quote packs or full article reproduction
- automatic snippet extraction by default
- snippet deduplication across separate farm runs
- UI review/acceptance state for snippets
- frontier model calls
- changes to chunk sizing or tokenizer setup

## Settings

Snippet extraction policy has normal farm config precedence:

1. Built-in default/profile.
2. Project `.qwen-farm.json` or explicit config file.
3. Per-request CLI override.

That means a power user or assistant can set a project default once, while a specific run can still override it.

Snippet extraction is off by default:

```json
{
  "summarize": {
    "snippet_policy": "off",
    "snippet_count": null,
    "snippet_min_count": 2,
    "snippet_max_count": 8,
    "snippet_max_chars": 600
  }
}
```

Power users can request a fixed count:

```json
{
  "summarize": {
    "chunk_strategy": "token",
    "snippet_policy": "fixed",
    "snippet_count": 3,
    "snippet_max_chars": 600
  }
}
```

Assistant-written config can enable automatic count selection:

```json
{
  "summarize": {
    "chunk_strategy": "token",
    "snippet_policy": "auto",
    "snippet_count": null,
    "snippet_min_count": 2,
    "snippet_max_count": 8,
    "snippet_max_chars": 600
  }
}
```

Project default example:

```json
{
  "summarize": {
    "chunk_strategy": "token",
    "snippet_policy": "auto",
    "snippet_count": null,
    "snippet_min_count": 2,
    "snippet_max_count": 8,
    "snippet_max_chars": 600
  }
}
```

Per-request CLI overrides:

```bash
python qwen.py farm run notes --mode summarize --snippets auto
python qwen.py farm run notes --mode summarize --snippets off
python qwen.py farm run notes --mode summarize --snippets 3
python qwen.py farm run notes --mode summarize --snippets 5 --snippet-max-chars 800
```

Rules:

- `snippet_policy` must be `off`, `fixed`, or `auto`.
- `snippet_count` is required when `snippet_policy` is `fixed`.
- `snippet_count` must be `null` or absent when `snippet_policy` is `auto` or `off`.
- `snippet_count`, when present, must be a non-negative integer.
- `snippet_min_count` must be a non-negative integer.
- `snippet_max_count` must be a non-negative integer greater than or equal to `snippet_min_count`.
- `snippet_max_chars` must be a positive integer.
- `--snippets off` and `--snippets 0` disable snippet extraction for that run.
- `--snippets auto` enables automatic count selection.
- `--snippets N` enables fixed count selection.
- CLI overrides win over config and profile defaults.
- Built-in profiles keep `snippet_policy: "off"` unless a future spec changes defaults, but user/project config can choose a different default.

## Auto Count Policy

When `snippet_policy` is `auto`, the farm calculates a requested snippet count for each file/job from that input's size and chunk shape instead of asking the user to pick an arbitrary number for every article.

The first implementation should use a simple, explainable heuristic:

```text
if snippets are off:
  requested = 0
else if fixed count is provided:
  requested = snippet_count
else if token count is available:
  requested = ceil(source_tokens / 3000)
else if chunked:
  requested = chunk_count + 1
else:
  requested = 2

requested = clamp(requested, snippet_min_count, snippet_max_count)
```

For chunked jobs, map calls may request a small number of candidates per chunk, such as 2, so the final reducer has enough verified choices. The final file-level snippet list remains capped by the resolved requested count.

The resolved snippet policy and count should be persisted in run/job artifacts so a human or primary AI can understand why a file received a given number of snippets.

Examples:

- A project configured with `snippet_policy: "auto"` makes snippets the default for normal summarize runs in that project.
- A run configured with `--snippets off` overrides the project default and resolves every job to 0 snippets.
- A run configured with `--snippets 3` overrides the project default and resolves every job to up to 3 snippets.
- A run configured through config or CLI with `snippet_policy: "auto"` may resolve a small single-pass file to 2 snippets and a larger chunked article to 6 snippets in the same run.

## Behavior

### Snippet Meaning

A snippet is a short verbatim passage from the source that is useful for later synthesis. Good snippets include:

- the article thesis or core claim
- a crisp definition
- a useful example or anecdote
- a concrete limitation, caveat, warning, or open question
- a memorable operational detail that a terse summary might lose

Snippets are not summary bullets. They should preserve source wording exactly.

The implementation filters obvious low-signal scaffolding from persisted snippets, including front matter, source URLs, conversion headers, and bibliography-style citation lines. This does not replace better ranking; it prevents common padding from occupying the requested snippet budget.

### Result Shape

When snippets are requested, the `summarize` result payload includes a `snippets` list:

```json
{
  "title": "Example",
  "abstract": "Short summary.",
  "bullets": ["Key point."],
  "open_questions": [],
  "confidence": "high",
  "snippets": [
    {
      "text": "Exact source passage.",
      "reason": "Why this passage matters for later synthesis.",
      "source_path": "article.txt",
      "start_line": 12,
      "end_line": 14,
      "char_start": 345,
      "char_end": 430
    }
  ]
}
```

`source_path` is required. Location fields are included when the farm can determine them reliably.

When snippets are not requested, the result may omit `snippets` or include an empty list. The implementation should choose the least disruptive option for existing tests and consumers, then document it.

### Exactness

The farm must not trust the local model's claim that text is verbatim.

For every candidate snippet:

1. Normalize only harmless boundary whitespace.
2. Search for the candidate in the relevant source text.
3. Include the snippet only if it matches exact source text after the allowed boundary normalization.
4. Record line and character location when matched.
5. Drop unmatched candidates and add a warning when the request needs strict fulfillment.

The farm must never silently include an unmatched quote-like snippet as source evidence.

### Single-Pass Summaries

For files that fit in one summarize call:

- the farm resolves the requested snippet count from `snippet_policy`
- the model receives the file content and resolved requested snippet count
- the response includes summary fields plus candidate snippets
- Python parses and validates candidates against the full source text
- final `result.json` includes up to the resolved requested count of verified snippets

If fewer than requested snippets can be verified, fixed-count requests complete with warnings. Auto requests expose the verified/requested count and stay clean when at least one verified snippet is preserved.

### Chunked Summaries

For chunked summarize jobs:

- each chunk map call may produce candidate snippets from that chunk
- chunk result artifacts may include verified chunk snippets
- final reduce output must not invent new source snippets
- final file-level snippets are selected from verified chunk snippets
- final snippets remain capped by the resolved requested count

The first implementation can use simple ordering or model-provided importance from chunk outputs. More advanced ranking can be deferred as long as final snippets are verified and useful.

### Markdown Output

When snippets are present, `result.md` includes:

```markdown
## Source Snippets

1. "Exact source passage."
   Why it matters: Reason.
   Source: article.txt:12-14
```

If snippets were requested but none were verified, `result.md` should make that visible without fabricating content.

### Warnings

Snippet-related warnings should be concise and machine-readable, for example:

- `snippet_candidates_unverified`
- `snippet_count_under_requested`
- `snippet_parse_fallback`

The presence of snippet warnings should mark the job `complete_with_warnings`, not failed, unless the normal summarize call itself fails. Auto partial counts are visible in artifacts without warning when at least one verified snippet is preserved.

### Performance

Snippet extraction should preserve the fast summarize call shape:

- no Ollama JSON grammar mode for the main summarize call
- keep `think: false`
- keep bounded summarize generation unless explicitly overridden
- do not add a second model call solely for snippets in the first implementation

If requested snippet counts make the response too long, the farm should prefer returning fewer verified snippets over expanding generation enough to reintroduce severe latency. Strict fixed-count requests should warn when underfilled.

## Acceptance Criteria

- `summarize.snippet_count` and `summarize.snippet_max_chars` are valid config fields.
- `summarize.snippet_policy`, `summarize.snippet_min_count`, and `summarize.snippet_max_count` are valid config fields.
- CLI supports `--snippets off`, `--snippets auto`, `--snippets N`, and `--snippet-max-chars N` for `farm run`.
- Existing runs without snippet settings behave as before, with snippets disabled.
- Project config can set a default snippet policy for future runs.
- CLI/request snippet settings override project config for that run.
- Auto snippet policy resolves a requested count from available token count, chunk count, or a documented fallback.
- Run-level snippet policy is persisted in resolved config artifacts.
- Per-job resolved snippet count is persisted in job result/status artifacts.
- Snippet-enabled single-pass summarize jobs include up to the requested number of verified source snippets in `result.json`.
- Snippet-enabled single-pass summarize jobs render verified snippets in `result.md`.
- Unverified candidate snippets are excluded from final results and surfaced through warnings for strict requests.
- Verified snippets include `source_path` and at least one reliable source location field when practical.
- Chunked summarize jobs can preserve verified chunk snippets and include up to the requested count in the final file-level result.
- Final reduce behavior cannot invent snippets that were not verified against source text.
- Snippet warnings can produce `complete_with_warnings` without failing the whole job.
- Fast summarize call-shape tests still prove summarize does not use Ollama JSON grammar mode by default.
- Unit tests cover config validation, CLI parsing, labeled snippet parsing, exact-match verification, unmatched candidate warnings, Markdown rendering, single-pass result shape, and chunked final snippet carry-forward.
- Docs explain when primary AIs should request snippets and how to inspect them.
- A focused dogfood run compares snippet-enabled summaries for articles 005 and 009 against the non-snippet fastpath run.

## Deferred To Roadmap

- Snippet ranking beyond simple model-proposed order or first-pass importance.
- Cross-file snippet packs for later synthesis.
- Dedicated `extract` mode and richer extraction schemas.
- Quote/citation export formats.
- Semantic retrieval or embedding-assisted snippet selection.
- Snippet review states such as accepted/rejected.
- Historical snippet-quality benchmark dashboards.
