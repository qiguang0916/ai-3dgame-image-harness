# Execution Receipt

A real Host action is not complete when a file merely exists. The v0.5 receipt
binds the current run and Host Action Packet to the exact input and result bytes.

## Real mark-generated

~~~bash
python3 scripts/execution_loop.py mark-generated \
  --run runs/RUN.json \
  --packet packets/01-imagegen.json \
  --result outputs/V1.png \
  --receipt receipts/V1.json \
  --host-attestation "Built-in imagegen executed this packet without fallback."
~~~

The attestation may be a short statement, a JSON object, or a workspace-local
JSON file. It is a host claim, not cryptographic proof of model identity.
Without `--dry-run`, `mark-generated` only accepts an auditable run; legacy or
fixture runs cannot be used to claim a real execution receipt.

## Bound evidence

The packet and receipt record:

- run, request, state, iteration, action, backend, and fallback policy;
- portable and resolved workspace paths;
- edit target and support-reference SHA-256 plus PNG metadata;
- selected result SHA-256, byte size, format, width, and height;
- UTC receipt time and host attestation.

`mark-generated` rejects a Packet that was not issued for the current action,
modified packet content, mismatched run, wrong action, non-`none` fallback,
workspace escape, changed input, or a receipt path that would overwrite an
artifact. Missing/invalid results become formal blockers.

Packet issuance and every state-changing run command take the same exclusive
per-run lock. An issued Packet can therefore be consumed once: a second
concurrent `mark-generated` reloads the advanced state and is rejected rather
than creating orphaned evidence.

## QA binding

Real QA includes `run_id`, `iteration`, `receipt_id`, and `result_sha256`. Before
routing, the Harness re-hashes the result and every bound input, then checks
each required PASS gate's visual evidence. A result or reference replaced after
receipt creation cannot be accepted.

The receipt proves file integrity and the recorded host statement. It does not
prove which proprietary model implementation produced the pixels.
