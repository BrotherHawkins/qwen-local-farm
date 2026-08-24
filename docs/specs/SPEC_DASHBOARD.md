# Spec Dashboard

This dashboard tracks living specs and change specs.

The dashboard is manual for now. Update it when adding, accepting, implementing, or deprecating specs.

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
| Implemented | 23 |
| Deprecated | 0 |

## Draft Canonical Specs

None.

## Draft Change Specs

None.

## Accepted Not Implemented

None.

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
| 0021 | Implemented | Add | [0021-add-safe-recommendation-config-apply.md](changes/0021-add-safe-recommendation-config-apply.md) | Adds a safe preview/write workflow for applying recommendation JSON to `.qwen-farm.json`. |
| 0022 | Implemented | Add | [0022-add-resource-aware-runtime-modes.md](changes/0022-add-resource-aware-runtime-modes.md) | Adds first-class `auto`, `gpu`, `hybrid`, and `cpu` resource modes to config, CLI, resolved artifacts, and recommendation apply. |

## Stale Drafts To Revisit

None yet.

Future AI review can surface drafts that have not changed recently or appear ready for human acceptance.
