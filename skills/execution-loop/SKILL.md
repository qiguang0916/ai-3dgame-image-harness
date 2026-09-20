---
name: game-image-execution-loop
description: Use when a game-image task must run through real reference preflight, host-native image generation or editing, visual QA, bounded repair/regeneration, or a persistent BLOCKED outcome.
---

# Game Image Execution Loop

## Core rule

Deterministic scripts own validation, state, budgets, and next-action packets. The host owns real image generation/editing and visual inspection.

Read when relevant:

- `references/runtime-preflight.md`
- `references/host-action-protocol.md`
- `references/host-failure-protocol.md`
- `references/execution-receipt.md`

## Initialize

Real execution performs reference-file preflight by default:

~~~bash
python3 scripts/execution_loop.py init \
  --asset <asset.toml> \
  --edit <edit.toml> \
  --output <run.json>
~~~

Repository fixtures that intentionally omit binary images must opt in:

~~~bash
python3 scripts/execution_loop.py init ... --dry-run
~~~

A failed real preflight persists `BLOCKED`; it never proceeds to imagegen.

## Run loop

Get the deterministic next action:

~~~bash
python3 scripts/next_action.py --asset <asset.toml> --edit <edit.toml> --run <run.json>
~~~

After a real image result is persisted:

~~~bash
python3 scripts/execution_loop.py mark-generated \
  --run <run.json> \
  --packet <packet.json> \
  --result <image.png> \
  --receipt <receipt.json> \
  --host-attestation "Built-in imagegen executed this packet without fallback."
~~~

After real visual inspection:

~~~bash
python3 scripts/execution_loop.py apply-qa --run <run.json> --qa <qa.toml>
~~~

Repeat until packet action is `deliver` or `report_blocked`.

## Host/backend failure

Do not edit run JSON manually:

~~~bash
python3 scripts/execution_loop.py mark-blocked \
  --run <run.json> \
  --reason-code host_native_imagegen_failed \
  --action imagegen_edit \
  --message "Built-in image edit failed."
~~~

No API/CLI fallback is automatic.

## Routing invariants

- Repair edits the failed result.
- Major regeneration returns to the approved source.
- Required topology failure regenerates.
- Required hard gate `NOT_VERIFIABLE` blocks.
- Repair/regeneration budgets remain bounded.
