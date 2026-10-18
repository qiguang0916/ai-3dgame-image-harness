#!/usr/bin/env python3
"""Compile a backend-neutral ai-3dgame-image-harness brief from asset + edit TOML files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from runtime_preflight import evaluate_reference_sufficiency
from topology_contract import packet_topology
from validate_project import (
    ValidationError,
    cross_validate,
    load_document,
    validate_document,
)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def compile_brief(asset: dict[str, Any], edit: dict[str, Any]) -> str:
    if asset["document_type"] != "asset_manifest":
        raise ValidationError("first document must be asset_manifest")
    if edit["document_type"] != "edit_request":
        raise ValidationError("second document must be edit_request")
    if asset["asset_id"] != edit["asset_id"]:
        raise ValidationError("asset_id mismatch between manifest and edit request")

    reference_by_id = {ref["id"]: ref for ref in asset.get("references", [])}
    reference_lines: list[str] = []
    for index, binding in enumerate(edit.get("reference_bindings", []), start=1):
        ref = reference_by_id[binding["reference_id"]]
        roles = ", ".join(binding["roles"])
        reference_lines.append(
            f"REF_{index}: {ref['id']} | path={ref['path']} | roles={roles}"
        )

    asset_hard = asset.get("locks", {}).get("hard", [])
    edit_hard = edit.get("preserve", {}).get("hard", [])
    asset_soft = asset.get("locks", {}).get("soft", [])
    edit_soft = edit.get("preserve", {}).get("soft", [])

    hard_preserve = _dedupe([*asset_hard, *edit_hard])
    soft_preserve = _dedupe([*asset_soft, *edit_soft])

    output = edit.get("output", {})
    edit_target_id = edit.get("execution", {}).get("edit_target_reference_id")
    edit_target_line = None
    if edit_target_id:
        ref = reference_by_id[edit_target_id]
        edit_target_line = f"{edit_target_id} | path={ref['path']}"

    topology = packet_topology(asset)
    sufficiency = evaluate_reference_sufficiency(edit)
    prohibited_assumptions = list(
        edit.get("reference_sufficiency", {}).get(
            "prohibited_assumptions", []
        )
    )
    provisional_fields = list(
        edit.get("reference_sufficiency", {}).get(
            "provisional_fields", []
        )
    )

    lines = [
        f"ASSET: {asset['asset_id']}",
        f"OPERATION: {edit['operation']}",
    ]

    if edit_target_line:
        lines.extend(
            [
                "",
                "EDIT TARGET:",
                edit_target_line,
            ]
        )

    lines.extend(
        [
            "",
            "TARGET:",
            str(edit["target"]),
            "",
            "CHANGE:",
            str(edit["change"]),
            "",
            "REFERENCE ROLES:",
        ]
    )
    lines.extend(reference_lines or ["(none)"])

    lines.extend(["", "REFERENCE SUFFICIENCY:"])
    lines.append(f"- status: {sufficiency['status']}")
    if sufficiency["required_roles"]:
        lines.append(
            "- required_roles: " + ", ".join(sufficiency["required_roles"])
        )
    if sufficiency["missing_roles"]:
        lines.append(
            "- missing_roles: " + ", ".join(sufficiency["missing_roles"])
        )

    if topology["required_components"]:
        lines.extend(["", "REQUIRED COMPONENTS:"])
        for component in topology["required_components"]:
            lines.append(
                f"- {component['id']} | count={component['count']} | "
                f"count_unit={component['count_unit']} | "
                f"visual_definition={component['visual_definition']}"
            )
            if component["excludes"]:
                lines.append(
                    "  excludes: " + ", ".join(component["excludes"])
                )

    if topology["structural_relationships"]:
        lines.extend(["", "STRUCTURAL RELATIONSHIPS:"])
        for relation in topology["structural_relationships"]:
            members = ", ".join(relation["members"])
            lines.append(
                f"- {relation['id']} | type={relation['type']} | "
                f"members={members}"
            )

    if topology["forbid_extra_components"]:
        lines.extend(
            [
                "",
                "TOPOLOGY BOUNDARY:",
                "- Do not add undeclared structural components.",
            ]
        )
        if topology["allowed_visible_details"]:
            lines.append(
                "- Allowed visible details that are not structural components: "
                + ", ".join(topology["allowed_visible_details"])
            )

    region_contract = edit.get("region_contract")
    if region_contract:
        lines.extend(["", "EDIT REGION CONTRACT (normalized 0..1 image coordinates):"])
        for item in region_contract.get("targets", []):
            lines.append(f"- EDITABLE {item['id']}: bbox={item['bbox']}")
        for item in region_contract.get("protected", []):
            lines.append(f"- PROTECTED {item['id']}: bbox={item['bbox']}")
        lines.append("- Keep regions outside the allowed edits unchanged as far as imagegen allows.")
        lines.append("- Region coordinates are QA guidance; do not claim a native mask unless the host supports it.")

    art=edit.get("art_direction")
    if art:
        lines.extend(["", "ART DIRECTION:"])
        for key in ("purpose","style_family","camera","lighting","game_scale_read"):
            lines.append(f"- {key}: {art[key]}")
        for key in ("palette","material_notes"):
            lines.append(f"- {key}: " + ", ".join(art[key]))
        if art.get("must_match"):
            lines.append("- This art direction is a mandatory Visual QA hard gate.")

    visual_evidence=edit.get("reference_evidence")
    if visual_evidence and visual_evidence.get("observations"):
        lines.extend(["", "REFERENCE VISUAL EVIDENCE (host-declared observations):"])
        for item in visual_evidence["observations"]:
            lines.append(f"- {item['reference_id']} roles: " + ", ".join(item["roles"]))
            lines.extend(f"  VISIBLE: {fact}" for fact in item["visible_facts"])
            lines.extend(f"  UNKNOWN / DO NOT INVENT: {unknown}" for unknown in item.get("unknowns",[]))

    if edit.get("prompt_intelligence"):
        from prompt_control import format_prompt_intelligence
        lines.extend(["", format_prompt_intelligence(asset, edit)])

    if provisional_fields:
        lines.extend(["", "PROVISIONAL / UNKNOWN FIELDS:"])
        lines.extend(f"- {item}" for item in provisional_fields)

    if prohibited_assumptions:
        lines.extend(["", "PROHIBITED ASSUMPTIONS:"])
        lines.extend(f"- {item}" for item in prohibited_assumptions)

    lines.extend(["", "HARD PRESERVE:"])
    lines.extend(f"- {item}" for item in hard_preserve)

    lines.extend(["", "SOFT PRESERVE:"])
    lines.extend(f"- {item}" for item in soft_preserve)

    lines.extend(["", "OUTPUT:"])
    if output:
        for key in sorted(output):
            lines.append(f"- {key}: {output[key]}")
    else:
        lines.append("- preserve current framing unless the request says otherwise")

    if edit["operation"] in {"local_edit", "repair"}:
        lines.extend(
            [
                "",
                "EDIT BOUNDARY:",
                "Do not redesign or reinterpret unaffected regions.",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def compile_from_paths(asset_path: Path, edit_path: Path) -> str:
    asset_doc = load_document(asset_path)
    edit_doc = load_document(edit_path)

    validate_document(asset_doc.data, asset_doc.path)
    validate_document(edit_doc.data, edit_doc.path)
    cross_validate([asset_doc, edit_doc])

    return compile_brief(asset_doc.data, edit_doc.data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset_manifest", type=Path)
    parser.add_argument("edit_request", type=Path)
    args = parser.parse_args(argv)

    try:
        brief = compile_from_paths(args.asset_manifest, args.edit_request)
    except (OSError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(brief, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
