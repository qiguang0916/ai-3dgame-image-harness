# v0.7 — Implementation Plan

Goal: improve pre-generation game image accuracy with **reference authority, concise visual facts, selected game style and conflict checks**, keeping the existing OpenAI Host ImageGen / Receipt / Visual QA workflow.

## Tasks

- [x] Strict optional `prompt_intelligence` schema and six original style profiles.
- [x] Opt-in automatic profile choice on `create` only.
- [x] Real-input Host reference review packet with SHA256, dimensions, pixel color swatches and inspection questions.
- [x] Digest-bound, Host-inspected visible facts and explicitly unknown geometry.
- [x] Explicit authority for overlapping roles; component-count/camera-lock conflict checks.
- [x] `styles`, `reference-review`, `prompt-check` CLI commands.
- [x] Digest-bound asset/edit spec for real runs, rejecting mid-run prompt changes.
- [x] Minimal repair prompts preserve passed gates and role authority without style reload.
- [x] Unit tests and offline LAMP/RADIO prompt A/B; KNIFE contract static check.
- [ ] Live OpenAI ImageGen A/B with LAMP and RADIO, independent QA.
- [ ] Real KNIFE_001 multiview/master completeness and regeneration validation.

Maintain v0.6 compatibility and avoid extra paid API clients, local models, or wholesale external prompt-library installations. Merge only after review; do not claim improved pixel quality without live visual A/B.
