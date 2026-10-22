# v0.13 audited native batch KPI candidate — D04/D08

**Engineering code candidate only. Real 12/30-job pilot and release acceptance remain BLOCKED.**

`batch-benchmark` is a read-only CLI that evaluates an existing v0.10
commercial batch manifest and its immutable state. It rechecks source-rights
SHA, original asset/edit contracts, production Run/Receipt/current pixels,
independent `production_audit` and duplicate identity/output evidence.
An `ACCEPTED` journal label or a manually written QA PASS alone NEVER
counts as a native production result.

## CLI

```bash
./bin/ai-3dgame-image-harness batch-benchmark \
 --workspace-root /absolute/private/workspace \
 --manifest /absolute/private/workspace/batch.json \
 --state /absolute/private/workspace/batch-state.json \
 --phase pilot --format json \
 --output /absolute/private/workspace/qa/pilot001.json
```

Choose `--phase pilot|candidate|rc`; output JSON or `--format markdown`
with a new `.md` path. Omit output to print on CLI only. Outputs are
exclusive new files, never overwrite existing records. Missing real data
returns exit 2 with `INSUFFICIENT_VERIFIED_REAL_PRODUCTION`.

## Observed sample targets (not claims of completion)

| Phase | Unique audited native result samples | Categories | First QA pass | Final QA pass |
| --- | ---: | ---: | ---: | ---: |
| pilot | >=12 | >=4 | measured only | measured only |
| candidate | >=30 | >=5 | >=75% | >=90% |
| rc | >=60 | >=6 | >=80% | >=95% |

Only independent native source PNGs with formal `production_audit=PASS`,
unique Run IDs, unique output hashes and distinct source asset/edit
contracts are valid independent successes. Collisions are rejected for
both records, independent of order. Started-but-failed tasks remain in the
first/final-pass denominators. Unstarted planned jobs are not image calls.
Observed rates include 95% Wilson confidence intervals, per-category
breakdown, repair/regeneration counts and sanitized failure reasons.

A scope-limited rate target never certifies user artwork, copyright,
Unity import/Player performance or Steam approval. Critical false-PASS
calibration and manual intervention rates stay NOT_VERIFIABLE without
their actual reviewer evidence. Every output keeps
`release_state=BLOCKED_PENDING_ART_UNITY_RIGHTS_STEAM`.

The two new LAMP/RADIO direct-native image runs from 2026-10-21 have real
PNG pixel/Mask evidence, but do NOT possess completed formal
`production_autopilot` Runs and independent `production_audit=PASS`.
They cannot be added to the 12/30 official batch numerators. LAMP's
brushed grain remains NOT_VERIFIABLE; both lack final human art signoff.

**Scope of this implementation:** D04 partial (audited KPIs) and D08
JSON/Markdown/CLI. The real 12→30→60 native sample campaigns,
fault-injection matrix, complete batch automation, human approvals,
isolated Unity Player, source-rights, and Steam review remain pending.
