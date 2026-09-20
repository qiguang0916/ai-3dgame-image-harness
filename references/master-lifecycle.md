# Master Lifecycle

A Master is a production authority, not merely a good-looking generated file.
Promotion is an explicit two-command flow that binds the exact image bytes to a
real-pixel QA report and preserves revision lineage.

## States

`candidate` is an inspected-file proposal that is not production eligible.
`draft` and `candidate` references cannot be bound as edit inputs or selected as
the primary Master. Finalization maps QA to exactly one terminal state:

- `PASS` or `PASS_WITH_NOTES` -> `approved`;
- `BLOCKED` -> `blocked`;
- every repair or regeneration outcome -> `rejected`.

Rejected and blocked candidates remain audit records. They are never copied to
an approved Master path.

## 1. Register a candidate

~~~bash
python3 scripts/master_lifecycle.py candidate \
  --image generated/ASSET_001_EDIT_002.png \
  --source-run runs/ASSET_001_EDIT_002.json \
  --reference-id ASSEMBLED_MASTER_R2 \
  --revision 2 \
  --supersedes ASSEMBLED_MASTER_R1 \
  --out runs/ASSEMBLED_MASTER_R2.candidate.json
~~~

The command requires a decodable PNG with positive pixel dimensions, because
the runtime accepts PNG production references. The image path must equal
`current_result_path` in the auditable source run.
It records the SHA-256 digest, dimensions, source run, revision, and predecessor.
The output path must not already exist.

This is file integrity checking, not Visual QA. The host must still inspect the
actual pixels and compare them with the approved references.

## 2. Write Master QA

Use the normal QA schema and include the candidate binding:

~~~toml
[master_candidate]
reference_id = "ASSEMBLED_MASTER_R2"
content_sha256 = "<candidate sha256>"
actual_pixels_inspected = true
source_run_id = "ASSET_001__EDIT_002"
~~~

The QA `asset_id`, `request_id`, run/iteration, receipt, and result digest must
match the source run's current receipt. Finalization requires that source run to
already be `ACCEPTED` with a persisted PASS verdict for the same receipt and
result. A passing report must satisfy every required hard gate and set
`actual_pixels_inspected = true`.
When pixels cannot be inspected, set it to `false` and use `BLOCKED`; the
deterministic harness does not invent a visual verdict.

## 3. Finalize

~~~bash
python3 scripts/master_lifecycle.py finalize \
  --candidate runs/ASSEMBLED_MASTER_R2.candidate.json \
  --qa qa/QA_MASTER_002.toml \
  --approved-image references/ASSET_001_ASSEMBLED_MASTER_R2.png \
  --out runs/ASSEMBLED_MASTER_R2.approved.json
~~~

For passing QA, `--approved-image` is mandatory and must be a new path distinct
from the candidate. Neither the approved image nor decision record may already
exist. Promotion copies to a temporary sibling, verifies both source and copy
digests, and links it into the final path without overwriting. Non-passing QA omits
`--approved-image` and produces a rejected or blocked decision record.

The approved decision records `revision`, `supersedes`, `content_sha256`, source
run id/path, and source QA report id/path. Add those same lineage fields to the
approved manifest reference, mark the predecessor `superseded`, and only then
make the new reference `primary_master`. `validate_project.py` rejects partial
lineage and an approved enhanced Master whose predecessor is not superseded.

No command silently overwrites a candidate, Master image, or decision record.
