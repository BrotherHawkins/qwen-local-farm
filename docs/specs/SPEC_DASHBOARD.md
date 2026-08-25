# Spec Dashboard

This dashboard tracks living specs and change specs.

The dashboard is manually maintained and CI-guarded. Update it when adding, accepting, implementing, or deprecating specs.

## Counts

### Canonical Specs

| Status | Count |
| --- | ---: |
| Draft | 0 |
| Accepted | 0 |
| Implemented | 1 |
| Deprecated | 0 |

### Change Specs

| Status | Count |
| --- | ---: |
| Draft | 0 |
| Accepted | 0 |
| Implemented | 35 |
| Deprecated | 0 |

## Draft Canonical Specs

None.

## Draft Change Specs

| ID | Type | Spec | Summary |
| --- | --- | --- | --- |
None.

## Accepted Not Implemented

| ID | Spec | Plan | Summary |
| --- | --- | --- | --- |
None.

## Current Groomed Focus

This is advisory, not a lifecycle state. See [../backlog.md](../backlog.md) for durable backlog rows.

| Rank | Candidate | Backlog |
| ---: | --- | --- |
| 1 | Platform-specific skill installation helpers | BL-0107 |
| 2 | Skip non-retryable jobs by default in `retry-failed` | BL-0099 |
| 3 | Reserved prompt-wrapper budget | BL-0065 |

## Implemented Specs

| Spec | Plan | Summary |
| --- | --- | --- |
| [farm-mvp.md](implemented/farm-mvp.md) | [0001-implement-worker-farm-mvp.md](plans/0001-implement-worker-farm-mvp.md) | First worker-farm MVP behavior: folder input, filesystem state, run status, Markdown plus JSON outputs. |

## Deprecated Specs

None.

## Change Specs

| ID | Status | Type | Spec | Summary |
| --- | --- | --- | --- | --- |
| 0000 | Implemented | Add | [0000-add-minimal-pr-gate.md](changes/0000-add-minimal-pr-gate.md) | Adds the first lightweight GitHub Actions PR gate for compile and unit test checks. |
| 0001 | Implemented | Add | [0001-add-worker-farm-mvp.md](changes/0001-add-worker-farm-mvp.md) | Adds the first filesystem-backed worker-farm MVP. |
| 0002 | Implemented | Add | [0002-add-summarize-chunking.md](changes/0002-add-summarize-chunking.md) | Adds chunked map/reduce summarization for oversized summarize inputs. |
| 0003 | Implemented | Add | [0003-add-farm-runtime-profiles.md](changes/0003-add-farm-runtime-profiles.md) | Adds explicit runtime profiles, config resolution, and resolved config artifacts for different local machine capacities. |
| 0004 | Implemented | Add | [0004-add-farm-scheduler-concurrency.md](changes/0004-add-farm-scheduler-concurrency.md) | Adds bounded file-job concurrency using resolved runtime profile settings. |
| 0005 | Implemented | Add | [0005-add-farm-timing-metrics.md](changes/0005-add-farm-timing-metrics.md) | Adds run, job, model-call, chunk, reduce, and dogfood timing summary artifacts. |
| 0006 | Implemented | Add | [0006-add-tokenizer-aware-chunk-sizing.md](changes/0006-add-tokenizer-aware-chunk-sizing.md) | Adds opt-in tokenizer-aware summarize chunk sizing and dogfood_lite baseline comparison. |
| 0007 | Implemented | Add | [0007-add-source-snippets-for-summarize.md](changes/0007-add-source-snippets-for-summarize.md) | Adds opt-in verified verbatim source snippets to summarize results. |
| 0008 | Implemented | Add | [0008-add-snippet-ranking-and-quality-metrics.md](changes/0008-add-snippet-ranking-and-quality-metrics.md) | Improves verified snippet usefulness with deterministic ranking, diversity, and quality diagnostics. |
| 0009 | Implemented | Add | [0009-add-dogfood-quality-history.md](changes/0009-add-dogfood-quality-history.md) | Adds a local dogfood quality history workflow to record and compare summarize/snippet run quality over time. |
| 0010 | Implemented | Add | [0010-add-cross-file-snippet-packs.md](changes/0010-add-cross-file-snippet-packs.md) | Adds deterministic cross-file snippet packs from existing summarize run artifacts for downstream synthesis. |
| 0011 | Implemented | Add | [0011-add-summary-snippet-synthesis-bundles.md](changes/0011-add-summary-snippet-synthesis-bundles.md) | Adds post-run synthesis bundles that combine compact per-file summaries with selected verified snippets. |
| 0012 | Implemented | Add | [0012-add-run-id-lookup-for-post-run-helpers.md](changes/0012-add-run-id-lookup-for-post-run-helpers.md) | Lets post-run helper commands accept known farm run IDs as well as run directory paths. |
| 0013 | Implemented | Add | [0013-add-farm-status-json.md](changes/0013-add-farm-status-json.md) | Adds machine-readable JSON output for `farm status` overview and single-run inspection. |
| 0014 | Implemented | Add | [0014-add-synthesis-bundle-budget-planning.md](changes/0014-add-synthesis-bundle-budget-planning.md) | Adds size estimates and optional character/estimated-token caps for synthesis bundles. |
| 0015 | Implemented | Add | [0015-add-farm-doctor.md](changes/0015-add-farm-doctor.md) | Adds a read-only farm doctor report for setup, model, runtime, tokenizer, and recent-run inspection. |
| 0016 | Implemented | Add | [0016-add-artifact-schemas-and-validation.md](changes/0016-add-artifact-schemas-and-validation.md) | Adds tracked schema contracts and model-free validation coverage for key farm JSON artifacts. |
| 0017 | Implemented | Add | [0017-add-schema-validation-cli.md](changes/0017-add-schema-validation-cli.md) | Adds a public model-free CLI for validating farm JSON artifacts against tracked schemas. |
| 0018 | Implemented | Add | [0018-add-post-run-package-schemas.md](changes/0018-add-post-run-package-schemas.md) | Adds schemas and validator auto-detection for post-run timing, snippet, synthesis, and dogfood package artifacts. |
| 0019 | Implemented | Add | [0019-add-dogfood-timing-history.md](changes/0019-add-dogfood-timing-history.md) | Adds local timing history records and comparisons for spotting dogfood performance regressions. |
| 0020 | Implemented | Add | [0020-add-benchmark-based-profile-recommendations.md](changes/0020-add-benchmark-based-profile-recommendations.md) | Adds measured local profile, chunking, and concurrency recommendations for power users and doctor-guided setup. |
| 0021 | Implemented | Add | [0021-add-safe-recommendation-config-apply.md](changes/0021-add-safe-recommendation-config-apply.md) | Adds a safe preview/write workflow for applying recommendation JSON to `.sift-farm.json`. |
| 0022 | Implemented | Add | [0022-add-resource-aware-runtime-modes.md](changes/0022-add-resource-aware-runtime-modes.md) | Adds first-class `auto`, `gpu`, `hybrid`, and `cpu` resource modes to config, CLI, resolved artifacts, and recommendation apply. |
| 0023 | Implemented | Add | [0023-add-spec-dashboard-consistency-checks.md](changes/0023-add-spec-dashboard-consistency-checks.md) | Adds a model-free CI guard for spec dashboard counts, change-spec rows, status/type values, and plan links. |
| 0024 | Implemented | Add | [0024-add-farm-collect.md](changes/0024-add-farm-collect.md) | Adds a post-run `farm collect` helper for flattening and indexing existing job result artifacts. |
| 0025 | Implemented | Add | [0025-add-configurable-farm-failure-policy.md](changes/0025-add-configurable-farm-failure-policy.md) | Adds caller-configurable farm retry/timeout policy and independent chunk/reduce retries. |
| 0026 | Implemented | Add | [0026-add-markdown-heading-ancestry-and-chunk-overlap.md](changes/0026-add-markdown-heading-ancestry-and-chunk-overlap.md) | Adds Markdown heading ancestry and opt-in chunk overlap to improve chunked summarize context. |
| 0027 | Implemented | Add | [0027-add-in-progress-chunk-and-reduce-status.md](changes/0027-add-in-progress-chunk-and-reduce-status.md) | Adds active chunk map and reduce progress visibility to farm status artifacts. |
| 0028 | Implemented | Add | [0028-add-failed-file-retry.md](changes/0028-add-failed-file-retry.md) | Adds a retry command for rerunning failed files from a prior farm run. |
| 0029 | Implemented | Add | [0029-add-failure-classification-and-retry-guidance.md](changes/0029-add-failure-classification-and-retry-guidance.md) | Adds durable failure codes, retryability flags, and recommended next actions for failed farm jobs. |
| 0030 | Implemented | Add | [0030-add-farm-discovery-include-exclude-overrides.md](changes/0030-add-farm-discovery-include-exclude-overrides.md) | Adds reproducible include/exclude controls for farm file discovery. |
| 0031 | Implemented | Add | [0031-add-model-family-adapter-foundation.md](changes/0031-add-model-family-adapter-foundation.md) | Adds a model-family adapter foundation so Qwen stays the default while other local model families can be added later without changing farm interfaces. |
| 0032 | Implemented | Add | [0032-add-ai-skills-library.md](changes/0032-add-ai-skills-library.md) | Adds a portable AI skills library so AI assistants can guide users through Sift setup and operation. |
| 0033 | Implemented | Add | [0033-add-hardware-specific-model-install-guidance.md](changes/0033-add-hardware-specific-model-install-guidance.md) | Adds hardware-specific model installation guidance for humans, AI assistants, doctor reports, and recommendation reports. |
| 0034 | Implemented | Add | [0034-add-package-shaping-budget-controls.md](changes/0034-add-package-shaping-budget-controls.md) | Adds package shaping and budget controls for synthesis bundles and snippet packs. |

## Stale Drafts To Revisit

None yet.

Future AI review can surface drafts that have not changed recently or appear ready for human acceptance.
