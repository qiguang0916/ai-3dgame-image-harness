# v0.9 — Native ImageGen Autopilot & Steam QA Bridge: verified acceptance

## Execution environment

- Mac host: Apple Silicon, authenticated `Codex CLI 0.163.0-alpha.10.2` using **ChatGPT login**, not `OPENAI_API_KEY`.
- The native `image_gen.imagegen` tool was successfully invoked through `codex exec` in an isolated temporary workspace.
- Selected output is matched by SHA-256 to an actual PNG under `$CODEX_HOME/generated_images/...`; the Codex JSONL transcript contains a successful native-copy command. This is **not** cryptographic model identity attestation, and the CLI may omit separate image tool events.
- No direct Images API, third-party paid gateway, ComfyUI or local image-generation model used.

## Real Host ImageGen results

| Asset | Source | Native ImageGen attempts | Visual QA | Final state | Notes |
|---|---|---:|---|---|---|
| LAMP_001 | Existing approved v0.5 master | **1** | 16/16 hard gates, `PASS_WITH_NOTES` | **ACCEPTED** | Three brass base screw heads now silver; slight non-target texture change |
| RADIO_001 | Existing approved v0.5 master | **2** | First: `REPAIR_MINOR`; second: `PASS_WITH_NOTES` | **ACCEPTED** | First red knob faces retained brass sidewalls; second native edit repaired sidewalls, same structure |

**LAMP:** Real output 1312×1199 PNG; result SHA starts `b61c3814f49a1969e22a`; receipt starts `3da467414479a353`. A separate read-only Codex visual critic inspected the source and output. The Harness accepted the real receipt and hard-gate QA.

**RADIO:** Real output 1536×1024 PNG; first run entered `REPAIR_READY` automatically. A **separate CLI invocation with `--resume`** performed a new built-in ImageGen edit, fresh receipt, independent QA and final `ACCEPTED` without overwriting the first result. Final receipt starts `93435d52c04173ee`; result SHA starts `6b1eb80926581ef5b3`. One minor repair, zero major regenerations.

Input PNGs, generated outputs, per-attempt packet/receipt/host JSONL, QA TOML, delivery manifests and all raw private evidence are kept **locally outside public Git**. The approved historical Master files are unchanged.

### Pixel-preservation A/B (same original sources)

Using v0.6's report-only approximate target rectangles and a maximum-channel pixel delta threshold of 15:

| Asset | Historical v0.5 outside-target changed fraction | New v0.9 outside-target changed fraction |
|---|---:|---:|
| LAMP_001 | 2.26015% | **2.54787%** |
| RADIO_001 | 13.94734% | **15.95313%** |

**These two real v0.9 samples show slightly MORE out-of-zone pixel variation than historical v0.5**; do not claim that the new Prompt Compiler has improved image fidelity. Changes include harmless lighting/texture variation, but exact region preservation is not proven. The purpose of the v0.9 test is to verify a real autonomous generator/critic/repair lifecycle, not to prove a superior image model. More controlled runs and calibrated region masks are required.

## Unity QA / Steam release bridge

- Isolated clone of independent `ai-3dgame-test-harness`: **61/61 self-tests PASS**. These are control-plane tests, **not** a live Unity Player game pass.
- New image Harness `unity-proof` checks original `ai-3dgame-test-harness` seven-category same-commit evidence and actual screenshot/commit/hash binding; missing/forged Unity PASS is rejected.
- Existing KNIFE_001 v030E GLB: named 7 mesh objects and four source-bound geometric views passed their **limited** validation, but materials, hidden tang shape and approved visual reference fidelity are not proven.
- All nine latest historical KNIFE_001 v2 reference PNGs were located on the Mac (Chinese filenames); their existence and SHA were checked. These are **design reference evidence**, not permission to silently promote a later model revision.
- The main Second Life Workshop Unity repository has **existing uncommitted modifications**; it was not modified or rebuilt in place.
- Rights approval, production visual/PBR acceptance and actual Unity Player seven-category game release evidence are missing for the target asset; the **Steam commercial gate correctly remains BLOCKED**.

## Automated and CI tests

- **168/168 Python tests PASS** (original v0.8 + v0.9 Autopilot + Unity release bridge).
- Manifest schema validation **PASS**.
- Legacy host protocol E2E dry-run **PASS**.
- Codex Skill Creator validation **PASS**.
- Git diff check **PASS**.
- Independent `ai-3dgame-test-harness` Node suite **61/61 PASS**.
- GitHub CI: check final PR actions separately after push.

The offline mock tests cover: bootstrap first Master, edit+resume, repair and regenerate routing, source tampering, invalid visual QA, leaked-secret prevention, partial evidence conflict, native copy SHA consistency, and release evidence provenance. The two real ImageGen runs are **in addition to** these synthetic tests, not part of a CI test matrix.

## Outstanding v1.0 commercial release gates

1. Run the new Host ImageGen/QA runner repeatedly against fresh real tasks and diverse asset styles; measure first-pass pass rate, QA false-accepts, changed regions, and recovery behavior (two real runs are insufficient for stable-production certification).
2. Complete KNIFE_001 current-reference authority reconciliation, PBR/geometry acceptance and multi-view hidden-interface validation; never infer Full Tang from a side silhouette alone.
3. Produce a protected or isolated Unity build of the actual game, collect genuine macOS Unity Player captures with the independent game-test Harness; fix all game physics/input/paper-cut/visual/performance failures for the same exact game commit.
4. Obtain explicit human rights/source review and the applicable Steam AI-content disclosure; Steam's own final review is external.
5. Only after all these gates pass may a candidate asset be marked ready for Steam submission review. **No v1.0 Steam-commercial-quality certification is claimed by v0.9.**

### Useful commands

```bash
./bin/ai-3dgame-image-harness autopilot run --asset <asset.toml> --edit <edit.toml> --workspace-root <workspace> --run <run.json> --max-actions 8
./bin/ai-3dgame-image-harness autopilot run --asset <asset.toml> --edit <edit.toml> --workspace-root <workspace> --run <run.json> --resume
./bin/ai-3dgame-image-harness autopilot status --run <run.json>
./bin/ai-3dgame-image-harness unity-proof --manifest <game-release-evidence.json> --commit <40-hex-git-commit> --output <proof.json>
./bin/ai-3dgame-image-harness commercial-gate --manifest <commercial-package.json> --output <QA-report.json>
```

## Additional end-to-end verification (2026-10-18, continued delivery)

**Read-only RADIO native production audit:** `production-audit` independently
rechecked the actual `ACCEPTED` run: **two** ImageGen calls, **two** visual QA
reports, both SHA-bound native `generated_images` source PNGs, receipt/event
transcripts, current Master and final image. **PASS, zero integrity errors**.
Its result is an integrity PASS, **not** a commercial quality PASS.

**Actual Unity Player built-in screenshots:** `SecondLifeWorkshop-0.2.0.app`
ran with its existing `-inspectHtmlQaCapture` flag and wrote **three genuine
Unity-engine PNGs** — sharpening HUD, A face inspection, B face inspection.
Each is 2880×1800 pixels. The Unity log contains real A/B screenshot markers
and `MINIMUM_LOOP_READY`. This works without the external macOS Screen
Recording/Accessibility privileges that blocked an earlier OS-level screenshot.
The new `player-capture --verify-existing` rehashes screenshots, application
executable and actual engine log. **Capture integrity PASS**; independent
seven-category Unity release QA and commercial gates remain **BLOCKED**.

**Private evidence persistence:** original LAMP/RADIO host workspaces, A/B QA,
native event logs and the Unity Player capture were copied without edits to
an ignored, private, checksum-indexed directory
`$HOME/ai-3dgame-image-harness/.ai-3dgame-image-harness/e2e-v09-preserved-20261018/`
(54 files, 16.53 MiB). Original run JSONs retain their original absolute paths;
the copy is a historical **audit snapshot, not a relocatable resumable run**.

**Cannot yet claim Steam-grade delivery:** the current KNIFE_001 model lacks
a user-accepted PBR/geometry/multiview visual signoff; the real Unity game
still has uncommitted development changes; OS-input/physics/paper-cut/performance/
non-development same-commit seven-gate evidence is not complete; human rights
review and Steam AI-use disclosure remain needed. Passing host receipts or a
Unity screenshot by itself does NOT upgrade commercial release status.


## Additional blocked live Unity Player test

An opt-in native Player QA run used `-whetstoneSelectionProof` on the same
SecondLifeWorkshop 0.2.0 build. The application reported `WHETSTONE_PLAYER_SCREEN
1440x900`, then **`Player stone selection rejected`**, and exited with
**status 1** before producing stone-variant screenshots. This is a real
**BLOCKED** game-interaction test, NOT a passing physics/asset-selection claim.

The gameplay selection method may reject while loading, disabled or flipping;
the exact triggering condition requires an isolated game-project debug run.
The user's dirty Unity development workspace was left unchanged. The game
test-harness must resolve this failure independently before seven-category
release acceptance.

## Durable native source preservation

The private E2E snapshot also contains **three separate SHA-matched copies
of original Codex generated_images sources** (LAMP 1, RADIO 2), plus
`NATIVE_SOURCES_INDEX.json`. This protects forensic evidence if the Codex
image cache is later pruned; copied paths do not make historical run state
relocatable or independently attest a model identity.
