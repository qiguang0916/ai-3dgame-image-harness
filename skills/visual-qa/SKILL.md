---
name: ai-3dgame-image-harness-visual-qa
description: Use when accepting, repairing, regenerating, or blocking a generated game-asset image based on actual pixels, approved references, required hard gates, structural topology, and task-specific change requirements.
---

# Game Asset Visual QA

## Core rule

Judge production usability from actual pixels. A visually attractive result is not acceptable if a required hard gate is missing, failed, or unverifiable.

**Required reference:** read `references/visual-qa-contract.md`.

## Inputs

Inspect:

- generated/edited result;
- selected approved references;
- requested delta;
- hard and soft preserve rules;
- `required_hard_gates`;
- topology/reference-sufficiency facts in the Host Action Packet.

If real pixels cannot be inspected, block the run.

## Required hard-gate statuses

Use:

- `PASS`
- `FAIL`
- `NOT_VERIFIABLE`

Every required hard gate must appear in the QA report.

For a real auditable run, bind the report to the current `run_id`, iteration,
receipt id, and result SHA-256. Every required PASS gate needs non-empty visual
evidence, an inspection method, and either a bound reference digest or an
explicit self-contained observation.

Overall `PASS` / `PASS_WITH_NOTES` is valid only when every required hard gate is explicitly `PASS`.

## Routing

- Localized, non-topology defect → `REPAIR_MINOR`.
- Identity/projection/silhouette or required topology/component-count failure → `REGENERATE_MAJOR`.
- Required fact `NOT_VERIFIABLE`, missing evidence, or unavailable inspection → `BLOCKED`.
- All required hard gates PASS → `PASS` or `PASS_WITH_NOTES`.

Repairs must contain minimal `repair_directives` and must protect gates that already passed.

## Boundaries

This is image QA, not CAD metrology. Do not invent dimensions or hidden structure that approved evidence does not support.

Persist QA with `templates/qa-report.toml`; the Harness validates completeness before routing.
