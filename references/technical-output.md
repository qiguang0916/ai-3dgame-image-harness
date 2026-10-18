# Technical Image Output QA

ImageGen images for concept art, UI graphics, backgrounds and model references
need different output properties. The existing `[output]` table accepts
optional enforced format properties:

```toml
[output]
purpose = "hero_prop_reference"
expected_size = "1536x1024"
require_transparency = false
```

Specifying either `expected_size` or `require_transparency` adds the
mandatory Hard Gate `image.technical_output`. The deterministic `apply-qa`
path measures PNG dimensions and actual alpha, and rejects fabricated PASS
when the result does not satisfy the contract.

`require_transparency = true` requires at least one pixel with alpha less
than 255 (not just an RGBA file with fully opaque alpha). This does not imply
every asset has good matte edges. A separate visual check must still judge
fringing, clipping, detail, and legibility at game scale.

No resizer/super-resolution generator is silently applied. If output does not
meet required dimensions, mark the QA failure and follow normal ImageGen
repair/regeneration policy or revise the specification explicitly.

Use `scripts/asset_report.py` or
`./bin/ai-3dgame-image-harness asset-report`.
