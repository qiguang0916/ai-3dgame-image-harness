# v0.9 — Unity QA evidence bridge (read-only)

The AI image harness does **not** duplicate the game's gameplay automation.
The independent [ai-3dgame-test-harness](https://github.com/qiguang0916/ai-3dgame-test-harness)
is the authority for seven same-commit Unity categories:

`unity-editor`, `game-physics`, `player-visual`, `os-input`,
`paper-cut`, `performance`, `nondev-build`.

The image harness verifies that every category has a passing, verified,
same-commit, immutable local `file://` evidence artifact whose SHA-256 matches.
For player-visual the evidence artifact itself must be a real PNG/JPEG of
sufficient dimensions from a Player-capture source. For os-input,
player-visual, game-physics and unity-editor the source classification must
agree with the independent game-test harness; nondev-build explicitly requires
`developmentBuild:false`. Any failure or missing category **BLOCKS**.

## Using the bridge

The input release JSON must contain `expectedCommit` and `evidence`
array using the independent test harness `ReleaseEvidence` contract.
It must refer to **real** on-disk artifacts, not synthetic test fixtures.

```bash
./bin/ai-3dgame-image-harness unity-proof \
  --manifest /path/real-game-release-evidence.json \
  --commit <40-hex-game-commit> \
  --output /new/report/unity-seven-gate.json
```

The public in-game `commercial-gate` additionally requires a
`unity_integration` proof with `test_harness_release` binding to the **original
seven-category manifest**, `build_id` matching the game commit, and
`player_capture` binding to the same screenshot SHA.

A fake `Unity PASS` string or a one-page screenshot report is inadequate.
The bridge checks hashes and provenance labels; it cannot cryptographically
prove a screenshot was truly captured by Unity or determine legal ownership.
Commercial release still requires independent human/engine source review.

Do not run Unity against a dirty user project in place. Use an isolated Unity
copy or pre-existing built Player with appropriate permissions and collect
real test-harness evidence separately; no writes to the user's game repo are
performed by this bridge.

## Real Unity Player screenshot without OS screen recording

For the existing Second Life Workshop build, `MinimumSharpeningLoop.cs`
already supplies `-inspectHtmlQaCapture` in-engine capture. The v0.9
image Harness wraps that exact opt-in feature:

```bash
./bin/ai-3dgame-image-harness player-capture \
  --app /path/to/SecondLifeWorkshop-0.2.0.app \
  --output-dir /new/private/empty/proof-folder --duration 45

./bin/ai-3dgame-image-harness player-capture \
  --app /path/to/SecondLifeWorkshop-0.2.0.app \
  --output-dir /existing/proof-folder --verify-existing
```

The Player itself writes `sharpening-hud.png`,
`inspection-html-A-2880x1800.png`, and `inspection-html-B-2880x1800.png`.
The harness requires all three, checks actual PNG format/dimensions,
verifies A/B screenshot path markers and `MINIMUM_LOOP_READY` in the Unity
log, binds the executable/log/PNG hashes, and refuses overwritten
destinations. The verify command rejects tampered previous evidence.

**Scope:** one real Player screenshot capture test, NOT a seven-category
game-test Harness QA pass. The screen-grabbing OS authorization is not
required because the screenshot is produced by Unity's own rendering
coroutine. The evidence is still not cryptographic proof of the UI's visual
correctness or legal rights. `commercial-gate` keeps requiring independent
same-commit seven-category proof and human rights/visual signoff.
