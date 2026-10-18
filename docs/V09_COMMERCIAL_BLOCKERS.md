# v0.9 → v1.0 Commercial Release Blockers

**Status: BLOCKED_FOR_STEAM_CERTIFICATION.** A successful host-native
ImageGen generation or screenshot capture is not a commercial release gate.

## Verified execution

| Area | Evidence | Outcome |
| --- | --- | --- |
| Native OpenAI ImageGen edit | LAMP, one generated PNG, receipt, 16-gate critic | ACCEPTED |
| Native OpenAI edit plus repair | RADIO, two generated PNGs, independent 23-gate critics, 1 repair | ACCEPTED |
| Production provenance re-audit | Native PNG copies, receipts, event SHA, source SHA, QA records | PASS |
| Unity Player screenshot | Real SecondLifeWorkshop 0.2.0, native in-engine A/B and sharpening HUD PNGs | CAPTURE PASS |
| Whetstone interaction proof | Real same-app opt-in `-whetstoneSelectionProof`, log and exit code 1 | **FAIL** |
| Complete Steam in-game asset release | Seven-category same-commit + artist QA + rights | **BLOCKED** |

## Mandatory remaining work

**B-01 — Approved KNIFE_001 authority.** Current v030E GLB gives
seven named component meshes and four consistent clay views, not independent
visual proof of a hidden Full Tang or agreement with newer nine reference
images/current Unity old-knife presentation. Reconcile actual approved
authority and visually sign off exact silhouette, materials, camera and
cross-view fit. Do not invent a new Master approval or silently switch to a
different historical knife version.

**B-02 — Whetstone Player QA failure.** The real Player displayed
`WHETSTONE_PLAYER_SCREEN 1440x900`, then `Player stone selection rejected`;
exit code **1**; no variant screenshots. Source
`SelectedWhetstoneSelection.TrySelect` can reject due disabled component,
loading, flip-in-progress, or invalid index. Which condition occurred is
not established by current logs. Debug in a **separate game-project branch
or clean copy**; preserve dirty user's Unity tree and existing app builds.

**B-03 — Full game test harness.** The image Harness can now capture actual
Unity Player screenshots and check copied SHAs, but only the independent
`ai-3dgame-test-harness` may close **unity-editor / game-physics /
player-visual / os-input / paper-cut / performance / nondev-build** for
the same exact game commit with live evidence. One runtime screenshot is
insufficient. Rebuild from a clean, approved game commit once fixes land;
do not map uncommitted modifications to an older build's commit.

**B-04 — Rights and Steam platform.** Record creator/source/license for
each shipped asset and an explicit responsible reviewer. Declare applicable
pre-generated AI content in Steam's Content Survey, observe Steam store
capsule copy rules and use only genuine gameplay screenshots as screenshots.
Only Valve can accept the Steam submission.

**B-05 — Real production reliability and scope drift.** LAMP/RADIO
prove the native call, QA, repair and resume; only two tasks / three generated
images have been independently verified. Real image output changed
approximately **2.55% of LAMP pixels outside the approximate target box**
and **15.95% of RADIO pixels outside its box**, slightly more than
their historical benchmarks. Light/texture variations are not necessarily
errors, but no improved pixel fidelity is proven. Add diverse, measured
runs and independent acceptance; enforce lossless existing Master geometry
where the game actually requires pixel-exact preservation.

## Proposed v1.0 objective gates (not currently passed)

- 100% of hard geometry/topology/reference gates genuinely verified and
  accepted on each release asset; any ambiguity returns BLOCKED.
- Repeated real production runs on multiple asset types, reporting
  pass/repair/regeneration rates, out-of-target drift and false-accept cases.
- Unity seven-category same-commit Player QA PASS, including successful
  real stone-selection proof and paper-cut/interaction regression.
- SHA-bound original models, images, native generation provenance,
  Unity screenshots and build reports; no synthetic/provisional evidence
  can mark a release green.
- Human ownership/rights and final visual approval where appropriate;
  Steam's review and content disclosures remain external.

## Local private evidence locations

`$HOME/ai-3dgame-image-harness/.ai-3dgame-image-harness/` contains:
`e2e-v09-preserved-20261018/` historical LAMP/RADIO/Unity screenshots,
`v09-real-radio-audit.json`, `unity-player-qa-20261018-automated/`,
and `unity-whetstone-proof-20261018-retry/` with failure log.

These files stay ignored by Git; the public repository contains contract code,
tests, docs and checks but **not** user game binaries or private assets.
