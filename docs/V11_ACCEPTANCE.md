# v0.11 — AssetSpec v2 / Reference Authority / Frozen Style Kit

Date: 2026-10-19 (America/Los_Angeles).
Parent: v0.10.1-dev at commit bec08e3.
Development branch: feat/v0.11-asset-contract.
Status: CODE_VALIDATED_LOCALLY; GITHUB_CI_PENDING; NO_NEW_REAL_IMAGEGEN_OR_UNITY_PROOF; NOT_STEAM_CERTIFIED.

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

Local results after final code changes: validator **10/10 TOML files PASS**, unit suite **207 tests PASS**, E2E **DRY RUN PASS**, `git diff --check` **PASS**, CLI `0.11.0-dev`. This verifies code contracts, not actual model image quality. GitHub CI outcome is tracked separately after push.

## 5. Remaining v0.11 release gates

- **B03 prompt intelligence**: current improvement compiles structured output category/style/authorities into original Host prompt; comprehensive alternative decomposition/selection based on real visual A/B is not independently proven.
- **B06 KNIFE_001**: Original approved v030E geometry and latest design references can differ. Current v030E GLB/four clay views do not prove hidden tang/PBR/Unity appearance, and image model cannot promote nine other references to a Master. Human reference authority reconciliation and real visual QA are **BLOCKED**; no new production Master is declared here.
- **v0.11 real visual sample**: new style kits and category outputs have **not yet been tested on actual Codex ImageGen images**. Therefore this version is code-level development rather than production art-quality acceptance.
- **v0.13/v0.14/v1.0 gates**: multi-asset live benchmark, independent visual QA, Unity Editor/Player import, seven-category same-commit release proof, actual source license signoff, Steam disclosures and Valve review remain external/uncompleted.

### Independence policy

A successful CLI `asset-spec inspect` or synthetic `StubHost` ACCEPTED run certifies only schema/state machine operation. It must never be presented as independently verified image aesthetics, human rights/title, real model identity, fully automatic Steam readiness or Unity Player validation.
