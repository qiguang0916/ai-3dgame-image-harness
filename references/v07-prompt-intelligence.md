# v0.7 — Intelligent Prompt & Reference Control

Opt-in layer for the existing host-native OpenAI ImageGen. Absence of `[prompt_intelligence]` preserves v0.6 behavior. No additional AI API, CLI generation backend, or local model is installed.

## Capabilities

- Generate a **host vision reference-review request** from real approved PNG inputs, SHA256, image dimensions, declared roles, and raw-color swatch hints.
- Require explicit authority if two references both declare the same role (e.g., geometry, material).
- Reject conflicting explicit component counts and camera changes under a hard camera lock.
- Add short game-specific style guidance: six presets in `data/game-style-profiles.json`. `auto` chooses a profile for *create* operations only; existing-image edits default to no new style.
- Bind inspected-reference notes to the input PNG SHA256 at real preflight and bind parsed edit/manifest to the run before issuing a packet. A mid-run change requires a new run.
- Preserve delta-only repair prompts; never load a full style profile during localized repair.

## Host workflow

```bash
./bin/ai-3dgame-image-harness styles
./bin/ai-3dgame-image-harness reference-review --asset <asset.toml> --edit <edit.toml> --workspace-root <workspace>
```

The last command emits `action = host_vision_reference_review`; it **does not actually inspect objects**. Codex/ChatGPT Host must open and examine the real reference pixels, then populate a concise opt-in TOML section:

```toml
[prompt_intelligence]
mode = "guided"
style_profile = "none"
camera_change = false

[prompt_intelligence.role_authority]
geometry = "BLADE_SIDE_MASTER"
material = "ASSEMBLED_MASTER"

[[prompt_intelligence.observations]]
reference_id = "ASSEMBLED_MASTER"
source_sha256 = "<64 lowercase hex characters from reference-review>"
inspected_pixels = true
subject = "One fictional approved hero prop knife."
camera = "Approved three-quarter camera."
composition = "Single full knife, no crop."
visible_features = ["Three metal rivet heads", "Dark hardwood grip"]
materials = ["Metal", "Wood"]
palette = ["Cold silver gray", "Dark warm brown"]
unknowns = ["Hidden inner tang geometry not visible here."]

[[prompt_intelligence.count_requests]]
component_id = "rivet"
count = 3
```

The SHA placeholder must be replaced with the **actual source digest**. `count_requests` must match the approved manifest Topology and may be omitted if that component is not defined. `role_authority` must choose one **selected approved reference** for each role assigned to multiple bindings.

```bash
./bin/ai-3dgame-image-harness prompt-check --asset <asset.toml> --edit <edit.toml> --workspace-root <workspace>
```

A real check can report `VERIFIED_DIGEST_ONLY`: the host note is bound to a real file, but **the note's visual truth has not been proven by a hash**. Dry-run returns `NOT_VERIFIED_DRY_RUN`. Use official Host ImageGen through the existing `init → next → generated → visual_qa → qa` pipeline. A swatch histogram may represent background or lighting, not the subject material.

## Profile library

`studio_hero_prop`, `orthographic_model_sheet`, `workshop_background`, `game_ui_icon`, `game_sprite`, `pbr_texture_reference`. Styles must never override approved identity, geometry, camera, topology, or a user's delta edit.

Priority: **approved Master / hard locks → requested delta → visible evidence → optional style**. Unknown rear faces, precise thickness, interior or hidden interfaces must not be imagined as observed truth.

## Boundaries

Detection is deterministic for **structured** count/camera/role conflicts; unconstrained free-form natural language can still contain contradictory statements and must be reviewed by Host. No SDK parameters for GPT Image 2/2.5 are hardcoded because a Codex built-in host may expose different controls.

Research inspiration: freestylefly/awesome-gpt-image-2 (MIT), YouMind-OpenLab/ai-image-prompts-skill (MIT), wuyoscar/GPT-Image2-Skill (MIT), gamedev-skills/awesome-gamedev-agent-skills (Apache-2.0). No external code, copied gallery prompts or sample images were vendored. Media rights require separate review.

Real image quality improvements require actual controlled OpenAI ImageGen A/B; prompt improvements alone are not proof.
