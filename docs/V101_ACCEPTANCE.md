# v0.10.1 — Batch Durability / Fail-Closed Recovery Acceptance

Date: 2026-10-19 (America/Los_Angeles)
Version: `ai-3dgame-image-harness 0.10.1-dev`
Branch: `feat/v0.10-steam-commercial-production`
Base: `88c4a56` (v0.10 product design plan and v1 roadmap).
Scope: v0.10.1 A01/A02/A03 reliability hardening and A04 bounded actions preservation.
Status: CODE_VALIDATED; REAL_MULTI_ASSET_IMAGEGEN_NOT_TESTED; NOT_STEAM_CERTIFIED.

## Implementation changes

1. `execution_loop.save_run` now writes a complete JSON snapshot into an exclusively created temporary file, flushes and fsyncs it, then atomically `os.replace`s the previous run pointer; cleans failed temporary writes and rejects state symlinks. A replace/write failure cannot truncate the previous valid Run JSON. This protects run **state** only, not native generated source image authenticity.
2. `production_autopilot.drive` refuses a fresh run when old `run.json.production/` evidence remains, rather than initializing a conflicting run and blocking only after consuming or touching more work.
3. Standalone `--resume` verifies exact asset/edit paths, canonical parsed spec digests and original workspace **before** terminal acceptance or further host actions.
4. `batch.run_batch` rejects fresh batch initialization if any planned Run or native host evidence exists without its state file. Requires manual reconciliation of any orphaned production artifacts.
5. Resume no longer blindly trusts a batch row marked `ACCEPTED`; it re-opens the original Run and checks current job binding, receipt digest, actual PNG SHA, linked critic receipt/result, and required hard QA gates.
6. A batch with two jobs using identical asset/edit specifications now binds each receipt's resulting file to the **specific job's production evidence directory**. Swapping their Run JSONs no longer passes even if all input spec digests match.
7. `batch status` now performs read-only plan/source/rights verification and accepted Run/PNG/QA proof checks. It returns a nonzero exit/status ERROR when the current bytes no longer justify an accepted state; it never invokes ImageGen or silently rewrites the batch.
8. No changes to the default subscription-only native image backend, existing rights licensing rules, project Master promotion or active Unity game tree. No paid API/local-model fallback added.

## Test-first evidence

- Started by adding `tests/test_v101_durability.py` with seven failing fault-injection cases on the unmodified implementation. All seven became green after code changes.
- Added accepted PNG missing/corruption and receipt tampering scenarios; they failed before the accepted evidence integrity fix, then passed.
- Added corrupt `status` reporting scenarios (missing PNG or changed rights); they failed before the read-only status fix, then passed.
- Added a same-spec two-job Run swap scenario; it failed before job-specific evidence directory binding, then passed.
- New module: 11 tests (plus subtests), all PASS; historical 178 tests remain in the full test suite.

### Final local regression (2026-10-19)

| Command | Result |
|---|---|
| `python3 scripts/validate_project.py` | PASS — 6 TOML examples |
| `python3 -m unittest discover -s tests -q` | **PASS — 189 tests, exit 0** |
| `python3 scripts/demo_e2e.py` | PASS — offline host-protocol dry-run |
| `git diff --check` | PASS |
| `./bin/ai-3dgame-image-harness version` | `0.10.1-dev` |
| Mac Git worktree | clean, on `feat/v0.10-steam-commercial-production` |

The full unit suite intentionally prints `ERROR: real mark-generated requires --packet, --receipt, and --host-attestation` from a rejection test. The suite itself returns `189 tests ... OK`, exit 0. This is not an unhandled test failure.

## Known limits, blockers and next P0 task

- Atomic replacement and fsync of file data reduce partial JSON risk, but this does **not** provide a transaction across external model calls, receipt files and journal updates. Interrupted native calls with uncertain side effects still require manual reconciliation; automatic regeneration is forbidden.
- The local accepted evidence checker validates bytes/receipt/QA/job binding only. Independent *native provenance* is still required from `production-audit` before Unity staging. No cryptographic proof of the actual model identity is provided by a copy transcript.
- This v0.10.1 iteration ran **no new real native ImageGen** and **no Unity import or Player build**. Existing historical v0.9 LAMP/RADIO and three real Unity screenshots remain separate prior evidence. Do not count mock images as new production throughput.
- No commercial-quality certificate, complete game seven-category release proof, human rights/title signoff, accepted KNIFE_001 reference reconciliation or Steam platform approval has been obtained.
- Follow-on P0: run a controlled genuine multi-asset pilot with at least twelve licensed independent tasks; record first-pass/repair/blocked rates and output drift. Before claiming v0.13 or v1.0 quality, complete the staged true-image QA/AssetSpec v2 tasks in `V1_DEVELOPMENT_ROADMAP.md`.
- Existing live game whetstone selection failure is a separate Game/Test Harness blocker; this change does not repair Unity gameplay.

## Reproduction

```bash
cd /Users/qiguang/ai-3dgame-image-harness
git switch feat/v0.10-steam-commercial-production
python3 -m unittest discover -s tests -p test_v101_durability.py -v
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -q
python3 scripts/demo_e2e.py
git diff --check
```

All historical generated images, rights sources, Unity project contents and local host run evidence are private and must remain outside public Git. Never infer commercial legality, artistic acceptance, Steam approval or true model origin solely from SHA checks or a simulated test pass.
