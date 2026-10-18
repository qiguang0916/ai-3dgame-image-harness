# v0.8 — Steam-Ready Commercial Art Evidence Gates

**Long-term objective:** single-person + AI game art production capable of unattended iterations and reliable, commercially usable Steam game assets. v0.8 is a **quality/evidence gate milestone**, not a declaration that this objective has been reached.

## Distinguish product stages

- **ImageGen concept/reference:** useful for designing but not automatically a shipping texture, mesh or Steam screenshot.
- **Unity game asset:** a mesh/texture with consistent approved geometry, valid rights, proven import/runtime visuals and a reproducible QA record.
- **Steam store art:** capsule/library art meeting current Steam dimensions and content rules, subject to final Steam review.
- **Steam gameplay screenshot:** an **actual gameplay capture**; never substitute AI concept art or a Blender beauty render.

Source: https://partner.steamgames.com/doc/store/assets (official dimensions), https://partner.steamgames.com/doc/store/assets/rules (capsule copy rules), https://partner.steamgames.com/doc/gettingstarted/contentsurvey (AI-use Content Survey).

## Production workflow

1. **Asset Intent** — distinguish concept, in-game prop, UI image, textures, marketing or gameplay capture. Specify game camera, native resolution, expected detail density, source rights.
2. **Approved Master** — collect approved reference images or an approved 3D source; keep SHA-bound structural contracts. No guessed hidden geometry.
3. **Host OpenAI ImageGen** — generate/edit via Codex/ChatGPT built-in ImageGen; bind real prompt+references+result receipt, never paid API fallback by default.
4. **Objective image QA** — inspect actual output dimensions, transparency, editable/protected pixels, cropped silhouette; block on impossible or unverified gates.
5. **Independent visual QA** — compare actual pixels and reference, count required components, assess material response/style/game-scale readability; route REPAIR/REGENERATE or BLOCKED with bounded budgets.
6. **3D canonical reference** — for a source GLB, run `render-views` (Blender Workbench geometry views) and `canonical-qa`. All views must be tied to one unchanged GLB SHA, show content, cover sufficient frame area, and pass named-mesh count tests. These are **candidate geometry baselines**, not user-approved Masters or PBR lookdev.
7. **Unity runtime proof** — use `ai-3dgame-test-harness` or an equivalent verifiable player/editor QA pass to capture actual Unity Player screenshots, build ID, integration report and hashes. Photoshop/composite or Blender screenshots cannot masquerade as runtime captures.
8. **Commercial/Steam gate** — `commercial-gate` checks file hashes, ownership evidence, visual QA, optional four-view GLB proof, Unity Player integration, Steam image dimensions and content review evidence.
9. **Candidate release** — pass means `READY_FOR_STEAM_SUBMISSION_REVIEW`, **not** that Valve has accepted the asset or that legal/commercial rights were independently proven.
10. **Policy check** — for AI-generated content that ships with the game, prepare accurate Steam Content Survey disclosure as required. Steam rules and review decisions remain external.

## One command interface

```bash
# Deterministic Blender orthographic geometry baselines (no AI image model)
./bin/ai-3dgame-image-harness render-views \
  --source /path/to/KNIFE_001_v030E.glb \
  --output-dir /new/empty/reference-evidence-folder

# Validate the generated image digests, distinct views and visible subject regions
./bin/ai-3dgame-image-harness canonical-qa \
  --manifest /reference-evidence-folder/manifest.json

# Commercial-package evidence review
./bin/ai-3dgame-image-harness commercial-gate \
  --manifest /package-folder/commercial-package.json \
  --output /package-folder/commercial-gate-report.json
```

A real commercial package has `asset_kind`: `ingame_3d_model`, `ingame_2d_asset`, `steam_store_capsule`, or `steam_gameplay_screenshot`; `concept_reference` is explicitly **REFERENCE_ONLY** and cannot be certified as shipping-ready.

All source/image evidence files should remain outside public Git unless specifically authorized to share. The readiness manifest binds SHA256 and reviewer-provided evidence; programmatic checks alone cannot prove visual truth, originality, or legal rights.

## Current Steam image requirements

Store header 920×430, small 462×174, main 1232×706, vertical 748×896; library capsule 600×900, library hero 3840×1240. Store screenshots: minimum 1920×1080, 16:9, actual gameplay images. These sizes were checked against Steamworks as of 2026-10-18 and must be rechecked before publishing.

## Automated refusal rules

- No adequate approved Master or geometry source → BLOCKED.
- Missing/invalid GLB components, empty canonical views or source-hash mismatch → BLOCKED.
- ImageGen cannot execute in current host → BLOCKED; never silently switch to a paid API or local AI model.
- Required QA failed/not visually verifiable → bounded repair/regenerate or BLOCKED.
- No signed-off source rights, provenance, Unity Player proof, Steam art copy/size review → BLOCKED.
- Game concept image submitted as Steam gameplay screenshot → BLOCKED.
- Missing/unsupported Steam AI-content disclosure or platform policy validation → manual release hold.

## Roadmap to full production readiness

**P0 (v0.8; current):** trustworthy geometry-view baseline and Steam commercial evidence gate, with QA reports and tests.

**P1 (v0.9):** execute actual Host ImageGen without manual command copying, from approved Master through receipt, QA, localized repair, topology regen and resumed jobs; measure first-pass yield, edit drift and QA false accept rate on LAMP/RADIO/KNIFE.

**P2 (v0.9):** connect `ai-3dgame-test-harness` Unity Editor/Player integration reports and device build screenshots to release evidence, including resolution and platform checks.

**P3 (v1.0 candidate):** repeated end-to-end runs, independent artist/game-scale review, license/AI usage records, Steam store compliance, reproducible evidence and bounded failure handling. Publish only after genuine pass criteria are satisfied; a policy or license uncertainty cannot be “auto-approved” by invented metadata.

The goal is automated execution with fail-closed escalation for human-owned legal/final approvals; absolute zero-human legally guaranteed Steam publication is not technically credible.
