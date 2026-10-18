# OpenAI Imagegen Delegation

This project treats OpenAI/Codex `imagegen` as an execution backend, not as logic that should be copied into ai-3dgame-image-harness.

Official source:
- https://github.com/openai/skills/blob/main/skills/.system/imagegen/SKILL.md

## Built-in-first policy

When the host has the official system imagegen skill:

- delegate normal generation and editing to `$imagegen`;
- prefer the host's built-in `image_gen` path;
- built-in mode does not require `OPENAI_API_KEY`;
- never switch to the fallback CLI merely because a built-in call fails;
- CLI/API fallback is explicit-only and may require an API key.

ai-3dgame-image-harness should not implement a shadow OpenAI API client just to reproduce behavior already owned by the official skill.

## Separation of responsibilities

ai-3dgame-image-harness owns:

- approved Master Reference selection;
- reference roles;
- geometry/material/camera locks;
- delta-only edit scope;
- run state;
- Visual QA gates;
- repair/regenerate routing.

imagegen owns:

- the actual image generation/edit call;
- current model/tool-specific execution behavior;
- built-in file handling policy;
- model-specific image controls exposed by the host.

## Prompt handoff

Pass the compiled ai-3dgame-image-harness brief as the authoritative visual specification.

Do not append a second competing art direction prompt.

For local edits, the most important handoff is:

- exact edit target;
- requested delta;
- HARD PRESERVE invariants;
- reference role mapping.

## Project-bound files

When the generated image belongs to a project, ensure the selected result is persisted into the project/workspace according to the host imagegen policy before marking the generation step complete.

The run state must point to the persisted selected result, not an ephemeral preview path.

## Future model changes

Do not hard-code a GPT Image model name in the core ai-3dgame-image-harness workflow.

The official imagegen layer should absorb model/version changes. ai-3dgame-image-harness stays focused on game-asset production constraints.
