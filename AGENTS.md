# Repository operating contract

This repository is an Agent Skill / lightweight image-production harness, not an image model.

## Principles

- Keep the core backend-neutral.
- Do not require ComfyUI, CUDA, local diffusion weights, or a local GPU.
- Do not add a direct OpenAI API client merely to duplicate the host's official imagegen capability.
- When an OpenAI/Codex host provides `$imagegen`, delegate generation/editing to the built-in path.
- Never auto-switch to API/CLI fallback or require an API key for normal host-native execution.
- Real runs perform reference preflight by default. `--dry-run` is explicit and only for fixtures/examples.
- Approved reference state, reference sufficiency, topology, and required hard gates are deterministic contracts.
- Do not promote inferred/provisional structure into authoritative facts.
- Never claim Visual QA passed without inspecting the actual generated image.
- Missing/failed/unverifiable required hard gates prevent acceptance.
- Host/backend failures must be persisted through `mark-blocked`; do not hand-edit run JSON.
- Real generation must bind the current packet, input digests, result digest, and host attestation in an execution receipt before QA.
- Real QA must bind the current receipt/result digest; do not reuse a report across iterations.
- Master candidates require explicit pixel QA and immutable promotion; never auto-promote or overwrite a Master.
- Repair/regeneration loops must remain bounded.
- Keep root `SKILL.md` concise; put heavy protocol detail in `references/`.

## Runtime separation

Deterministic scripts may validate inputs, compile briefs, persist state, enforce QA completeness, and route outcomes.

Deterministic scripts must not pretend to visually inspect images or call an image model.

The Agent/host must invoke the real image tool, inspect real output pixels, and write the visual QA judgment.

## Validation before reporting completion

Run after the final code change:

~~~bash
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -v
python3 scripts/demo_e2e.py
~~~

If adding a contract field, reason code, or state transition, update validator/state-machine tests.

## v0.6 and naming

- Canonical name: AI 3D Game Image Harness (`ai-3dgame-image-harness`).
- Legacy `.game-image/` evidence must remain untouched and ignored.
- Bootstrap manifests may only create images; production editing still requires approved references.
- First-Master registration must verify source Run, Receipt, real-pixel QA and candidate lineage, not just a declared `approved` JSON.
- Enforced region/technical-output QA must recompute real pixels; a handwritten PASS is not sufficient.
- Do not confuse generated QA fixture images, local differential metrics or the self-declared Host attestation with independent real-model production evidence.

## v0.7 — prompt and reference controls

- Keep `[prompt_intelligence]` opt-in; old v0.6 TOML prompts are unchanged.
- Reference review emits SHA-bound *questions* and palette swatches, not local
  semantic vision. Codex host must inspect actual image pixels before asserting
  `inspected_pixels = true`; the hash cannot certify truth.
- Role overlap requires an explicit authoritative reference; do not silently
  rank two geometry or material masters.
- Count/camera preflight conflicts must BLOCK, not be suppressed by a style
  preset. Unstructured natural-language contradictions still require review.
- The real-run manifest/edit schema hash prevents silent mid-run prompt changes.
- During repair apply only failed delta corrections; do not restart a style
  library or replace the approved edit target.

## Steam-grade v0.8 readiness rule

- Use the approved model or Master for structural authority; four Blender
  clay views have a shared GLB hash but are NOT automatically production
  textures, a new Master, or proof of a correct hidden Full Tang.
- A Unity Player build ID and actual screenshot digest are mandatory for
  in-game shipping evidence. No hand-written `PASS` without bound files.
- Store capsules require current Steam sizes and content review; store
  screenshots must be genuine gameplay at >=1920x1080, 16:9.
- Rights and Steam AI disclosure must be documented. Legal/Steam approval
  is external, and a SHA cannot prove ownership or aesthetic quality.
- Never merge to main or claim fully automatic commercial-ready Steam art
  until real OpenAI Host ImageGen/Unity round trips are independently accepted.

## Native game-harness release bridge

- v0.9 `unity_release_bridge.py` imports only immutable, seven-category,
  same-commit evidence from `ai-3dgame-test-harness`. It neither launches
  Unity nor rewrites any user project.
- A fake `Unity PASS` review is insufficient. Require original release
  manifest SHA, artifact URIs with matching SHA-256, an actual Unity Player
  screenshot and game build commit. Do not claim rights/Steam approval.

## v0.9 additional evidence hardening

- Never treat a test stub or forged model-origin statement as a native
  OpenAI image generation. `production-audit` requires actual,
  traceable Codex-native source PNG, receipt and event transcript hashes.
- Unity `player-capture` obtains three game-authored frames; an OS-level
  screenshot permission grant is not required. Use an empty output
  directory and stop the Player after capture, without modifying Unity
  source. A PASS in this utility proves screenshot collection only.
- Full commercial release remains BLOCKED without independent, same-commit
  game-test Harness verification across all categories, human source rights,
  game-scale visual approval and applicable Steam disclosures.

## v0.10 — Commercial batch workflow

- Enforce human rights-review records + SHA bindings + commercial license allowlist before any native model work. Hashes do not prove real rights.
- Never rerun ambiguous/partial Host calls or overwrite accepted work. Bound job and action counts, maintain immutable batch plan and sources across resumes.
- No API/local-model fallback: authenticated Codex built-in ImageGen only.
- Unity staging copies original audited PNG bytes without editing the active game project; independent Unity seven-category QA, visual review, Steam disclosure and Valve approval remain external.


## v0.11 optional AssetSpec v2

- Old schema_version=1 asset/edit TOMLs and packets remain unchanged unless edit.asset_spec_v2 is explicitly present.
- V2 categories have typed use/size/alpha/colorspace; image generation does NOT automatically satisfy the technical output or art/QA gates.
- Duplicate approved reference roles must resolve to one specific selected authoritative Master; Style Kit text may not override identity/geometry/camera/hard-preserve locks or invent unseen components.
- Style Kit canonical SHA binds the project palette and art direction; changing it after a Run begins requires a fresh Run, never a silent resume.
- A concept reference or Steam marketing image is not an in-game Unity 2D asset; Unity staging rejects v2 intended_use != ingame.
- Asset scaffold output is draft TOML with no ImageGen provenance, no rights signoff, and no Steam/Unity acceptance.
- An explicitly pinned batch.style_kit_sha256 is a fail-closed cross-job contract; no v2 kit or mismatched SHA must block before the first native Host image action.
