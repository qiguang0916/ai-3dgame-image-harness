---
name: ai-3dgame-image-harness
description: Use when creating a first game-art Master, editing or repairing game image assets through official OpenAI built-in imagegen, preserving approved references and protected regions, and verifying topology, art direction and PNG quality with auditable QA.
---

# AI 3D Game Image Harness

This is a professional game image-production contract and QA harness, not a drawing model. OpenAI/Codex built-in `$imagegen` performs all real generation and AI editing. No local generation model, automatic API/CLI fallback, or API key is required.

## Workflow selection

- **First Master:** `status="bootstrap"` + `operation="create"`; auditable ImageGen → actual-pixel QA → candidate → immutable approved image → `master register-first`. See `references/first-master.md`.
- **Existing approved Master:** declare reference roles, select the correct image edit target, compile a delta-only brief and preserve hard gates.
- **Local precision:** optional `[region_contract]` declares editable and protected boxes, measured after generation. `enforce` re-checks actual pixel diffs at `apply-qa`. See `references/region-quality.md`.
- **Structural tasks:** declare required component counts and visible relations, and explicit unknown details. Optional `reference_evidence` keeps visual role claims reviewable.
- **Art direction:** optional `[art_direction]` specifies style, palette, materials, lighting, camera and game-scale legibility. See `references/game-art-direction.md`.
- **Technical game asset:** optional PNG dimensions and transparency checks. See `references/technical-output.md`.

## Non-negotiables

- Approved references are role-specific authorities. Candidate, draft and rejected references are never production inputs.
- The issued Host Action Packet controls exactly what the image model receives.
- Real runs require preflight, input/output digests, execution receipt, and Host attestation; attestation does not establish proprietary model identity.
- Host must inspect real pixels; required hard gates cannot be missing or marked PASS without evidence. Deterministic region/output checks independently re-read pixels and reject fabricated PASS.
- Local defect → REPAIR, required topology failure → REGENERATE, unverifiable evidence/backend → BLOCKED.
- Repair/regeneration passes are bounded. Never silently weaken rules or switch to paid API/CLI/local generation.
- Do not treat synthetic fixtures or dry-run as real ImageGen E2E.

## Host loop

For an explicitly authorized unattended native Codex run, use
`python3 scripts/cli.py autopilot run --asset <asset.toml> --edit <edit.toml> --workspace-root <workspace> --run <workspace/run.json>`.
Use `--resume` for existing state and `autopilot status --run <run.json>` to inspect it.
This subscription-only driver blocks on unverifiable native provenance, critic
failure or partial evidence; it never promotes a Master. Read
`docs/V09_ACCEPTANCE.md` for evidence limits and reconciliation behavior.

`./bin/ai-3dgame-image-harness doctor` → `validate` → `init` → `next` → **host-native ImageGen** → `generated` (receipt) → actual-pixel QA → `qa` (apply) → deliver/repair/regenerate/block.

For first Master, finalize the independent QA promotion before registering an active manifest.

Read on demand:
`references/runtime-preflight.md`, `references/reference-evidence-review.md`, `references/topology-contract.md`, `references/host-action-protocol.md`, `references/execution-receipt.md`, `references/visual-qa-contract.md`, `references/master-lifecycle.md`, `references/openai-imagegen-delegation.md`.

## Verification

```bash
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -v
python3 scripts/demo_e2e.py
```

Additional reference-selection policy: `references/reference-sufficiency.md`.
Failure persistence: `references/host-failure-protocol.md`.

## v0.7 — optional intelligent reference and prompt preparation

For tasks with many references, uncertain hidden details or difficult style
consistency, read `references/v07-prompt-intelligence.md`.
Use `styles` to choose a small game-art preset, and `reference-review` to
create a SHA-bound **host visual inspection request**. The Host must actually
inspect pixels and supply visible facts/unknowns; local code does not recognize
objects or infer dimensions. Run `prompt-check` before `init`.
`prompt_intelligence` is opt-in, with approved Master and hard locks always
above style inspiration. Never substitute gallery prompts for an approved
reference; no extra API or local generation engine.

## v0.8 — Steam commercial release candidate gates

When preparing final game/Steam assets, read `docs/V08_COMMERCIAL_TARGET.md`
and `docs/V08_ACCEPTANCE.md`. For GLB 3D sources use optional Blender
`render-views` (read-only geometry reference; NOT AI drawing) then
`canonical-qa`. Run `commercial-gate` on an evidence-bound package manifest
to require actual image/glb hashes, source rights review, visual QA,
Unity Player runtime capture and, for store graphics, current Steam
dimensions/copy rules. An unreviewed concept picture or Blender reference
may **never** be presented as real Steam gameplay. A PASS means ready for
Steam submission review, not Steam-approved; unresolved evidence must BLOCK.

## Unity release evidence bridge

Do not invent Unity or Steam approvals. Before an in-game asset may ship,
obtain independent `ai-3dgame-test-harness` evidence for seven same-commit
release categories. Read `docs/V09_UNITY_RELEASE_BRIDGE.md` and run
`unity-proof` (read-only) to check raw file:// evidence SHA-256 and native
Player screenshot binding. Missing/failing evidence must keep
`commercial-gate` BLOCKED, even when model GLB views and image QA pass.

## v0.9 — real host delivery and Player evidence

For an actual Codex ChatGPT-subscription ImageGen production run, use
`autopilot run` / `--resume`; see `docs/V09_ACCEPTANCE.md`. The host uses
the authorized native Codex ImageGen only, with no OpenAI API key fallback.
Use `production-audit` to rehash every native generation, receipt and
critic record; a fabricated synthetic stub may not pass this integrity
gate. For a real game image, use `player-capture` on an existing Unity
Player app where the opt-in `-inspectHtmlQaCapture` feature exists, and
`--verify-existing` to detect later PNG/log/executable changes. It does not
replace independent seven-category `unity-proof` or Steam release review.
