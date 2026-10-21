# v0.12 fresh Codex-native ImageGen: 2-asset pilot (2026-10-21)

**State: OBJECTIVE_PIXEL_PASS (2/2), INDEPENDENT MODEL VISUAL QA PASS (1/2), RELEASE BLOCKED.**

This is a sanitized report only. Original source PNGs, newly generated native PNGs, composited PNGs, Host JSONL, review images, approval records and quality reports remain on the user's Mac, outside the public Git repository. This pilot **does not satisfy** the v0.13 minimum 12/30 production or v1.0 commercial gate.

## Evidence and controls

- Both assets used actual approved source PNGs and the owner-approved v002 binary ROI masks, with source, Mask and user decision SHA verified.
- Each new native generation was limited to **one** Codex built-in image generation request, using ChatGPT subscription auth, no paid API, local model or other provider fallback.
- LAMP: isolated direct Codex attempt-v003 after prior v001/v002 failures. It completed and copied the genuine PNG from a Codex `generated_images` source, validated against the original source with successful `cp` and `cmp` in Codex JSONL and matching SHA.
- RADIO: isolated direct Codex attempt-v001. A new native source PNG appeared in the corresponding `generated_images/<thread>` folder, but Codex's attempt to copy it into the working directory was denied by the local approval policy. After the Codex turn completed, it was **recovered without a second ImageGen invocation**, the source/thread path and byte SHA were verified. It is not a structured tool-level attestation.
- Codex CLI did not expose structured `image_generation_call` events in the JSONL for either case. Source evidence rests on Codex's generated_images folder, thread binding, original-source copy or recovered SHA, and original events; it is not cryptographic model identity proof.
- Independently SHA-bound new PNG `precision-compose` output and `precision-report` quality inspection were run for each new asset, using the same approved v002 ROI Mask and owner decision receipt.
- Independent, no-ImageGen Codex visual review saw three images each (approved Master, native raw, protected composite), with six specific visual gates per asset.

## Quantitative results

| Evidence | LAMP_001 | RADIO_001 |
| --- | ---: | ---: |
| Approved Master SHA | `ae91896b0dcf9edff201e78d93b0c64bced4ec122d407486342be926ca82f182` | `443ee73d48ce9c28a453b3ba3fccba3ff03564f04774370f78886e7d7a87f604` |
| Native PNG SHA | `46d5f42448465357ccb96364ecce0fab8bbbf0ec5f50071513ce5224207c47dd` | `3e359a56267190c96e693d7b2f5fefa8c974bd8c6e7050d204913bc10f943336` |
| Protected composite SHA | `112de3dc4558340522adaf6d4ca4c24881f719f2bc409edb19b622c05c24e6a8` | `b7a5996148ef522e86892ebf279782e9b6866a058e774d1095f6626ce4e33d9f` |
| Pixel objective gate | PASS | PASS |
| Protected pixel mismatches | 0 | 0 |
| Edited pixel-source mismatches | 0 | 0 |
| Changed target pixels | 7,220 | 34,891 |
| Raw native non-target change, threshold 15 (matched case ROI) | 2.11936% | 7.98834% |
| Composited non-target change, same ROI | 0% | 0% |
| Max RGB seam excess | 20 | 16 |
| Independent model visual QA | BLOCKED (5/6 gates PASS) | PASS (6/6 gates PASS) |
| Human final art signoff | PENDING | PENDING |
| Unity Player proof | NOT VERIFIED | NOT VERIFIED |
| Rights / Steam release | BLOCKED | BLOCKED |

## Visual outcomes and failure handling

LAMP: Three silver-colored screw heads, slots, positions, silhouette, background and seam quality visually passed the separate Codex reviewer, but the **fine brushed-steel directional grain could not be verified at available scale**. The reviewer explicitly marked `material_edit_all_three=NOT_VERIFIABLE`, overall `BLOCKED`. Do not automatically upgrade to PASS.

RADIO: Two full red enamel knobs, count, face/side ridges, silhouette and crop, grille/handle/tuning details and seam artifacts all passed the six-gate independent Codex visual review. This is **model visual QA PASS, not independent human release signoff**.

The previous LAMP direct attempt-v002 failed due to a Python-child network sandbox denial. Its process was confirmed ended without a PNG or ImageGen call event. The original Harness run remains BLOCKED and untouched. Do not conflate failed attempts with successful new-image production denominators.

## Audit report

The private final audit was written at:

`/Users/qiguang/ai_bridge/v12-native-approved-pilot-20261021-v001/FRESH_NATIVE_TWO_ASSET_PILOT_20261021.json`

SHA-256: `5354d79bdad1c7e5944423fb26d2871eb3b754d8970f2169396889fce11deb59`

It cross-checks both assets' raw Master/Mask/Codex source SHA, user ROI approval, composite, numeric quality, and independent Codex reviewer JSON. State: **`release=BLOCKED`**.

## Next gates

1. LAMP full-resolution independent material reviewer must determine if brushed-steel texture satisfies the requested finish. If not, repair only in a **new versioned attempt**, never the accepted source, and re-run pixel/visual QA.
2. Perform human source-resolution signoff for both LAMP and RADIO on geometry, materials, seams and image quality; do not infer legal authority from hashes.
3. Expand from 2 new authentic images to v0.13 controlled 12→30 independent tasks only after v0.12 real QA gates close. Record every failed attempt and source/CI evidence.
4. Verify KNIFE_001 authority and Unity Editor/Player actual delivery separately.

## Second machine review at source-pixel detail (2026-10-21)

The LAMP material exception was independently re-examined using a nine-cell
contact sheet: approved Master/native ImageGen/strict composite for all three
screws, with actual 110×96 source-pixel crops enlarged using nearest-neighbor.
This was a **new visual reviewer only**: no native ImageGen regeneration or
source changes.

Review JSON state: **`NOT_VERIFIABLE`**. The three screw faces are visibly
cold-silver with realistic sheen, but the actual source pixels do not reveal
distinct fine directional brushed grain. Slot highlights and tonal variation
are not sufficient evidence of brushed steel texture. This is **not** a
technical pixel failure and is **not** permission to alter the accepted Mask;
it is a material acceptance gap.

Private evidence: `LAMP_001/direct-native-attempt-v003/LAMP_V003_PIXEL_1TO1_MATERIAL_REVIEW.png`
SHA `af404404b742b92a3a8330dd7e9feb6f991812858bff637ad831ba842f7bf0d3`,
and its `independent-material-zoom-qa.json`. Both remain Mac-only.

Disposition: LAMP `MATERIAL_BRUSHED_GRAIN_NOT_VERIFIABLE`; retain
`BLOCKED` on full machine-art acceptance. RADIO remains machine visual
`PASS`. An optional future repair must be a separately budgeted, new
native attempt with SHA-bound source and protected Mask, with **no**
alteration of the historical v003 evidence and no unfounded art signoff.
