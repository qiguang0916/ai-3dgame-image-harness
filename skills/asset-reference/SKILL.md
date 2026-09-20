---
name: game-image-asset-reference
description: Manage approved game-asset masters and a reference atlas. Use before generation or editing when multiple images define identity, geometry, material, camera, or component interfaces.
---

# Asset Reference

## Purpose

Create a stable reference chain so the image model does not decide on its own which image is authoritative.

## Reference states

Every reference must have one state:

- approved: eligible for production.
- draft: may be inspected but is not authoritative.
- rejected: must not enter generation unless the user explicitly asks to revisit it.
- superseded: historical only; a newer approved master replaced it.

## Reference roles

A reference may control one or more declared roles:

- identity: overall asset identity.
- geometry: broad shape and proportion.
- silhouette: outer contour.
- part_layout: component count and relative placement.
- interface: contact/mating boundaries between parts.
- material: surface material behavior.
- color: color target.
- camera: view/projection/framing.
- lighting: lighting direction and softness.
- style: rendering language.
- mood: atmosphere only.

Never use a mood-only reference to override geometry.

## Master hierarchy

Use role-specific authority, not a single universal ranking.

Example:

- assembled master: strongest identity and overall appearance.
- side master: strongest side silhouette and longitudinal part positions.
- top master: strongest thickness relationship and top-view proportions.
- component outer master: strongest outer shape/material for that component.
- component inner master: strongest mating/interface logic.

If references conflict, obey the one explicitly authoritative for that role and record the conflict.

## Minimal reference rule

Select the smallest set that covers the current operation.

For a rivet material edit, an assembled master may be enough.

For a component interface correction, use the assembled master plus the relevant interface/component master.

Do not attach every image in the atlas by default.

## Reference binding output

Before generation, produce an internal binding table:

~~~text
REF_1: ASSEMBLED_MASTER
roles: identity, material, camera
must influence: overall appearance, wood tone, framing
must not influence: hidden inner-handle interface

REF_2: HANDLE_L_INNER_MASTER
roles: interface, geometry
must influence: tang contact surface and pin alignment
must not influence: final studio lighting
~~~

## Atlas maintenance

When a new result is approved:

- do not automatically replace a master;
- promote it only if it has a defined master role;
- mark replaced references superseded;
- keep rejected outputs out of future generation;
- update the manifest before the next dependent task.

Use `references/master-lifecycle.md` and `scripts/master_lifecycle.py` for a
candidate. Approval copies it to a new immutable path and emits a lineage
decision; it never silently overwrites or auto-promotes the candidate.

Use templates/asset-manifest.toml as the persistent format.
