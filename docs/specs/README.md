# Specs

This folder contains living behavioral specs for Qwen Local Farm.

Roadmaps describe where the project may go. Specs describe behavior that is being proposed, accepted, implemented, or deprecated.

Specs should be practical, short enough to maintain, and specific enough to test.

## Spec Types

### Canonical Specs

Canonical specs describe subsystem behavior.

Locations:

```text
docs/specs/drafts/
docs/specs/accepted/
docs/specs/implemented/
docs/specs/deprecated/
```

Moving a canonical spec between lifecycle folders is a human-controlled status change.

### Change Specs

Change specs describe a specific proposed add/modify/delete behavior change.

Location:

```text
docs/specs/changes/
```

Change specs stay in one chronological folder and use an internal `Status` field. They should not move between lifecycle folders.

## Status Values

| Status | Meaning |
| --- | --- |
| `Draft` | Useful thinking, not binding yet. |
| `Accepted` | Human-approved behavior target. |
| `Implemented` | Behavior has landed in code/docs/tests. |
| `Deprecated` | Behavior is no longer the preferred contract. |

Merging a draft spec does not make it accepted. A human controls progression from `Draft` to `Accepted`.

## Implementation Plans

When a human accepts a behavior spec, the next AI-assisted step should be an implementation plan before runtime code is changed.

Implementation plans live in:

```text
docs/specs/plans/
```

Plan files should tie an accepted spec to:

- intended implementation steps
- test plan
- manual verification plan
- docs updates
- spec lifecycle updates needed after implementation

The plan should name when the canonical spec can move from `accepted/` to `implemented/` and when any related change spec can move to `Implemented`.

Planning-only PRs can still use `NO-SPEC`, but once an accepted behavior spec is being implemented, the implementation PR should cite the relevant plan.

## AI Process Gate

For behavior-changing work, AI assistants should follow this order:

1. Draft or update the change spec.
2. Stop for human acceptance of the behavior target.
3. Draft or update the implementation plan.
4. Stop for human acceptance of the plan.
5. Implement only after both gates are satisfied.
6. Update spec/dashboard status only when the corresponding human-controlled lifecycle step has happened.

Do not mark a change spec `Accepted` without explicit human acceptance.
Do not mark a change spec `Implemented` while it is only local WIP.
Do not open an implementation PR for behavior-changing work unless it cites an accepted spec and plan, or explicitly uses `NO-SPEC`.

## Change Types

Change specs should identify one of:

| Type | Meaning |
| --- | --- |
| `Add` | Introduces new behavior. |
| `Modify` | Changes existing behavior. |
| `Delete` | Removes existing behavior. |

## Required Sections

Behavior specs and change specs should include:

```text
# Title

Status: Draft | Accepted | Implemented | Deprecated
Type: Add | Modify | Delete    # change specs only

## WHY

## Scope

## Non-Goals

## Behavior

## Acceptance Criteria

## Deferred To Roadmap
```

Specs should not carry unresolved open questions. Decisions should be answered in the spec, or deferred into roadmap/backlog language.

## WHY Comes First

Every behavior-changing spec should explain why the behavior exists before defining details.

The WHY should cover:

- the user or caller problem
- the product principle being protected
- the tradeoff being made

## Spec Requirements For PRs

Behavior-changing PRs should do one of:

1. Add or update a canonical spec.
2. Add a change spec.
3. Cite an existing spec if the behavior is already covered.

Use the lightest spec artifact that keeps future behavior understandable.

Examples:

| Work Type | Spec Expectation |
| --- | --- |
| Major feature | Update/add canonical spec and add a change spec. |
| Small behavior change | Change spec may be enough. |
| Tiny fix | Cite existing spec and update tests. |
| Planning/docs-only | Mark `NO-SPEC`. |

## NO-SPEC Changes

Use `NO-SPEC` for changes that do not define or alter accepted behavior.

Examples:

- roadmap exploration
- planning docs
- typo fixes
- PR summary updates
- benchmark notes

## Dashboard

Keep [SPEC_DASHBOARD.md](SPEC_DASHBOARD.md) updated when adding or changing specs.

The dashboard is intentionally manual for now. Future tooling can regenerate or audit it.
