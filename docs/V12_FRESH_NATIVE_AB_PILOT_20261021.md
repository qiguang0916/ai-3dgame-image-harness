# v0.12 Fresh native Codex ImageGen A/B pilot — 2026-10-21

**Status: two distinct new native-source PNGs verified, two strict-composition pixel gates PASS, machine visual QA mixed, human art/Unity/rights/Steam release BLOCKED.**

## Actual execution, not synthetic fixtures

Using the **same project-owner-approved v002 ROI and SHA-locked binary
protection mask** as the archived-image pilot, two independently generated
Codex-native image outputs were obtained: a lamp with three screw heads
changed from brass to cold silver and a radio with two control knobs changed
from brass to glossy deep red.

Each asset had one new bounded native generation attempt with an identifiable
Codex session. The raw output bytes were copied from a
`CODEX_HOME/generated_images` source and independently compared by SHA.
Codex self-reported one ImageGen call per successful generation session, but
the Codex JSONL interface did **not** expose structured
`image_generation_call` events. Treat provenance as
**generated_images path + thread + file hash**, not cryptographic model
attestation or formally metered call count.

Two earlier LAMP attempts must not be confused with the successful LAMP
candidate:
- The historical Harness Run remains `BLOCKED` at its original failed Host
  authentication preflight; it was never replayed or overwritten.
- Direct attempt v002 failed WebSocket/HTTPS networking inside a Python-spawned
  Codex child; the process later exited without ImageGen event or PNG.
  Its private stderr and event snapshot remain archived.
- A separate direct Codex attempt v003 produced the successful lamp output.
- RADIO direct attempt v001 produced a generated source PNG, but its automatic
  `cp` was rejected by the Host's noninteractive approval policy.
  Rather than calling ImageGen again, a read-only recovery verified the
  `generated_images` source belonged to the matching completed thread,
  then copied its original bytes into the private attempt folder with
  independent SHA verification. No image regeneration was performed for
  recovery.

No paid OpenAI Images API, third-party generation service, or local model
was used or substituted.

## Source and native candidate binding

| SHA binding | LAMP_001 | RADIO_001 |
| --- | --- | --- |
| Approved Master | `ae91896b0dcf9edff201e78d93b0c64bced4ec122d407486342be926ca82f182` | `443ee73d48ce9c28a453b3ba3fccba3ff03564f04774370f78886e7d7a87f604` |
| User-approved binary mask | `82a6b86744f293c5a464affc55ca2e133bbb49fc273005b166171bcd137180aa` | `53b73bdae0819d029213140f4888017da1115413ddc095634219a024a805685e` |
| Fresh Codex native PNG | `46d5f42448465357ccb96364ecce0fab8bbbf0ec5f50071513ce5224207c47dd` | `3e359a56267190c96e693d7b2f5fefa8c974bd8c6e7050d204913bc10f943336` |
| v0.12 strict composite | `112de3dc4558340522adaf6d4ca4c24881f719f2bc409edb19b622c05c24e6a8` | `b7a5996148ef522e86892ebf279782e9b6866a058e774d1095f6626ce4e33d9f` |
| v0.12 quality report | `78bf21f02a7f8f17b9ed3b6b9dda06076c4a9603932afb7b96c71facde38849d` | `4fb2afc1b76d01b401854cbd7f72685a2c23d0f089e59040a00187e799c6501a` |
| Machine visual critic JSON | `3b9ea6ff3cca188d055899f9188fc25ab50376c2bfd54410532be480e4f8a69f` | `0ddfde40934aedb42da1d37379098007f21b9b5bf0959f1485c81ab694945e6a` |

Shared project-owner ROI/Mask decision receipt:
`6ac6a73def53297bbfa1327481fff518abaf8185589a81c72fea54e66104549b`.
The prior owner's approval was for these exact ROI and Mask files only;
**it does not pre-approve all future generated artwork, geometry, rights or
Unity use**.

Input dimensions/mode: LAMP `1312×1199 RGB`; RADIO `1536×1024 RGB`.
Both fresh generated outputs retained their respective source image
dimensions/mode and had matching ICC conditions, satisfying strict-composite
technical comparison preconditions.

## Actual pixel-quality findings on real native outputs

| Metric | LAMP_001 new native | RADIO_001 new native |
| --- | ---: | ---: |
| Native raw outside approved ROI, changed fraction at max-channel threshold 15 | 2.11936% | 7.98834% |
| Strict composite outside same approved ROI, threshold 15 | **0%** | **0%** |
| Protected pixel mismatches (exact) | **0** | **0** |
| Outside-target pixel mismatches (exact) | **0** | **0** |
| Mismatches between native candidate and composited editable area (exact) | **0** | **0** |
| Actual changed target pixels | **7,220** | **34,891** |
| Maximum extra RGB seam gradient | **20** | **16** |
| Objective preservation gate | **PASS** | **PASS** |
| Owner approved mask + SHA gate | **PASS** | **PASS** |
| Native output/composition receipt SHA binding | **PASS** | **PASS** |

Within these **specific** approved Mask bounds, new raw image changes outside
the intended edit were eliminated by v0.12 post-composition. These exact
pixel counts do **not** prove perceptual material quality, source ownership,
hidden geometry, or gameplay readiness.

For context only, the historical v0.9 ImageGen output measured with those
same v002 masks showed raw outside-target threshold-15 differences of
**2.35417%** (LAMP) and **14.51927%** (RADIO), with max seam risk of **30**
and **27** after v0.12 post-composition. On the new native samples the seam
risk measurements are **20** and **16**. This pairwise numeric contrast is
**not** a statistically meaningful model-quality or commercial-readiness
improvement claim; it compares two distinct generation samples.

## Independent machine visual quality review

The generated source and final composite were visually inspected, then a
distinct read-only Codex visual critic evaluated each asset against its
approved original Master and new raw output. The critic report JSONs were
checked against the six declared per-asset gates with
`native_codex_host.validate_critic`. This is a **machine reviewer, not an
independent human art signoff**.

- **RADIO_001: machine `PASS` (6/6 visible gates).** Two complete deep-red
  knobs with rounded faces, ridges and glossy highlights; original
  grille/tuning window/handle and camera framing preserved; no conspicuous
  seam or brass fringe at the reviewer-visible resolution.
- **LAMP_001: machine `BLOCKED` (5/6 visible gates).** Three cold-silver
  screw heads, original count/slots/positions, preserved lamp silhouette and
  no obvious seam. However the required **fine directional brushed-steel
  grain remains `NOT_VERIFIABLE`** at these native pixels. A second
  read-only reviewer examined nearest-neighbor enlarged true-pixel crops
  and independently returned `NOT_VERIFIABLE`; pixel enlargement cannot
  create material detail that the source did not resolve. The image is not
  technically rejected for drift; material finish acceptance remains open.

Both assets are still **NOT APPROVED FOR RELEASE**. Explicit human reviewer
decisions, rights review and Unity Player evidence have not been supplied.
LAMP should not be silently promoted to full material PASS.

## Private evidence location and non-destructive controls

The per-asset real PNGs, raw native Codex event transcripts, comparison
composites, approval receipts, independent numeric/image QA, machine review
and high-resolution visual contact sheets are stored on the authorized Mac
under the **private** `ai_bridge/v12-native-approved-pilot-20261021-v001/`
directory. Its local `REVIEW_FRESH_NATIVE_20261021.html` opens both actual
source/raw/composite comparisons and local QA reports.

Private immutable summary artifact:
`FRESH_NATIVE_TWO_ASSET_PILOT_20261021.json`, SHA-256
`5354d79bdad1c7e5944423fb26d2871eb3b754d8970f2169396889fce11deb59`.

Do not push private PNGs, complete native Host transcripts, or user source
assets into this public GitHub repository. The original dirty Mac worktree,
historical Masters and old BLOCKED Runs remain untouched.

## Next release-blocking acceptance steps

1. Decide whether the LAMP fine-grain brushed finish must be re-authored at
   a higher material-resolving pixel scale or can receive explicit accountable
   human visual approval at the current resolution. No status can be upgraded
   based only on a nearest-neighbor crop.
2. Obtain independent human artistic approval for **both new images**, with
   the source/target SHA, model QA limits and visible material/seam results.
3. Reconcile the original Mac worktree safely before any code integration;
   PR #11/#12 stay Draft pending their remaining gates.
4. Expand from this **2 image / 2 asset pilot** to the planned **12 and 30
   distinct** real native production tasks, measuring first-pass/final QA
   denominators, false positive rate, failures, recovery and costs.
5. Import three separate asset categories into an **isolated Unity Editor**
   project, then capture bound real Player screenshots. Test Harness and
   rights/Steam review remain independent.

**Result: technical native-image precision pilot succeeded; complete v0.12
art release gate still BLOCKED.**
