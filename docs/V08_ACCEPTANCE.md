# v0.8 — KNIFE_001 Commercial Gate Evidence

## Verified on user-authorized Mac source

Source: existing `KNIFE_001_v030E.glb` in the user's Unity project. GLB 2.0 SHA256 prefix `71044c53acbba2197067c381`, file size 17,421,592 bytes.

- Actual glTF JSON declares **seven named mesh nodes**: `KNIFE_001_BLADE`, `KNIFE_001_GUARD`, `KNIFE_001_HANDLE_L`, `KNIFE_001_HANDLE_R`, `KNIFE_001_PIN_01`, `_02`, `_03`.
- Read-only geometry baseline rendered successfully with Blender **5.2.2 LTS** using the new CLI. Views `BROAD_A`, `BROAD_B`, `SPINE`, `QUARTER`, each 960×720.
- The canonical check validates same source SHA, four distinct PNG SHA values, nonempty subjects and sane visible bounds; **4/4 PASS**. Normalized approx. foreground fractions: A 0.063115, B 0.062471, spine 0.015246, quarter 0.04727.
- The renderer initially produced blank images because camera rotation used Euler values in Quaternion mode. This failure was observed and fixed; blank-view gates now fail closed rather than accepting files merely because they exist.
- These are **clay/geometry QA views**, not approved PBR textures or final user-accepted Master images. Named nodes alone do not prove visible hidden Full Tang structure or exact dimensional fidelity.

All private GLB/PNGs/reports are stored inside the ignored local `.ai-3dgame-image-harness/knife-v030E-commercial-test/` workspace; no game asset binaries are committed to GitHub.

## Latest commercial package decision

`commercial-gate` reads the actual copied GLB and source-bound four-view evidence:

- GLB component node count: **PASS**.
- Canonical four-view validity: **PASS**.
- Rights review: **MISSING**.
- Final visual material/geometry review: **MISSING**.
- Unity Player actual screenshot + build QA: **MISSING**.
- Overall: **BLOCKED**.

This is an expected safe refusal, not a claim of commercial acceptance. User approval of Master, game lookdev validation, and Unity runtime proof remain.

## Production test and release boundary

The legacy v0.7 unit suite was **136 PASS** prior to v0.8 changes. v0.8 adds new binary-GLB, view, store-dimension, fake Unity attestation and provenance regression tests. GitHub CI and final complete test count are recorded separately after commit.

**Not tested:** new OpenAI ImageGen results, automated host-invocation reliability, real repaired KNIFE images, material consistency in Unity, Steam game publication. Do not claim v1.0 until these tests and independent visual review complete.
