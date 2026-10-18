# First Master Bootstrap (v0.6)

Production rules remain strict: a production edit requires an existing **approved**
master; candidate and draft assets cannot bypass them.

New assets are entered through an explicitly marked **bootstrap asset**:

- `status = "bootstrap"`, no `primary_master`, no approved production references.
- The only permitted operation is `create`, without production reference bindings.
- A real Host `imagegen_generate` Packet is issued, PNG persisted, receipt recorded.
- Required Hard Gate Visual QA runs over actual pixels; `ACCEPTED` is required.
- `master candidate --revision 1` records immutable bytes, without `--supersedes`.
- Master QA binds the actual candidate digest, current receipt and explicit pixel inspection.
- `master finalize` promotes it into a new immutable path, never overwriting.
- `master register-first` creates a **new** active manifest in the same directory, with
  `primary_master` and `[[references]]` including digest/source lineage.
- New production edits may use the approved Master only **after** the new manifest validates.

Subsequent Master revisions continue requiring `--supersedes`; a first Master
cannot fake a predecessor.

For sample input, see `examples/BOOTSTRAP_PROP_001/`.
Test fixtures using synthetic PNGs are NOT real ImageGen E2E.
