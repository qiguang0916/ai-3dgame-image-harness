---
name: game-image
description: Use when creating, editing, repairing, or validating game-asset images that require approved references, structural consistency, controlled local edits, repeatable visual QA, or host-image execution without a local model.
---

# Game Image

## Overview

Treat game-image generation as a controlled production run, not a one-shot prompt. Approved references and declared contracts are the source of truth; the host image model is only the executor.

## Core invariants

- Never promote draft/rejected/superseded references into production inputs.
- Real runs perform runtime preflight; use `--dry-run` only for fixtures/examples.
- Edit-like operations use an explicit edit target.
- Host Action Packets are authoritative for target, references, contracts, budgets, and next transition.
- Real generation is auditable: the packet, bound inputs, result, and host attestation produce an execution receipt.
- A Master candidate is never production authority until real-pixel Master QA explicitly approves and promotes a new immutable revision.
- Required hard gates must be explicitly verified before acceptance.
- Topology failures regenerate; localized defects may repair; unavailable evidence/backend blocks.
- Never auto-switch to API/CLI fallback.
- Repair and regeneration remain bounded.

## Workflow

1. Validate schema: `python3 scripts/validate_project.py`.
2. Initialize a real run with `scripts/execution_loop.py init`; preflight may block it.
3. Read the next packet from `scripts/next_action.py`.
4. Execute only the packet action with the host-native image tool.
5. Persist the selected output, then `mark-generated` with its packet, receipt path, and short host attestation.
6. When the packet says `visual_qa`, inspect actual pixels and write a digest-bound, evidence-complete QA TOML.
7. `apply-qa`, then repeat until `deliver` or `report_blocked`.

## Load detailed contracts when relevant

- Runtime inputs: `references/runtime-preflight.md`
- Structural assets: `references/topology-contract.md`
- Minimum evidence / unknowns: `references/reference-sufficiency.md`
- QA report completeness and routing: `references/visual-qa-contract.md`
- Host/backend failure: `references/host-failure-protocol.md`
- Packet fields and execution: `references/host-action-protocol.md`
- Execution receipt and artifact binding: `references/execution-receipt.md`
- Master candidate approval: `references/master-lifecycle.md`
- OpenAI/Codex delegation: `references/openai-imagegen-delegation.md`

Subskills cover reference selection, delta edits, visual QA, and the execution loop under `skills/`.

## Verification

~~~bash
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -v
python3 scripts/demo_e2e.py
~~~

A dry-run proves orchestration only. A real Host Image E2E requires real reference files plus a host-native image tool.
