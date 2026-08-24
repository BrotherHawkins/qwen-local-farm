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
| Implemented | 7 |
| Deprecated | 0 |

## Draft Canonical Specs

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

## Stale Drafts To Revisit

None yet.

Future AI review can surface drafts that have not changed recently or appear ready for human acceptance.
