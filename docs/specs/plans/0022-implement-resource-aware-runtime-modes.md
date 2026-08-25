# 0022 Implement Resource-Aware Runtime Modes

Status: Implemented
Spec: [0022 Add Resource-Aware Runtime Modes](../changes/0022-add-resource-aware-runtime-modes.md)

## Plan

1. [x] Promote spec 0022 from draft to accepted for implementation.
2. [x] Extend runtime config validation and resolution with `resource_mode`.
   - add valid mode vocabulary
   - add profile defaults
   - add CLI override support
   - resolve requested/effective mode after agent load
   - enforce CPU mode with effective `num_gpu: 0`
   - fail obvious GPU/hybrid conflicts with CPU-forced agents
3. [x] Surface resource mode in run artifacts.
   - `farm-config.resolved.json`
   - compact runtime status metadata
   - status Markdown/JSON
   - timing and dogfood identity records where runtime identity is captured
4. [x] Update doctor and recommend flows.
   - add `--resource-mode`
   - include resource mode in doctor JSON/Markdown
   - let recommendations consider the requested/effective runtime resource mode
   - update next actions/docs for applying resource mode to config
5. [x] Update recommendation apply.
   - write valid `resource_mode` to `.sift-farm.json`
   - stop listing valid resource mode as guidance-only
   - keep `OLLAMA_NUM_PARALLEL` guidance-only
6. [x] Update schemas and docs.
   - affected JSON schemas
   - schema docs if field shape changes
   - README and AI usage docs
   - dashboard/backlog lifecycle
7. [x] Add model-free tests.
   - profile/config validation
   - CLI parsing/handler behavior
   - runtime enforcement/conflicts
   - doctor/recommend/apply behavior
   - schema validation
8. [x] Verify.
   - focused unit tests
   - full unit test suite
   - compileall
   - diff check

## Non-Goals

- multiple Ollama server pools
- automatic model-size switching
- automatic agent switching
- Ollama service management
- applying `OLLAMA_NUM_PARALLEL`
- dynamic scheduler backoff
- model calls in CI

## Acceptance Notes

Accepted by the user before implementation. The implementation PR should mark this plan, spec 0022, and BL-0072 implemented when code/docs/tests land.
