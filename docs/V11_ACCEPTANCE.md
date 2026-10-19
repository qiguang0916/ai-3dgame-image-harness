# v0.11 — AssetSpec v2 / Reference Authority / Frozen Style Kit

Date: 2026-10-19 (America/Los_Angeles).
Parent: v0.10.1-dev at commit bec08e3.
Development branch: feat/v0.11-asset-contract.
Status: CODE_VALIDATED / NATIVE_IMAGEGEN_SMOKE_ACCEPTED_AND_PRODUCTION_AUDIT_PASS / NOT STEAM CERTIFIED.

## 1. New design contract (opt-in)

New `[asset_spec_v2]` TOML table is **nested inside an existing schema_version=1 edit_request**. This is deliberate backward compatibility: old manifests, Host packets, receipts and historical runs remain unchanged when v2 is absent. The accepted `contract_version=2` has the following typed fields:

- `category`: concept_prop, background, ui_icon, sprite, vfx_sheet, texture_candidate, steam_capsule.
- `intended_use`: reference for concept_prop; marketing for steam_capsule; ingame for background/ui_icon/sprite/vfx_sheet/texture_candidate.
- `expected_size`: bounded WxH pixels; must match the existing `[output].expected_size`. Native ImageGen is not guaranteed to return that size; existing technical output QA must enforce it.
- `alpha_mode`: required/forbidden/optional. UI icon, sprite and VFX sheet require alpha; backgrounds, Steam capsule art and texture candidates forbid alpha. Must not contradict the existing `[output].require_transparency`.
- `color_space`: sRGB for authored RGB images; texture candidate basecolor is sRGB, normal/roughness/metallic/mask are linear data textures. This is metadata/intent, not proof of physically correct PBR.
- `quality_tier`: draft or production_candidate. No value means legal, player or Valve approval.
- `texture_channel`: mandatory only when category=texture_candidate.
- `required_roles` + `[asset_spec_v2.authority]`: explicit selected approved Master binding for reference identity/geometry/material/camera etc. Overlapping selected roles cannot infer priorities and must have a specific approved reference. Unknown/unselected or nonapproved references fail. Existing prompt_intelligence.role_authority cannot conflict.

Optional `[asset_spec_v2.style_kit]` contains an original project-wide design language: ID, palette (hex), lighting, material language, edge language, game-scale readability, negative constraints and sha256. SHA is canonical JSON of the kit excluding the sha256 field. It detects any edited text/palette and keeps multiple assets on a measurable frozen style definition. It does not certify copyright or style aesthetic correctness.

Legacy `prompt_intelligence.style_profile` must be none when an independent v2 Style Kit is provided, avoiding implicit contradictory style sources.

## 2. Runtime integration

- `validate_project.py`: validates typed schema on all edit TOMLs, and checks source-to-role authority in cross_validate.
- `compile_brief.py`: injects category, intended use, dimensions, color/alpha, role authority, hash-bound style hints and no-invented-geometry priority.
- `compile_repair.py`: references the already-pinned style ID/SHA; instructs local repair without a full artwork restyle.
- `next_action.py`: inserts canonical `asset_spec_v2` and Style Kit SHA into the regular native action packet, automatically covered by packet digest/receipt hashing.
- `topology_contract.py`: opt-in hard gates art_v2.category_intent and art_v2.style_consistency; required visible QA cannot be skipped or declared PASS without independent actual image inspection.
- Existing `execution_loop`, `production_autopilot` and `batch` keep their original Host ImageGen backend and input-spec SHA binding; changing edit/style after initializing an auditable Run invalidates the next packet.
- `batch_production.stage_unity`: refuses v2 concept/marketing assets, rather than pretending any ACCEPTED PNG is in-game Unity texture.
- `batch_production.make_plan`: optional top-level `style_kit_sha256` locks every job in the same production batch to one identical SHA-verified v2 Style Kit before calling ImageGen. Old batches without this field retain their prior behavior.
- `asset_spec_scaffold.py`: creates new draft bootstrap asset+edit TOMLs for all seven categories, under a fresh target directory without overwriting existing state; creates no rights statement, approved Master or ImageGen output.
- `cli.py`: `asset-spec inspect`, `asset-spec scaffold` and `asset-spec style-hash` entrypoints.

## 3. Commands

```bash
cd /Users/qiguang/ai-3dgame-image-harness
./bin/ai-3dgame-image-harness version
./bin/ai-3dgame-image-harness asset-spec scaffold \
  --category background --asset-id WORKSHOP_BG_001 \
  --out /absolute/new-workspace/background/
./bin/ai-3dgame-image-harness asset-spec scaffold \
  --category ui_icon --asset-id HUD_ICON_001 \
  --out /absolute/new-workspace/icon/
./bin/ai-3dgame-image-harness asset-spec inspect \
  --asset /absolute/new-workspace/background/asset.toml \
  --edit /absolute/new-workspace/background/create.toml
./bin/ai-3dgame-image-harness asset-spec style-hash --json <original-style-fields.json>
```

The scaffold output uses `draft`, not `commercially_approved`; must revise prompt and legal source records before real commercial batch work. Templates deliberately contain generic, original prompts without representing images, user-owned rights or a new knife Master.

Two validated public examples are `examples/V11_BACKGROUND_001` and `examples/V11_UI_ICON_001` (TOML only, no images).

## 4. What is actually verified

- Opt-in v2 typed constraints, seven category contracts, color/alpha conflicts and texture semantics.
- SHA mismatches, repeated palette values and unknown style fields fail closed; scope and role authority conflicts block.
- Native action packet and prompt inherit v2 style hash; repair is delta-only.
- Historical v0.6 image production packet remains without new v2 fields or hard gates.
- Source TOML changes after immutable auditable Run initialization reject the next packet.
- Synthetic-only byte staging test: concept_prop and steam_capsule cannot be staged as in-game 2D assets; original background ingame staging remains viable after mocked audit. This test is **not** proof of an actual Unity import or ImageGen source.
- One original source style SHA (same for background and icon examples) is used without overriding geometry and camera authority.
- Batch-level Style Kit SHA pin accepts a matching background+icon bundle, rejects absent/mismatching v2 style before any model call, and leaves legacy batches without a style pin unchanged.

### Regression commands

```bash
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -q
python3 scripts/demo_e2e.py
git diff --check
./bin/ai-3dgame-image-harness version
```

Initial v0.11 development commit 8c44a6c: 10 config docs, 207 Python tests, dry-run E2E and GitHub CI run 39255014047 all passed. Live-smoke-driven uncertainty regression requires final revalidation after this change.

## 5. Remaining v0.11 release gates

- **B03 prompt intelligence**: current improvement compiles structured output category/style/authorities into original Host prompt; comprehensive alternative decomposition/selection based on real visual A/B is not independently proven.
- **B06 KNIFE_001**: Original approved v030E geometry and latest design references can differ. Current v030E GLB/four clay views do not prove hidden tang/PBR/Unity appearance, and image model cannot promote nine other references to a Master. Human reference authority reconciliation and real visual QA are **BLOCKED**; no new production Master is declared here.
- **v0.11 live image test**: one actual Codex ImageGen asset was generated, but the independent critic returned BLOCKED. No new v0.11 production artwork has passed full Host QA; diverse real-run validation remains pending.
- **v0.13/v0.14/v1.0 gates**: multi-asset live benchmark, independent visual QA, Unity Editor/Player import, seven-category same-commit release proof, actual source license signoff, Steam disclosures and Valve review remain external/uncompleted.

### Independence policy

A successful CLI `asset-spec inspect` or synthetic `StubHost` ACCEPTED run certifies only schema/state machine operation. It must never be presented as independently verified image aesthetics, human rights/title, real model identity, fully automatic Steam readiness or Unity Player validation.

## 6. Real Codex ImageGen smoke and QA blocker (2026-10-19)

- Private path: HOME/ai-3dgame-image-harness/.ai-3dgame-image-harness/v11-native-smoke-20261019/ (private, ignored by Git).
- Auth: Codex login status reports Logged in using ChatGPT, not API key.
- Native action count: one real ImageGen generate plus one independent visual critic call; overall autopilot exit 2 / BLOCKED, no automatic retry.
- Generated original fictional lantern: PNG RGB 1536x1024, result SHA prefix 8b5fbd6a4327; SHA matches Receipt and Codex generated_images native source. Completed copy event and transcript hash verified; no distinct structured image model events were exposed, so model identity is NOT cryptographically attested.
- Critic issued a real QA TOML with four gates: identity PASS, image.technical_output NOT_VERIFIABLE, art_v2.category_intent PASS, art_v2.style_consistency PASS; overall QA BLOCKED because technical file inspection could not be confirmed.
- Previous technical gate verifier incorrectly rejected NOT_VERIFIABLE as unsupported even when deterministic image measurements passed, masking the existing critic record into a generic exception. New code allows a conservative unknown technical QA gate to correctly transition to BLOCKED and retain that report, while rejecting any false PASS against measured technical failure.
- Three offline regression tests added: measured PASS plus critic unknown -> BLOCKED; measured FAIL plus critic unknown -> no false PASS; unsupported statuses still refused.
- Re-evaluating the private saved QA in memory (without writing or repeating Host calls) yields BLOCKED / visual_inspection_unavailable with measured technical PASS. The original Run remains BLOCKED on disk.

This is a real native generation smoke and a successfully preserved failure, NOT completed native generation-to-visual-acceptance or Unity/Steam qualification. Use a separate fresh Run if conducting a future independent visual critic investigation.

## 7. Second isolated live production: CLOSED technical-QA blocker

Date: 2026-10-19. Code base used: feat/v0.11-asset-contract commit d67e9ae.
Private evidence: `$HOME/ai-3dgame-image-harness/.ai-3dgame-image-harness/v11-native-e2e-20261019-second/`.
No private generated images or original Host transcripts were added to public Git.

- Asset: WORKBENCH_STOOL_001, a fictional original workshop stool game-prop concept reference (no externally sourced images). The AssetSpec v2 scaffold was changed explicitly before the first run.
- Native Codex ImageGen executed **once**, then an independent visual QA review executed **once**, with max-actions=2. The final autopilot CLI exit is **0**, Run state is **ACCEPTED**, and the delivery record is present.
- Generated PNG: 1536x1024 RGB, SHA256 `51cfd0b2574de6917e4d1e217caecb1d83ec506b42f01dfa494fa0c0355366b1`. The result is bound to its input-spec SHA and Receipt; original Host event transcripts are locally preserved.
- Independent critic returned **PASS_WITH_NOTES**. All four actual required gates are PASS: `declared visible object identity`, `image.technical_output`, `art_v2.category_intent`, `art_v2.style_consistency`.
- Technical precheck: genuine original PNG, 1536x1024, alpha absent, SHA equal to candidate; deterministic check PASS was bound and supplied to critic without making subjective image quality claims.
- Independent `production-audit`: **PASS**, exactly 1 source PNG generation step, 1 QA step, 0 integrity failures; release_status=NOT_CERTIFIED and steam_approved=false.
- Initial BLOCKED lantern test from section 6 remains immutable and BLOCKED. Its separately issued diagnostic QA PASS did not rewrite the original historical Run. The latest success uses a completely fresh run/production directory.

**Interpretation:** native Codex ImageGen → receipt → independent visual QA → audited delivery **works for one new v0.11 item**. v0.11's code-level and single-item smoke acceptance can be recorded, but a single prop concept does not prove reliable large-batch game art, exact KNIFE_001 geometry, human source rights, Unity Player, Steam listing or v1.0 commercial-readiness. Real multi-category and A/B fidelity studies are pending v0.12/v0.13.
