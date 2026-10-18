# Optional Visual Reference Evidence Review

A declared reference role is **not** proof that the image actually depicts
the required geometry. Complex interface/structural tasks should use optional
`[reference_evidence]` with `required = true` and `[[reference_evidence.observations]]`:

```toml
[reference_evidence]
required = true

[[reference_evidence.observations]]
reference_id = "BLADE_SIDE_MASTER"
roles = ["geometry", "part_layout"]
visible_facts = ["Knife profile and three rivet center positions are visible."]
unknowns = ["The exact hidden rear thickness is not shown."]
```

When required, every `reference_sufficiency.required_roles` must be covered by
an explicit selected-reference observation, or real preflight blocks. Unknown
hidden geometry must not be promoted to authoritative fact.

**Limits:** these are human/host-declared visual observations. Deterministic
Python can validate completeness and role binding, not whether the claim truly
matches image pixels. Actual evidence must be visually inspected by the host.
