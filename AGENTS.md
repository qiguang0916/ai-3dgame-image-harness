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
