# v0.12 real archived ImageGen precision A/B pilot — 2026-10-21

**Status: OBJECTIVE_PIXEL_QA_VERIFIED / MASK_REVIEW_PENDING / ART_SIGNOFF_PENDING / NOT UNITY OR STEAM CERTIFIED.**

This document contains sanitized measurements and cryptographic source hashes only.
The real private PNGs, trial binary masks, native Codex receipts/events, visual
previews and locally-generated image QA heatmaps have **NOT** been uploaded to
GitHub. All historical source PNGs and run evidence remain immutable.

## Provenance and scope

- Inputs: historical v0.9 genuine Codex-native ImageGen **LAMP_001**
  (one generation) and **RADIO_001** (final output after repair), as backed up
  in the 2026-10-18 private read-only archive. Original v0.9 native receipts,
  independent QA and SHA inventory already existed.
- Both archived source/result SHA-256 values were independently rehashed and
  exactly match the v0.9 archive index. RGB dimensions and ICC metadata also
  match on each pair; LAMP is 1312×1199, RADIO is 1536×1024.
- This is a **real-image precision-composition pilot** using existing historical
  model output. It is NOT a new v0.12 ImageGen invocation, new native-generation
  benchmark, multi-attempt image-quality reliability study or artist acceptance.
- v0.12 `precision-compose` generated new candidate PNGs and SHA-bound reports.
  `precision-report` independently rechecked decoded source, raw, composed
  and mask pixels, exported difference/ROI/seam heatmaps, and required
  original, raw, composed, mask and contract digests. A follow-up verifier
  additionally validated matching `precision-compose` report digests.
- The masks are **proposed, not user-approved**. Their review and authoritative
  ROI selection remain mandatory before declaring strict final edit quality.

## Two genuinely observed runs of the compositor

| Item | v001 historical rectangular ROI trial | v002 focused part-level ellipse mask trial |
| --- | --- | --- |
| LAMP_001 | Objective lock PASS; **visual FAIL:** left brass screw remained brass | Objective lock PASS; visually all three screws appear silver |
| RADIO_001 | Objective lock PASS; **visual FAIL:** knobs half brass/half red | Objective lock PASS; visually two full deep-red knobs |
| Protected pixels outside declared edit area | 0 modified | 0 modified |
| Real v0.12 ImageGen model invocations | 0 | 0 |
| Source artwork / native output overwritten | None | None |
| Human artistic signoff | Not obtained | Not obtained |

These failures show that pixel equality alone can yield a false positive for
the semantic target when an ROI clips required components. The smaller,
separate-part masks were deliberately drafted to cover all three existing lamp
screw heads and both entire radio knobs, with no broad changes to body,
background, grille or hardware. Visual observations are preliminary; neither
candidate is promoted to an approved Master.

## Actual numeric A/B evidence — v002 refined candidates

| Metric | LAMP_001 | RADIO_001 |
| --- | ---: | ---: |
| Historical v0.9 outside change (old approximate ROI, threshold 15) | 2.54787% | 15.95313% |
| Raw v0.9 change outside **v002 focused ROI** (threshold 15) | 2.35417% | 14.51927% |
| v0.12 candidate change outside **v002 focused ROI** | **0%** | **0%** |
| Locked region mismatches (exact bytes) | 0 | 0 |
| Candidate-source mismatches within editable pixels | 0 | 0 |
| Changed editable pixels | 7,223 | 34,926 |
| Max additional RGB boundary-gradient jump, v001 → v002 | 67 → 30 | 231 → 27 |
| Mean additional RGB boundary gradient, v002 | 1.6832 | 5.0235 |
| Quantitative report state | MEASURED_NEEDS_VISUAL_REVIEW | MEASURED_NEEDS_VISUAL_REVIEW |

The historical and new-ROI outside-change rates have **different denominators
and region boundaries**. Never describe 2.54787%→2.35417% or
15.95313%→14.51927% as a direct performance improvement. The within-v002
raw-versus-composited comparison with the exact same ROI is valid for the strict
pixel-preservation claim. No quantitative seam metric is an art PASS by itself.

### SHA evidence

| Binding | LAMP_001 | RADIO_001 |
| --- | --- | --- |
| Approved historical source | `ae91896b0dcf9edff201e78d93b0c64bced4ec122d407486342be926ca82f182` | `443ee73d48ce9c28a453b3ba3fccba3ff03564f04774370f78886e7d7a87f604` |
| Native raw v0.9 source | `b61c3814f49a1969e22a7fa7a74f8b8cb040f824bfcb1776c92bb0ebcadb710b` | `6b1eb80926581ef5b3c9d4b0b3bcc1cbee1f6b59dfe63b524bf53467177f69af` |
| v002 trial mask | `82a6b86744f293c5a464affc55ca2e133bbb49fc273005b166171bcd137180aa` | `53b73bdae0819d029213140f4888017da1115413ddc095634219a024a805685e` |
| v002 composite | `0b451d74ac71eb352e721208421c6483c24bb81ad4de3cb8dccdde7fd921c6ca` | `65fe1d55a22d38b3010fb4534457656741287b99d8e693cd3a7c7c36086a16dc` |
| Composition report SHA | `093bd60e7a6dce5a673bc7f4bd73a1339cd730a3b322d39fffb1deb4728c83e7` | `8a9aa613bee304c7cfefec4d03c1eb05055fb22eda3b78140c639f4648996fd5` |

## Art QA and risks

The local visual crop comparison showed the original rectangle masks did not
cover entire required components. The focused ellipse candidates appear to
restore the intended materials to every required visible part without obvious
large-scale unrelated restyling. Final seams/halos, exact object alignment,
geometry integrity and material plausibility need independent artist review
at source resolution (not only a small JPEG preview). The `precision-report`
state remains `MEASURED_NEEDS_VISUAL_REVIEW`.

No authorized reviewer has approved these masks as the final area contract.
The experiment deliberately preserved the historical native input SHA and
never replaced or reapproved a Master. It also does not prove hidden structure,
PBR physical accuracy, legality, Steam policy acceptance or Unity rendering.

## How to reproduce without leaking data

- Local isolated code worktree based on GitHub `feat/v0.12-quality-metrics`.
- Private read-only archive: project-ignored `.ai-3dgame-image-harness/e2e-v09-preserved-20261018/`.
- Private separate A/B trials (not in Git): `ai_bridge/v12-private-ab-20261021-v001/`
  and `ai_bridge/v12-private-ab-20261021-v002/`. Do not copy to public Git.
- Confirm source, candidate, mask and composited PNG SHA, inspect
  `precision-compose-report.json`, `quality-bound.json` and same-case heatmaps.
- Do not overwrite trial paths. Every new candidate needs its own unique
  sequence/suffix and review record.
- Run `python3 -m unittest discover -s tests -q`,
  `python3 scripts/validate_project.py`, `python3 scripts/demo_e2e.py`,
  and compare current GitHub CI.

## Still-blocking P0 gates

1. Approve final authority and component-level source-geometry ROI/masks with
   documented reviewer, version and digest.
2. Get independent **full-resolution** art QA (seams, highlights, identity,
   knobs/screws count and component shape), log failures and calibrate automated
   critic false acceptance against human labels.
3. Repeat controlled A/B tests with **fresh distinct native ImageGen outputs**
   and consistent signed regions. Report denominators and failed trials too.
4. Continue KNIFE_001 Master reconciliation, 12→30 true batch production,
   Unity actual import/Player proof, rights and Steam review separately.

**Do not close Issue #13 or merge PR #11/#12 on the strength of this pilot.**
