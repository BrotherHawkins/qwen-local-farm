# 0023 Add Spec Dashboard Consistency Checks

Status: Implemented
Type: Add

## WHY

The project now relies on specs, plans, the spec dashboard, and backlog rows to preserve process memory across many small PRs. That only works if the planning index stays accurate.

We already saw a dashboard drift risk after a merge: the behavior landed, but the dashboard could lag behind the actual spec files. This change implements BL-0002 so CI can catch that kind of process drift before merge.

The goal is not a heavy documentation linter. The goal is a small, model-free guard that checks the few facts the repo uses as source-of-truth navigation:

- spec statuses use the allowed vocabulary
- dashboard counts match actual spec files
- dashboard change-spec rows match actual change specs
- accepted/implemented change specs have implementation plans where the current process expects them
- plan files point at existing spec files

## Scope

This change adds:

- a dependency-free Python spec consistency checker
- unit tests for the checker
- a CI step that runs the checker on pull requests and pushes to `main`
- docs showing how to run the checker locally
- dashboard/backlog lifecycle updates for BL-0002

The checker covers:

- canonical spec counts by lifecycle folder
- change spec counts by `Status:` field
- allowed status and type values
- change spec filename ID consistency
- dashboard change-spec row presence and status consistency
- plan-to-spec links for plan files
- matching implementation plans for accepted/implemented change specs, excluding legacy change spec `0000`

## Non-Goals

This change does not add:

- Markdown formatting lint
- prose style lint
- generated dashboard rewriting
- automatic spec creation
- GitHub branch protection changes
- model calls
- network access
- Ollama/model integration checks
- enforcement that every deferred sentence has a backlog row beyond the existing process docs

## Behavior

### Checker Command

Add a local command:

```powershell
python -m src.sift_spec_guard
```

The command exits:

- `0` when specs/dashboard/plans are consistent
- non-zero when one or more consistency errors are found

On failure, it prints actionable messages that name the file or spec id involved.

### Dashboard Checks

The checker reads:

```text
docs/specs/SPEC_DASHBOARD.md
docs/specs/changes/*.md
docs/specs/plans/*.md
docs/specs/drafts/*.md
docs/specs/accepted/*.md
docs/specs/implemented/*.md
docs/specs/deprecated/*.md
```

It compares actual spec files to dashboard counts and rows.

The dashboard remains human-edited for now. The checker audits it; it does not rewrite it.

### Plan Checks

Each plan file must include a `Spec:` or `Change Spec:` link pointing at an existing spec file.

Each accepted or implemented change spec should have a plan file whose filename begins with the same four-digit id.

Legacy exemption:

- `0000-add-minimal-pr-gate.md` predates the current plan convention and is allowed without a matching plan.

## Acceptance Criteria

- `python -m src.sift_spec_guard` exists and runs without third-party dependencies.
- The checker exits `0` on the current valid repo state.
- The checker reports dashboard count mismatches.
- The checker reports missing dashboard rows for change specs.
- The checker reports dashboard row status mismatches.
- The checker reports invalid change spec statuses or types.
- The checker reports missing implementation plans for accepted/implemented change specs after legacy exemptions.
- The checker reports plan files whose `Spec:` or `Change Spec:` link does not resolve.
- The GitHub Actions CI workflow runs the checker.
- Unit tests cover valid state and representative failure cases.
- Docs explain the local command.
- BL-0002 is marked implemented when this PR lands.

## Deferred To Roadmap

- Generated dashboard rewriting.
- Markdown formatting or prose style lint.
- Deferred-to-backlog semantic audits beyond simple checklist-style guardrails.
- Cross-file link checking outside the spec/plans/dashboard surface.
