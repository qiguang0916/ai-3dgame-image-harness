# Visual QA Contract

Visual QA is performed by the host/agent on actual pixels. The Harness enforces report completeness and routing; it does not fake visual judgment.

## Gate statuses

For required hard gates use:

- `PASS`
- `FAIL`
- `NOT_VERIFIABLE`

A required hard gate may not be omitted.

## Acceptance rules

- Overall `PASS` / `PASS_WITH_NOTES` requires every required hard gate to be present with `severity = "hard"` and `status = "PASS"`.
- In a real auditable run, QA must match the current run, iteration, receipt id,
  and result SHA-256. The result is re-hashed before routing.
- Every required PASS gate needs non-empty evidence, `inspection_method`, and
  either a receipt-bound `reference_digest` or an explicit `observation`.
- Required hard gate `NOT_VERIFIABLE` blocks acceptance.
- Missing required component, wrong required component count, or required topology relationship failure routes to `REGENERATE_MAJOR`.
- A localized non-topology defect may use `REPAIR_MINOR`.
- Backend/inspection inability uses `BLOCKED`, not a synthetic PASS.

Required hard gates are the de-duplicated union of:

1. asset-level `locks.hard`;
2. edit-level `preserve.hard`;
3. `edit_request.qa_contract.required_hard_gates`;
4. required topology components/relationships.

This means a field declared HARD PRESERVE cannot silently disappear from QA.

## Example

~~~toml
[[gates]]
name = "camera/projection"
severity = "hard"
status = "PASS"
note = "Camera and projection match the approved reference."
inspection_method = "side_by_side_pixel_inspection"
reference_digest = "<approved reference sha256>"

[[gates]]
name = "topology.component.decorative_screw.count"
severity = "hard"
status = "PASS"
note = "Three visible screws remain."
inspection_method = "direct_pixel_count"
observation = "Observed exactly 3 visible screw heads using the manifest count semantics."

[[gates]]
name = "topology.relationship.shade_mounted_on_arm"
severity = "hard"
status = "PASS"
note = "The shade remains visibly mounted on the arm."
inspection_method = "side_by_side_pixel_inspection"
reference_digest = "<approved reference sha256>"
~~~

Do not use keyword matching as visual evidence. The host must inspect the actual output and references.
