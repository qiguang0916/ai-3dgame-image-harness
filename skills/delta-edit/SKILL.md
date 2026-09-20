---
name: game-image-delta-edit
description: Route game image changes to the smallest safe edit. Use for local material/color/part corrections, repair prompts, and edit-vs-regenerate decisions.
---

# Delta Edit

## Core rule

Describe only the requested difference.

The more of the original asset you re-describe, the more opportunities the image model has to reinterpret unchanged areas.

## Operation routing

Choose local_edit when:

- target is spatially or semantically bounded;
- current identity, camera, and broad geometry are correct;
- examples: recolor a bolster, change rivet finish, remove a stain, strengthen a bevel highlight.

Choose structural_edit when:

- one component shape or interface changes;
- the rest of the asset must remain stable.

Choose repair when:

- a generated output failed specific QA gates;
- the failure is localized and the core image remains usable.

Choose regenerate when:

- wrong projection/view;
- wrong broad silhouette;
- wrong asset identity;
- wrong part count/topology;
- widespread drift;
- two repair passes fail the same hard gate.

## Delta prompt pattern

~~~text
OPERATION: local_edit

TARGET:
Only the three existing handle rivets.

CHANGE:
Change the existing rivet finish to subtle brushed cold-silver steel.

HARD PRESERVE:
- exact blade silhouette
- exact handle silhouette
- exact rivet count and centers
- bolster and butt-cap geometry
- camera, crop, projection

SOFT PRESERVE:
- wood tone and grain direction
- blade finish
- lighting and background

NO REDESIGN:
Do not reinterpret unaffected regions.
~~~

Use NO REDESIGN as a short boundary statement; do not create long negative-prompt lists.

## Repair directive

A correction must name the failed gate and the smallest restoration.

Bad:

“Make the knife more accurate.”

Good:

“Restore the rear rivet center to the approved master position. Keep the other two rivets and all other geometry unchanged.”

## Change budget

Default to one conceptual change per edit pass.

If the user requests several unrelated changes, split them when they affect different lock domains and one combined edit would make drift hard to diagnose.

## Escalation rule

If a local edit repeatedly damages hard-preserved regions:

1. stop the repair loop;
2. restore the last approved master as the edit target;
3. reduce the edit scope;
4. if the backend still cannot maintain hard gates, report the control limit.

Do not hide repeated failure behind aesthetic success.
