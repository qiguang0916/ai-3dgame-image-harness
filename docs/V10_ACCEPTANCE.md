# v0.10 Audited Batch Production Acceptance

Date: 2026-10-18, America/Los_Angeles.
Base: v0.9 native-host-autopilot at 91e9f3d.
Branch: feat/v0.10-steam-commercial-production.
Status: CODE_VALIDATED / PRODUCTION_VISUAL_SIGNOFF_PENDING / NOT_STEAM_CERTIFIED.

## Implemented

1. Workspace-scoped JSON batch, 1–128 unique jobs, bounded sequential native Codex image actions.
2. Preflight requires SHA-bound commercial rights evidence and explicit responsible reviewer, blocks unknown and noncommercial licenses, requires CC-BY attribution.
3. Immutable SHA-bound source manifest and parsed asset/edit specs, durable batch state, resumable jobs and no repeat model calls for accepted runs; partial conflicting evidence blocks.
4. Generation uses existing subscription-authenticated Codex ImageGen only; no direct API, local image weights or provider fallback.
5. Unity staging copies original bytes only after actual native PNG/receipt/QA/event source audit. Synthetic host output fails this audit; stage does not touch the Unity project.
6. CLI operations: batch validate, run, status, unity-stage.

## Verified in this development session

- python3 scripts/validate_project.py: PASS, six example docs.
- python3 -m unittest discover -s tests -q: **178 tests PASS**, exit 0 (168 baseline + 10 new).
- python3 scripts/demo_e2e.py: PASS (offline host protocol dry-run).
- git diff --check: PASS.
- New offline scenarios: multi-job bounds; pause/resume without duplicate host invocation; source/rights tamper denial; CC-BY attribution; swapped Run denial; synthetic artifacts not eligible for actual Unity staging.

One expected negative-case test writes a diagnostic that begins with ERROR; full suite exit 0 and summary OK distinguish it from a failure.

## Steam commercial release is STILL BLOCKED

- New multi-asset live v0.10 native ImageGen generation, independent visual critic evidence, production quality/drift benchmarks.
- Actual asset/source/license human verification. Saved license SHA and reviewer statements do not independently prove ownership, correct attribution, or legal permissions.
- Unity Editor import, in-game visual approval, and the independent full seven-category same-commit Unity Player release QA. Historical game whetstone selection test remains failed.
- KNIFE_001 current approved reference geometry/material acceptance.
- Applicable Steam AI disclosure, external Valve submission acceptance.

A batch with all source image jobs ACCEPTED or a produced PNG staging package is not a Steam certification or proof of actual Unity import.
