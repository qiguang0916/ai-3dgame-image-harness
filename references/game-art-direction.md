# Professional Game Art Direction (v0.6)

This project selectively adopted the **workflow principles** of
`gamedev-skills/awesome-gamedev-agent-skills`, `create-game-assets`
(Apache-2.0), without copying third-party program source or requiring that Skill.

For a new image family, record:

- purpose / gameplay role: hero prop, concept, texture, sprite, UI image;
- approved visual direction, palette roles, materials, shape/readability;
- camera, projection, lighting, exposure, crop, background;
- in-game readability at intended displayed scale;
- what constitutes forbidden drift between asset variants.

The optional `[art_direction]` TOML is validated and becomes a named section
in the generated Host ImageGen brief and Action Packet. `must_match = true`
adds `art_direction.consistency` as a required visual Hard Gate. It still
requires real inspection: a field's presence does not prove artistic quality.

`Create Game Assets` calls the installed host `imagegen` where available;
this Harness likewise delegates only to the official OpenAI/Codex host. No
additional API, local image model or permanent plugin installation is needed.

Source: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/tree/main/skills/disciplines/create-game-assets
License: Apache-2.0 (project upstream). See `ACKNOWLEDGEMENTS.md`.
