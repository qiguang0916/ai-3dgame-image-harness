# v0.6 Acceptance Evidence (updated when verified)

Evidence must be separated into: code tests; measured historical image
results; real new Host ImageGen runs. A GitHub green CI **does not** certify
game-art quality.

## Historical baseline available locally (source v0.5)

The original `$HOME/game-image/.game-image/e2e-v05/` contains
LAMP_001 (ACCEPTED, 1 generation), RADIO_001 (REPAIR_MINOR then ACCEPTED,
2 iterations), radio-negative (BLOCKED), receipts, PNGs and Master promotions.
These are not shipped into GitHub.

## New v0.6 image difference baseline

With approximate, report-only rectangular target regions and RGB/RGBA
per-channel difference threshold of 15:

- LAMP_001: changed-fraction **outside** the approximate screw box = 0.0226015.
- RADIO_001: changed-fraction **outside** the approximate two-knob box = 0.1394734.

Both cases are `INFO` (measured changes, not automatically judged defects).
Images and heatmaps remain **local, ignored, and out of Git**.

These values establish a measurement baseline, **not** a proven gain in
OpenAI model success rate. Region boxes are approximations, not expert
pixel masks.

## Verified / unverified

- Code-level bootstrap & approval: covered by synthetic unit E2E only.
- Code-level region report and non-bypass: covered by synthetic unit integration.
- Game art brief / reference evidence / technical output: covered by unit tests.
- New real Host $imagegen generate/edit on v0.6: **NOT VERIFIED YET**.
- Real REGENERATE_MAJOR: **NOT VERIFIED YET**.
- Complex KNIFE_001 pixel QA: **NOT VERIFIED**; example TOML lacks actual
  reference PNGs in its own directory.

No real game-image v1.0 or commercial-quality certification is claimed.
