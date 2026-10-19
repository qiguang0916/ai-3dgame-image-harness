# v0.12 Phase 1 — SHA-locked exact region preservation

**Status:** CODE_VALIDATED_IN_GITHUB_CI / ART_VISUAL_QA_PENDING / NOT_UNITY_OR_STEAM_CERTIFIED. This is a deterministic post-edit safety tool, **not** a new image model, visual acceptance, commercial certification, or replacement Master. Base is v0.11 development branch `feat/v0.11-asset-contract` after the successful audited native E2E.

## Problem and contract

In v0.9 real ImageGen edits, LAMP_001 and RADIO_001 had measured changes outside approximate target rectangles (~2.55% and ~15.95% respectively at the existing pixel threshold). Those changes can include harmless lighting/texture variation but are incompatible with strict untouched-region requirements for a game hero prop.

`precision-compose` now creates a **new candidate PNG**. Only pixels within declared editable rectangles **AND** not marked protected in a same-size binary PNG mask may come from the ImageGen candidate. All other pixels are copied from the immutable approved source.

- No target changes or no editable pixels → BLOCKED.
- Source/candidate differ in dimensions, RGB/RGBA mode or ICC profile → BLOCKED/NOT_COMPARABLE, never fake pixel alignment.
- Mask must be 8-bit grayscale PNG, same width/height as source, **only values 0 (editable) or 255 (locked)**; no grayscale feathering is assumed.
- Exactly the source PNG SHA and mask PNG SHA must match the explicit `[region_contract.strict_mask]` bindings. Files and generated outputs must stay within `workspace_root`, including after resolving symlinks.
- Mode must be `enforce`, with real, bounded `[[region_contract.targets]]`. Existing v0.6/v0.11 contracts without `strict_mask` remain compatible.
- Any output path collision or pre-existing output/report refuses overwrite. An interrupted output requires **manual reconciliation** before retrying.
- The compositor does not invoke Codex/ImageGen/API, auto-promote a Master, or set any QA approval flag.
- Pixel equality outside edit boundaries is objective; visible seam quality, lighting response, shape consistency, material authenticity and game-scale readability require **independent visual review**. Recorded boundary pixel change counts are diagnostic data, **not a seam PASS**.

## Input schema

Add to an existing valid local-edit request (the edit and all images are still inside the current workspace):

```toml
[region_contract]
mode = "enforce"
pixel_threshold = 0
max_outside_changed_fraction = 0.0

[[region_contract.targets]]
id = "approved-edit-area"
bbox = [0.30, 0.76, 0.70, 0.99]

[region_contract.strict_mask]
path = "masks/protect.png"
sha256 = "<actual 64-hex SHA256 of binary protection mask>"
reference_sha256 = "<actual 64-hex SHA256 of approved source PNG>"
```

The mask is a separate *protection* contract, not an implicit segmentation prediction. A draft mask from AI must be reviewed and explicitly approved for the asset. For strict invariants, source and candidate must already be pixel-aligned; this tool intentionally does not warp or resample the subject.

## Usage

```bash
./bin/ai-3dgame-image-harness precision-compose \
  --workspace-root /absolute/workspace \
  --edit /absolute/workspace/edit.toml \
  --reference /absolute/workspace/approved-master.png \
  --candidate /absolute/workspace/generated.png \
  --output /absolute/workspace/candidates/strict-v001.png \
  --report /absolute/workspace/qa/strict-v001.json
```

Report state: **`CANDIDATE_NEEDS_VISUAL_REVIEW`** with complete ROI contract SHA plus source/candidate/mask/output SHA, target pixel changes, outside mismatch count (must be zero), protected mismatch count (must be zero), measured boundary changes and explicit `visual_seam_review_required=true`. `commercial_release_certified=false` and `steam_approved=false`.

Candidate provenance is a **separate gate**: for real production use, verify the input candidate came from an auditable native ImageGen Run with `production-audit`; a locally constructed image by itself is not native image origin proof. Do not stage into Unity or Steam before independent QA, approved source rights and appropriate runtime tests.

## Verification scope

- New synthetic regression cases cover exact outside-ROI protection, protected pixel inside editable ROI, hash pinning, image dimensions/mode, binary mask validation, no-op changes, fully protected targets, non-overwrite, path traversal/symlinks and schema constraints.
- The v0.12 test suite uses deliberately synthetic 12x12 PNGs and a separate full CLI fixture. It proves **pixel algorithm behavior only**, not advanced art quality or real model fidelity.
- Historical real LAMP/RADIO input and output PNGs remain read-only in the private v0.9 evidence archive. Any new A/B benchmark must use fresh, separately named private output paths, indicate whether ROI is merely approximate or artist-reviewed, and never upgrade history to a new approved Master.

## GitHub remote validation (2026-10-19)

- Branch: `feat/v0.12-precision-region`, base: v0.11 code + successful independent native ImageGen smoke.
- GitHub PR: [#11](https://github.com/qiguang0916/ai-3dgame-image-harness/pull/11), retained as Draft until real-image seam QA.
- GitHub Actions run [39261468001](https://github.com/qiguang0916/ai-3dgame-image-harness/actions/runs/39261468001): **SUCCESS**. 224 Python tests PASS; schema validation PASS; legacy host-protocol dry-run PASS.
- CLI-level regression explicitly tests full valid TOML, SHA-bound ROI report, no overwrite on repeated invocation, and compatibility with v0.6 edit manifests.
- The original Mac worktree branch also contained a local first implementation and 11 passing tests before its Desktop Commander monthly tool quota was exhausted. Remote GitHub edits were then applied to the remote branch. **Mac worktree has not been synchronized to this remote branch since that quota block**; preserve its uncommitted code when eventually reconciling.
- No real historical LAMP/RADIO PNG A/B was executed in this phase because the private Mac files were no longer reachable. Reports of numerical 0 outside-target mismatches refer to synthetic fixture tests, not a passed visual fidelity benchmark. Do not fabricate private evidence or mark C09 complete.

## Remaining v0.12 tasks

C01 real approved source/ROI/mask benchmark samples and independent annotated failure labels; C03 multi-threshold quality/SSIM/palette metrics; C04 seam-aware blending option without weakening strict masks; C05 independent geometry/material visual acceptance; C06 false-positive audit; C07 bounded repair improvements; C08 actual texture technical output; C09 controlled real A/B comparisons. These remain **uncompleted** and must be validated with evidence, not inferred from synthetic image tests.

Full normal regressions:

```bash
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -q
python3 scripts/demo_e2e.py
git diff --check
```
