# Runtime Preflight

Runtime preflight is the gate between valid project metadata and a real host image action.

## Three validation levels

1. **Static schema validation** — `scripts/validate_project.py`; does not require image files.
2. **Dry-run orchestration** — pass `--dry-run`; intended only for repository examples/tests that intentionally omit binary images.
3. **Real runtime preflight** — default for a real run; required before an image action.

Dry-run skips real file I/O only. It still enforces reference-sufficiency logic and other deterministic contracts.

## Real checks

For every selected production input, preflight verifies:

- reference is approved;
- path resolves to a regular readable file;
- edit target exists;
- required support references exist;
- image format is supported;
- image payload can be decoded by the guaranteed runtime validator.
- every selected input remains inside the declared workspace root;
- SHA-256 and PNG metadata are captured for the Host Action Packet.

The current zero-dependency guaranteed format is PNG. Unsupported formats block instead of being treated as valid by filename alone.

## Blocking reason codes

- `edit_target_missing`
- `required_reference_missing`
- `reference_unreadable`
- `reference_image_invalid`
- `reference_sufficiency_failed`
- `path_outside_workspace`

A failed preflight must be persisted as `BLOCKED`. It must never emit an imagegen action.

## Commands

Real run:

~~~bash
python3 scripts/execution_loop.py init \
  --asset <asset.toml> \
  --edit <edit.toml> \
  --output <run.json>
~~~

Dry-run fixture:

~~~bash
python3 scripts/execution_loop.py init \
  --asset <asset.toml> \
  --edit <edit.toml> \
  --output <run.json> \
  --dry-run
~~~

Use `--workspace-root` when reference paths should resolve from a project root other than the asset-manifest directory.
