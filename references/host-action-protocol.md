# Host Action Protocol

The Host Action Packet is the machine-readable contract between deterministic ai-3dgame-image-harness logic and the Agent/host that can call image tools.

Generate it with:

~~~bash
python3 scripts/next_action.py \
  --asset <asset.toml> \
  --edit <edit.toml> \
  --run <run.json>
~~~

A real run must have passed runtime preflight before an image action can exist. A blocked run returns only `report_blocked`.

## Packet versions

Legacy/dry in-memory flows may emit Packet v2. A real auditable run emits
Packet v3 with `packet_id`, `iteration`, `workspace_root`, and
`input_bindings`. Each input binding carries a portable workspace-relative
path, resolved local path, SHA-256, and PNG metadata.

When an image action is emitted, its `packet_id`, action, state, and iteration
are persisted as the run's `issued_packet`. `mark-generated` accepts only that
exact issued Packet; recomputing a digest for altered content is not enough.

## Common fields

Every packet carries:

- `operation`
- `requested_delta`
- `hard_preserve`
- `soft_preserve`
- `required_hard_gates`
- `topology.required_components`
- `topology.structural_relationships`
- `reference_sufficiency`
- `knowledge.authoritative_facts`
- `knowledge.provisional_fields`
- `knowledge.prohibited_assumptions`
- repair/regeneration `budget`
- `expected_post_action_transition`
- `fallback_policy = "none"`

The host must not re-infer these structural facts from natural language.

## Actions

### imagegen_generate

Use the host-native generation capability with packet references and packet prompt.

### imagegen_edit

Use the exact packet `edit_target`. Support references are separate inputs with declared roles.

For a real v3 action, pass only files in `input_bindings`; do not reinterpret
paths from the shell cwd. After execution, use the same packet to create the
execution receipt.

For initial edits the target comes from `execution.edit_target_reference_id`.

For repair, the failed generated result becomes the edit target.

For major regeneration, the approved base source becomes the edit target again.

### visual_qa

Inspect the actual `result_path` and approved comparison references.

The packet includes required hard gates and allows required hard-gate statuses:

- `PASS`
- `FAIL`
- `NOT_VERIFIABLE`

Write a complete QA TOML, then apply it through `execution_loop.py apply-qa`.
The QA report must bind the current receipt and result digest; an earlier
iteration's report cannot be replayed.

### deliver

The accepted persisted result is terminal.

### report_blocked

The blocker object contains the formal reason. No new image action is allowed.

## Reference knowledge

`reference_sufficiency` states whether minimum roles are covered.

`authoritative_facts` may be enforced.

`provisional_fields` are explicitly unconfirmed.

`prohibited_assumptions` must never be invented or promoted to Master truth.

See:

- `references/reference-sufficiency.md`
- `references/topology-contract.md`
- `references/visual-qa-contract.md`
- `references/host-failure-protocol.md`
- `references/execution-receipt.md`

## OpenAI/Codex delegation

When `$imagegen` is available, follow `references/openai-imagegen-delegation.md`.

Use the built-in image path, obey this packet, persist the selected result, and advance state explicitly. Never auto-switch to API/CLI fallback.
