# v0.13 native material-finishing pilot — real RADIO result (2026-10-22 UTC)

**Scope:** tested engineering candidate only. This is neither human final-art acceptance nor commercial release/Steam certification.

## Motivation and non-deceptive provenance

The approved RADIO original had two brass control knobs with circular brushed-metal reflections. Multiple genuine native-image trials faithfully recolored brass to deep red but retained unwanted radial wedges/turning marks. Three bounded ImageGen attempts through the existing strict-mask Host pipeline correctly failed their explicit enamel-material QA. No unsuccessful sample was removed or counted as accepted.

A model-native-only prompt repeatedly failed to remove the low-frequency material signature. This opt-in **deterministic postproduction** pass fits a smooth low-order enamel face illumination separately within each reviewer-scoped ellipse, keeps genuinely generated softbox highlights, and retains the original rim/knurled sidewalls outside the ellipse. It uses Pillow/NumPy, **no local AI model**, no paid OpenAI Images API or other image generator. Codex authenticated with ChatGPT still executes all actual model-native generation and independent Visual QA.

The original Codex-native PNG is never rewritten. Each real production step creates independent, new-only files:

| Artifact | Meaning |
| --- | --- |
| `native-generated.png` | original Codex native `generated_images` result and event/host provenance |
| `material-finished-native.png` | deterministic parameterized local surface finish applied to the original native pixels only inside the SHA-pinned approved Mask |
| `material-finish-report.json` | recipe/source/native/final SHA, fitted coefficients, changed-area and zero-protected-change observations; **not art approval** |
| `generated.png` | final strictly composited source/finished candidate copied only inside declared editable ROI |
| `precision-compose-report.json` | exact original/approved Mask/derived-candidate composite binding |
| `packet.json`, `events.jsonl`, `attestation.json`, `receipt.json`, `qa.toml` | formal Host call, immutable original event, material provenance, final result and model QA evidence |

`production-audit` independently reruns the exact material recipe on the verified raw Codex image, compares **all material-finished PNG bytes**, checks the recipe's immutable Asset/Edit SHA, independently recomputes final masked composite pixels, verifies final receipt/critic binding, and rehashes the original `generated_images` source and completed `cp` event. A handwritten PASS string is not sufficient.

### Optional versioned edit TOML contract

The following is a **geometry-only example**, not an approved commercial-use sample. The complete edit request must already have a source-approved `[region_contract.strict_mask]` and explicit ROI; `[material_finish]` is opt-in.

```toml
[material_finish]
preset = "smooth_nonmetallic_enamel_face_v1"

[[material_finish.faces]]
id = "top_enamel_face"
center_uv = [0.7760416666666666, 0.5000000000000000]
radius_uv = [0.0358072916666667, 0.0478515625000000]

[[material_finish.faces]]
id = "bottom_enamel_face"
center_uv = [0.7760416666666666, 0.6591796875000000]
radius_uv = [0.0358072916666667, 0.0488281250000000]
```

Coordinates must be intentionally tied to the **same signed-off reference and Mask pixels**. Unapproved/new sources or altered/oversized/out-of-ROI faces must fail before any new native call. The current preset is **RGB PNG only**; it is not a PBR roughness/normal texture generator, universal material model, or rights-certifying process. Perceptual accuracy and seam quality still require independent visual inspection.

## Genuine technical run — native model to independent audit

- Private pilot: `v13-radio-enamel-audited-material-20261022-v001/`.
- Run ID: `RADIO_001__RADIO_001_V13_MATERIAL_AUDIT_20261022_001`.
- User-approved original/reference SHA-256: `443ee73d48ce9c28a453b3ba3fccba3ff03564f04774370f78886e7d7a87f604`.
- User-approved protection Mask SHA-256: `53b73bdae0819d029213140f4888017da1115413ddc095634219a024a805685e`; the owner decision covers ROI/Mask **only**.
- Original ChatGPT-authenticated Codex generated PNG SHA-256: `eeedcccbe0409a8b377ed5aceae7f921ff382014990fa7a5e10a72fe232b608e`.
- Deterministically finished source SHA-256: `8b1fc99dbab1bbe8d40effd23016955a569a8c56e3a03b33af52af93393b9dad`.
- Final source-locked composite SHA-256: `a8f6c83d5759cdc17681ec04ee6034b1a3dd46748718b3322d48ad0f44c9d83c`.
- Material recipe SHA-256: `9d3ff2fa0595bc59edfad9b436e802de6b3df53d1c3bfbc234f52bb9f05e259b`.
- Final Receipt ID: `cc28cef95c41b2e2eddd7b3a4edba87a72c0e16cb149d489bde241de6d8d2056`.
- Material retouch changed 15,369 editable pixels with 0 protected pixel mismatches; final strict composite changed 34,905 target pixels with 0 protected pixel mismatches.
- Formal genuine model Visual QA: **29 required gates PASS / 0 non-PASS**, including no radial metal wedges and correct deep-red nonmetallic material.
- Final Run state: **ACCEPTED**.
- Independent `production_audit.audit_run`: **PASS**, generation step PASS, QA step PASS, zero failures.
- Real independent CLI invocation: `python3 scripts/production_audit.py --run <private-run.json> --output <new-private-audit.json>` → exit **0**, `{"status":"PASS","steps":1,"qa":1,"problems":[],"steam_approved":false}`.
- Independent audited report SHA-256 (separate private report): `03ca77bf347b1adf1c3493f5a21805f664ac3d34125a5141de58ef0660081331`.

The independent machine critic had also reviewed a *separate prior experimentally finished image* and returned 7/7 material/geometry/seam/ROI gates PASS, with separate SHA-bound source/finished pixels. This does not replace the formal 29-gate real Run reviewer or an accountable human artist.

**Limits:** The official Codex CLI transcript did not expose structured image-generation tool-call events. Original `generated_images` bytes, matching completed native copy command, event SHA, subscription login and Host Receipt are the available scoped provenance; this is **not** cryptographic model-identity attestation.

## Regression and release gates

- 7 added isolated deterministic positive/negative tests: real-vs-derived separation, byte-identical independent replay, edited material-report/PNG tamper, coherent forged hashes, bad geometry rejected **before** any Host action, nonred source refused without a fake Receipt, and synthetic stub accepted outputs still failing formal native audit.
- Full unit validation and GitHub CI are recorded on the follow-up Draft PR. Mock/fixture images **do not count** toward real batch targets.
- The actual production run did not come from a source-rights-reviewed, human-final-approved v0.10 immutable commercial batch. **Countable official v0.13 production samples: 0.**
- Human artist signoff, original source rights, LAMP fine brushed-steel finish, KNIFE_001 authoritative Master reconciliation, true Unity Editor/Player/quality/performance results and Steam asset/AI disclosures are **all still BLOCKED**.
- Neither the game worktree nor any historical BLOCKED source/Run/Master has been overwritten. Private raw PNGs, Host transcripts and Unity builds were not uploaded to public GitHub.

**Result:** One actual end-to-end native → material → strict composite → Receipt → machine QA → independent `production-audit=PASS` engineering pilot, not full v0.13 or v1.0 RC exit. Keep all PRs Draft and main untouched.

