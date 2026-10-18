# Topology Contract

Use topology only when visible structural consistency matters. It declares project facts; it does not infer hidden engineering details from an image.

## Schema

~~~toml
[topology]
forbid_extra_components = true
allowed_visible_details = ["maker mark", "assembly seam"]

[[topology.components]]
id = "base"
required = true
count = 1
count_unit = "assembly"
visual_definition = "one complete base silhouette"
excludes = ["cast shadows", "reflections"]

[[topology.components]]
id = "decorative_screw"
required = true
count = 3
count_unit = "visible_instance"
visual_definition = "round screw head visible from the approved camera"
excludes = ["engraved circles", "specular highlights"]

[[topology.relationships]]
id = "shade_mounted_on_arm"
type = "mounted_on"
members = ["shade", "arm"]
required = true
~~~

A required component must declare an explicit non-negative integer `count`.
TOML booleans are not counts even though Python represents booleans as a
subclass of integers. `required` and `forbid_extra_components`, when present,
must be real booleans.

### Count semantics

Enhanced components declare all three fields together:

- `count_unit`: `assembly`, `visible_instance`, or `piece`;
- `visual_definition`: a non-empty description of what the inspector counts;
- `excludes`: a list of lookalikes that must not be counted.

`allowed_visible_details` is a topology-level list of details that may remain
visible without being treated as forbidden extra components. It does not add
required components or waive a component count.

Legacy manifests that omit all enhanced component fields remain valid. Their
Host Action Packet uses `count_unit = "piece"`, the component id as the
`visual_definition`, and an empty `excludes` list. Once any enhanced component
field is written, all three are required so a partially specified count cannot
reach the host.

Supported relationship types:

- `integral`
- `separate`
- `mounted_on`
- `enclosed_by`
- `aligned_with`
- `shared_centers`
- `interfaces_with`

## Derived QA gates

Required components produce:

~~~text
topology.component.<component_id>.count
~~~

Required relationships produce:

~~~text
topology.relationship.<relationship_id>
~~~

When extra components are forbidden:

~~~text
topology.no_forbidden_extra_components
~~~

These gates are mandatory in QA. Missing gates invalidate the QA report. A topology `FAIL` routes to major regeneration; a required topology fact that is `NOT_VERIFIABLE` blocks acceptance.

## Host Action Packet

`packet_topology` preserves the full counting meaning. Every required component
contains `id`, `count`, `count_unit`, `visual_definition`, and `excludes`; the
topology packet also contains `allowed_visible_details` and
`forbid_extra_components`. The host must judge the count using these fields as
one contract rather than treating the integer alone as sufficient.

## Boundaries

- Do not encode knife-specific assumptions globally.
- Do not invent millimeter precision from pixels.
- Do not declare hidden structure authoritative unless an approved reference/source supports it.
- Different assets may define completely different topology contracts.
