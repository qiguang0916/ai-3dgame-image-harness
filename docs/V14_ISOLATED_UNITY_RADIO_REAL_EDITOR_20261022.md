# v0.14 — isolated Unity 6 RADIO textured-image acceptance pilot

**Observed 2026-10-22 UTC. Engineering stage: real Unity Editor import/render PASS; real Player runtime capture BLOCKED.** This is deliberately not an assertion of 3D game integration, performance certification, art rights or Steam readiness.

## Context and exact scope

The v0.13 privately approved-for-ROI-only RADIO PNG has real native ImageGen→deterministic enamel finish→Mask composite→Visual QA→`production-audit=PASS` evidence. Its final source SHA-256 is

`a8f6c83d5759cdc17681ec04ee6034b1a3dd46748718b3322d48ad0f44c9d83c`.

It is a full RADIO 2D reference image—not a rigged, modeled or materialized 3D radio. The isolated Unity test places the **actual imported PNG** on a quad in a standalone single-scene project. It does not touch the `Second Life Workshop` Unity tree, approved Masters, the existing dirty Image Harness worktrees or any user's Unity game build.

Unity 6.6.3f1 Editor / Apple Silicon was actually callable by the authorized Mac bridge. Its Unity Personal license was available. A *new isolated project* was created and the private PNG staged after a fresh read-only native production audit PASS and byte-for-byte SHA match.

## Real failures and fix (do not erase failed case)

- **v001**: real Unity Editor source texture import/build succeeded, but the actual Editor scene screenshot contained only the background (incorrect Quad-facing test setup). This was **NOT** accepted as a visual PASS. The original evidence is retained privately.
- **v002**: recomputed the Quad front-facing orientation from actual Mesh normals and camera direction, requiring facing dot-product above 0.95. Added a hard Editor screenshot non-background content threshold. New Editor screenshot contains the visible RADIO in the correct left-right orientation and exact original geometry/layout, measured independently against the original private PNG.

## Genuine v002 observed evidence

| Real signal | Observed result |
| --- | --- |
| Unity version | `6000.6.3f1` |
| macOS architecture / Editor graphics | arm64, Apple M4 Pro |
| Original production-audit | `PASS`, source SHA `a8f6c83d5759...` |
| Actual Unity TextureImporter | Default uncompressed sRGB RGB, no mipmaps, readable; 1536×1024 |
| Editor generated asset GUID | `14768271f282040cf9b13e3638b0b6fa` |
| Unity Editor script pixel-content sample count | 8,967 nonbackground cells |
| Quad world normal vs camera dot product | 1.0 |
| Real Editor RenderTexture capture | 1280×800 PNG, SHA-256 `571262a983c46928e5e62a3dace19ef295402db27bc1d1b6d9c0643f6f6a4dbb` |
| Independent nonbackground fraction | 50.2409% |
| Actual content bounding box `xyxy` | [169,86,1111,714] |
| Source-orientation pixel mean absolute RGB error | 2.56475 / 255 |
| Horizontally mirrored source error | 32.11355 / 255 |
| Vertically flipped source error | 36.64874 / 255 |
| Editor build action | **Succeeded** |
| Build mode | reported non-development |
| Build artifact | standalone private macOS `.app`, with actual Info.plist and executable |
| Player launch and Player frame capture | **BLOCKED** (authorized `dc_bridge` command policy rejects arbitrary Player executable) |
| Actual Player FPS / GPU frame time / memory | **NOT VERIFIED** |
| In-game 3D radio/Second Life Workshop scene integration | **NOT TESTED** |

Original Unity logs identify the exact screenshot path and screenshot SHA plus `HARNESS_V14_EDITOR_IMPORT_DONE <SHA> Succeeded`; the independent verifier checks these markers, hashes the actual private source screenshot and import report, checks that the compiled-input C# matches the versioned repository, validates the macOS .app structure and compares all rendered pixels against the same original RADIO PNG.

The Editor's empty v001 screenshot could **not** pass these checks. A mirrored/random/unrelated/blank preview also fails. This shows a genuine nonempty Editor image render, not a Player frame or game physics proof.

## Reproduction on a permitted Mac (do not run against the game project)

1. Create a fresh named Unity 6.6.3f1 sandbox with the standard Editor `-batchmode -nographics -quit -createProject <fresh_project>` call.
2. Run `python3 scripts/v14_unity_radio_prepare.py --project <fresh_project> --run <private_AUDITED_run.json> --expected-sha <64_digit_result_sha>`. This **refuses any nonempty/other named project**, re-audits the original real native image and copies the versioned Unity C# and the pinned private PNG only to the fresh sandbox. It does not launch Unity or call a model.
3. Launch actual Unity Editor with `-batchmode -quit -projectPath <fresh_project> -executeMethod HarnessV14RadioEditor.Execute -harnessV14ExpectedSha <sha> -harnessV14OutputDir <new_private_evidence_dir> -logFile <new_editor_log>`. Do **not** pass `-nographics` for real graphics-device capture.
4. Run `python3 scripts/v14_unity_radio_verify.py --project <fresh_project> --evidence <new_private_evidence_dir> --run <private_AUDITED_run.json> --expected-sha <sha> --editor-log <new_editor_log> --output <new_private_verdict.json>`. The verifier checks the real production Run again, source SHA, Unity C# hashes, imported GUID/dimensions, Editor screenshot content and non-mirrored appearance, exact Editor log markers, and physical .app/Info.plist.
5. The **built Player must still be launched and genuinely screen-captured** in an approved GUI/execution environment before the Player gate can be set to PASS. Never infer it from Editor screenshot, file existence, log strings or a synthetic capture. Current `dc_bridge` explicitly rejects launching the .app by path; do not bypass that restriction.

All evidence outputs are new-only; no copied private RADIO PNG, Host transcripts, Editor screenshot or Unity Player .app is committed publicly. The C# files under `unity/v14_isolated_radio/Assets/` are reusable reviewable test source, not private gameplay data. The prepared stage is a purpose-built QA project only; never interpret its CPU/frame timing scripts as verified performance until an actual Player run succeeds.

## Remaining release gates

Real Editor textured-image import/render (this scope): **PASS**.

Real Player screenshot, input, non-development runtime evidence and performance: **BLOCKED**. The standalone non-development build's existence alone does not close the gate.

RADIO independent accountable human art decision and source commercial rights: **NOT VERIFIED**. LAMP brushed steel and KNIFE_001 authority remain unresolved. Steam AI/source disclosures, 12→30→60 independently rights-reviewed native batch tasks, and actual 3D game integration remain **BLOCKED**. **Commercial release certified = FALSE.**

No `main` merge or change to the real game worktree is authorized or performed. Keep draft PRs open pending explicit review.

