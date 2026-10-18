# v0.6 Professional Game Asset Production — spec / plan / tasks

## Goal

Rename `game-image` to `ai-3dgame-image-harness` and improve first-Master
production, precision of OpenAI image edits, visual reference sufficiency,
art-direction quality and deliverable PNG consistency **without replacing
OpenAI's built-in ImageGen or increasing local model complexity**.

## Immutable rules

- Preserve the earlier v0.5 receipt/QA/approved-Master state machine.
- Synthetic PNG fixtures are unit tests, not proof of real ImageGen generation.
- The Host must inspect actual pixels; local tools may measure pixel differences.
- Original local E2E binaries remain ignored/untouched; no secret or local user
  game asset enters public Git.
- No automatic API, paid SDK, CLI fallback or local diffusion engine.

## Implementation tasks

1. [x] Rename public GitHub repository and create separate v0.6 Mac workspace.
2. [x] Add bootstrap first-Master create → candidate → QA → approve → active manifest.
3. [x] Add optional region contract + objective outside-change metrics and heatmap.
4. [x] Bind deterministic region/technical-output gates into real auditable apply-qa.
5. [x] Add opt-in visual reference evidence role-review gate.
6. [x] Adopt lightweight Create Game Assets style-guide principles via art brief.
7. [x] Add technical PNG dimensions/transparency validation.
8. [x] Add one CLI and maintain existing legacy run-directory compatibility.
9. [x] Run saved LAMP/RADIO baseline measurement and synthetic defect tests.
10. [ ] Real v0.6 Host ImageGen A/B: same task with and without new art/region brief.
11. [ ] Real structural REGENERATE_MAJOR and real complex KNIFE_001 verification.
12. [ ] Independent new-session forward review and publish/merge decision.

## Release criteria

All automated tests green **plus** real built-in ImageGen acceptance,
independent visual evidence for complex structures, no critical security/gate
bypass and observed improvement in at least one defined quality criterion.
Without the final real-host gates, remain `BETA / BLOCKED_FOR_V1.0`.
