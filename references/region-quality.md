# Localized Edit Region / Pixel Preservation Contract

An optional `[region_contract]` in the edit TOML records target and protected
image-space rectangles. All coordinates are **relative [0,1] to the original
image canvas**, `bbox = [left, top, right, bottom]`.

Example:

```toml
[region_contract]
mode = "enforce"          # or "report"
pixel_threshold = 15      # 0..255, maximum per-channel difference
max_outside_changed_fraction = 0.08

[[region_contract.targets]]
id = "three_screws"
bbox = [0.31, 0.75, 0.70, 0.97]

[[region_contract.protected]]
id = "shade"
bbox = [0.24, 0.08, 0.78, 0.52]
max_changed_fraction = 0.07
```

- `report`: measure first, never infer quality PASS from a metric. No hard gate.
- `enforce`: adds required `visual.region_preservation`; a measured violation
  cannot be converted to PASS by hand-written QA.
- Source/result must have equal dimensions for region checking. Mismatched
  dimensions are `NOT_VERIFIABLE`, not a green result.
- Target rectangles must not overlap protected rectangles.
- The checker produces reference/result SHA-256, region counts, outside-area
  fractions and optionally a difference heatmap.
- A single global threshold is **not** suitable for every asset. Normal
  illumination and antialiasing can change pixels outside the named material
  region; tune acceptable fractions with real examples and conservative review.
- `Pillow` and `NumPy` are lightweight local QA dependencies. No local AI
  generation or object recognition is performed.
- Host-built-in ImageGen may **not** support mask as an editing input. This
  contract only guarantees QA measurement; never claim pixel-exact generation.

Use:

```bash
./bin/ai-3dgame-image-harness region-qa --edit <edit.toml> \
  --reference <master.png> --result <result.png> --output <qa.json> \
  --diff-image <diff.png>
```

The production `apply-qa` path independently recomputes the measurement from
receipt-bound source/result pixels and persists the measured report.
