# Acknowledgements

ai-3dgame-image-harness is an original implementation.

The design was informed by public workflow ideas from:

## waterblower/Omni-Art-Skills

Relevant ideas studied:

- explicit art-direction responsibility;
- reference images with declared purposes;
- production planning separated from visual review;
- generated-image quality gates.

The inspected Skill files identify themselves as MIT licensed.

Repository:
https://github.com/waterblower/Omni-Art-Skills

## ybuild-ai/ai-game-art-pipeline-skill

Relevant ideas studied:

- provider-neutral game-art workflows;
- choose the pipeline by runtime job;
- do not treat raw AI output as a finished production asset;
- QA as part of the pipeline.

The project declares an MIT license.

Repository:
https://github.com/ybuild-ai/ai-game-art-pipeline-skill

## Implementation note

No upstream source file is vendored into this repository. The ai-3dgame-image-harness control model, TOML contracts, validation logic, game-asset locks, delta-edit routing, and KNIFE_001 example are independently implemented for this project.

## v0.6 art-direction research

The v0.6 production-brief principles were informed by the open-source
[Create Game Assets](https://github.com/gamedev-skills/awesome-gamedev-agent-skills/tree/main/skills/disciplines/create-game-assets)
Skill (Apache-2.0). Its source code was **not copied or vendored**. The
art-direction contract and image QA checks in this repository are written
independently for the existing OpenAI-native Harness.
