# 0033 Implement Hardware-Specific Model Install Guidance

Spec: [0033-add-hardware-specific-model-install-guidance.md](../changes/0033-add-hardware-specific-model-install-guidance.md)

## Outcome

Add beginner-readable and machine-readable hardware-specific model installation guidance, then expose it through doctor/recommend reports and AI-facing setup rails without adding automatic installers or model downloads.

## Checklist

- [x] Add `docs/model-installation.md` with hardware-band guidance.
- [x] Add `docs/model-installation.json` as the machine-readable guidance catalog.
- [x] Add `schemas/model-installation.schema.json` and register it in `schemas/index.json`.
- [x] Add schema auto-detection for the guidance catalog.
- [x] Add a shared guidance helper for doctor/recommend reports.
- [x] Add `model_installation_guidance` to doctor JSON and Markdown.
- [x] Add `model_installation_guidance` to recommendation JSON and Markdown.
- [x] Link the guide from README, platform notes, AI usage docs, and setup/operator skills.
- [x] Add model-free tests for catalog/schema sync, command parsing, docs links, stale references, and report fields.
- [x] Update spec dashboard and backlog bookkeeping.

## Verification

Run:

```bash
python -m unittest tests.test_sift_model_installation tests.test_sift_farm_doctor tests.test_sift_farm_recommend tests.test_sift_farm_schema tests.test_sift_skills
python -m unittest discover -s tests
python -m compileall sift.py examples src tests
python -m src.sift_spec_guard
python sift.py farm schema validate docs/model-installation.json --json
git diff --check
```

No Ollama model calls, model pulls, tokenizer downloads, or network access are required for this implementation.
