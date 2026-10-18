# Backend Integration

ai-3dgame-image-harness is a control layer, not a model provider.

## Capability detection

Before execution, determine whether the current environment supports:

- text-to-image generation;
- image editing from an existing target;
- multiple reference images;
- masks or region selection;
- image inspection/vision after generation.

Use the strongest available path without making the repository depend on it.

## Preferred path for edits

If image editing is available:

1. use the approved current image as the edit target;
2. attach only necessary masters;
3. declare each reference role;
4. send the delta brief;
5. inspect the returned image;
6. run Visual QA.

Avoid replacing a local edit with fresh text-to-image unless the edit path is unavailable or the image has already failed major gates.

## OpenAI / ChatGPT environments

When the runtime exposes a native OpenAI/ChatGPT image generation or editing capability, use that native capability as the execution backend.

The core Skill should not require API keys, SDKs, or local model installation merely to operate inside an environment that already provides image tools.

If an API adapter is later added, keep credentials and billing outside the core skill.

## Graceful degradation

If the backend supports only one input image:

- select the highest-priority reference for the critical role;
- fold secondary constraints into the text brief;
- report that multi-reference control was reduced.

If the backend cannot inspect generated output:

- do not claim QA PASS;
- return BLOCKED for visual acceptance.
