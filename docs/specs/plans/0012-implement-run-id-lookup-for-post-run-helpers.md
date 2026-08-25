# 0012 Implement Run-ID Lookup For Post-Run Helpers

Status: Implemented
Spec: [0012 Add Run-ID Lookup For Post-Run Helpers](../changes/0012-add-run-id-lookup-for-post-run-helpers.md)

## Plan

Implement the small run-reference lookup behind the existing post-run helper commands:

1. Add a shared `resolve_run_reference(root, run_ref)` helper in `sift_farm`.
2. Preserve existing path input by checking filesystem paths before run ID lookup.
3. Resolve exact run IDs through the existing run index.
4. Emit clear errors for unknown references, stale indexed paths, and directories missing `farm-status.json`.
5. Wire `farm snippets pack`, `farm synthesis bundle`, and `farm dogfood record` through the resolver.
6. Update CLI help/docs from `<run-dir>` to `<run-ref>` where users see the argument.
7. Add model-free tests for resolver behavior and CLI handler wiring.
8. Mark 0012 and BL-0058 implemented in the implementation PR.

## Acceptance Notes

Accepted by the user before implementation. No full dogfood rerun is required because the change only resolves existing run references before calling current post-run artifact builders.

## Verification

Implemented with:

- shared `sift_farm.resolve_run_reference`
- run-ID support for `farm snippets pack`, `farm synthesis bundle`, and `farm dogfood record`
- README and AI usage documentation updates
- model-free resolver and CLI handler tests

Checks:

```powershell
python -m unittest tests.test_sift_farm tests.test_sift_cli
python -m unittest discover -s tests
```
