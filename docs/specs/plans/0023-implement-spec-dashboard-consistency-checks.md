# 0023 Implement Spec Dashboard Consistency Checks

Status: Implemented
Spec: [0023 Add Spec Dashboard Consistency Checks](../changes/0023-add-spec-dashboard-consistency-checks.md)

## Plan

1. [x] Add a dependency-free spec guard module.
   - parse canonical specs by lifecycle folder
   - parse change specs by id/status/type
   - parse dashboard counts and change-spec rows
   - parse plan files and resolve their spec links
2. [x] Validate consistency.
   - allowed status/type values
   - dashboard counts match actual specs
   - dashboard rows match change spec files/statuses
   - accepted/implemented change specs have plans after legacy exemptions
   - plan `Spec:` links resolve
3. [x] Add CI coverage.
   - run `python -m src.qwen_spec_guard`
4. [x] Add unit tests.
   - valid fixture
   - dashboard count mismatch
   - missing dashboard row
   - row status mismatch
   - invalid status/type
   - missing plan
   - broken plan link
5. [x] Update docs and planning state.
   - specs README local command
   - dashboard counts/rows
   - BL-0002 implemented
   - deferred follow-ups captured
6. [x] Verify.
   - focused tests
   - full unit suite
   - compileall
   - spec guard
   - diff check

## Notes

Accepted by the user with approval to skip separate plan approval and proceed directly to implementation/PR.
