#!/usr/bin/env python3
"""Topology contract helpers for game-image."""

from __future__ import annotations

from typing import Any

from validate_project import ValidationError

ALLOWED_RELATIONSHIP_TYPES = {
    "integral",
    "separate",
    "mounted_on",
    "enclosed_by",
    "aligned_with",
    "shared_centers",
    "interfaces_with",
}

ALLOWED_COUNT_UNITS = {"assembly", "visible_instance", "piece"}
ENHANCED_COMPONENT_FIELDS = {"count_unit", "visual_definition", "excludes"}


def _validate_string_list(value: Any, where: str) -> None:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValidationError(f"{where}: expected a list of non-empty strings")
    if len(value) != len(set(value)):
        raise ValidationError(f"{where}: duplicate values are not allowed")


def validate_topology_schema(asset: dict[str, Any], where: str) -> None:
    topology = asset.get("topology")
    if topology is None:
        return
    if not isinstance(topology, dict):
        raise ValidationError(f"{where}: topology must be a table")

    components = topology.get("components", [])
    relationships = topology.get("relationships", [])
    if not isinstance(components, list):
        raise ValidationError(f"{where}: topology.components must be an array")
    if not isinstance(relationships, list):
        raise ValidationError(
            f"{where}: topology.relationships must be an array"
        )

    if "forbid_extra_components" in topology and not isinstance(
        topology["forbid_extra_components"], bool
    ):
        raise ValidationError(
            f"{where}: topology.forbid_extra_components must be boolean"
        )
    _validate_string_list(
        topology.get("allowed_visible_details", []),
        f"{where}: topology.allowed_visible_details",
    )

    component_ids: set[str] = set()
    for index, component in enumerate(components):
        cwhere = f"{where}: topology.components[{index}]"
        if not isinstance(component, dict):
            raise ValidationError(f"{cwhere}: expected table")
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValidationError(f"{cwhere}: id is required")
        if component_id in component_ids:
            raise ValidationError(
                f"{cwhere}: duplicate component id '{component_id}'"
            )
        component_ids.add(component_id)
        if "required" in component and not isinstance(
            component["required"], bool
        ):
            raise ValidationError(f"{cwhere}: required must be boolean")
        if component.get("required", False) and "count" not in component:
            raise ValidationError(
                f"{cwhere}: required component must declare count"
            )
        count = component.get("count")
        if count is not None and (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            raise ValidationError(
                f"{cwhere}: count must be a non-negative integer"
            )

        enhanced_fields = ENHANCED_COMPONENT_FIELDS.intersection(component)
        if enhanced_fields and enhanced_fields != ENHANCED_COMPONENT_FIELDS:
            missing = ", ".join(
                sorted(ENHANCED_COMPONENT_FIELDS - enhanced_fields)
            )
            raise ValidationError(
                f"{cwhere}: enhanced topology component is missing: {missing}"
            )
        if enhanced_fields:
            count_unit = component["count_unit"]
            if count_unit not in ALLOWED_COUNT_UNITS:
                raise ValidationError(
                    f"{cwhere}: count_unit must be one of: "
                    + ", ".join(sorted(ALLOWED_COUNT_UNITS))
                )
            visual_definition = component["visual_definition"]
            if (
                not isinstance(visual_definition, str)
                or not visual_definition.strip()
            ):
                raise ValidationError(
                    f"{cwhere}: visual_definition must be a non-empty string"
                )
            _validate_string_list(
                component["excludes"], f"{cwhere}: excludes"
            )

    relationship_ids: set[str] = set()
    for index, relationship in enumerate(relationships):
        rwhere = f"{where}: topology.relationships[{index}]"
        if not isinstance(relationship, dict):
            raise ValidationError(f"{rwhere}: expected table")
        relation_id = relationship.get("id")
        relation_type = relationship.get("type")
        members = relationship.get("members")
        if not isinstance(relation_id, str) or not relation_id.strip():
            raise ValidationError(f"{rwhere}: id is required")
        if relation_id in relationship_ids:
            raise ValidationError(
                f"{rwhere}: duplicate relationship id '{relation_id}'"
            )
        relationship_ids.add(relation_id)
        if "required" in relationship and not isinstance(
            relationship["required"], bool
        ):
            raise ValidationError(f"{rwhere}: required must be boolean")
        if relation_type not in ALLOWED_RELATIONSHIP_TYPES:
            raise ValidationError(
                f"{rwhere}: unsupported relationship type '{relation_type}'"
            )
        if (
            not isinstance(members, list)
            or len(members) < 2
            or any(member not in component_ids for member in members)
        ):
            raise ValidationError(
                f"{rwhere}: members must reference at least two known components"
            )


def expected_topology_hard_gates(asset: dict[str, Any]) -> list[str]:
    topology = asset.get("topology", {})
    gates: list[str] = []

    for component in topology.get("components", []):
        if component.get("required", False):
            gates.append(f"topology.component.{component['id']}.count")

    for relationship in topology.get("relationships", []):
        if relationship.get("required", False):
            gates.append(f"topology.relationship.{relationship['id']}")

    if topology.get("forbid_extra_components", False):
        gates.append("topology.no_forbidden_extra_components")

    return gates


def expected_hard_gates(
    asset: dict[str, Any],
    edit: dict[str, Any],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for gate in asset.get("locks", {}).get("hard", []):
        if gate not in seen:
            seen.add(gate)
            result.append(gate)

    for gate in edit.get("preserve", {}).get("hard", []):
        if gate not in seen:
            seen.add(gate)
            result.append(gate)

    for gate in edit.get("qa_contract", {}).get(
        "required_hard_gates", []
    ):
        if gate not in seen:
            seen.add(gate)
            result.append(gate)

    for gate in expected_topology_hard_gates(asset):
        if gate not in seen:
            seen.add(gate)
            result.append(gate)

    return result


def validate_qa_completeness(
    required_hard_gates: list[str],
    qa: dict[str, Any],
) -> None:
    gate_by_name = {
        gate["name"]: gate for gate in qa.get("gates", [])
    }

    missing = [
        gate for gate in required_hard_gates if gate not in gate_by_name
    ]
    if missing:
        raise ValidationError(
            "QA missing required hard gate(s): " + ", ".join(missing)
        )

    for name in required_hard_gates:
        gate = gate_by_name[name]
        if gate.get("severity") != "hard":
            raise ValidationError(
                f"required gate '{name}' must have severity=hard"
            )

    if qa.get("status") in {"PASS", "PASS_WITH_NOTES"}:
        bad = [
            name
            for name in required_hard_gates
            if gate_by_name[name].get("status") != "PASS"
        ]
        if bad:
            raise ValidationError(
                "PASS requires every required hard gate to PASS: "
                + ", ".join(bad)
            )


def topology_route(
    asset: dict[str, Any],
    qa: dict[str, Any],
) -> str | None:
    """Return a deterministic route override for topology failures."""
    topology_gates = set(expected_topology_hard_gates(asset))
    if not topology_gates:
        return None

    gate_by_name = {
        gate["name"]: gate for gate in qa.get("gates", [])
    }
    statuses = {
        name: gate_by_name[name].get("status")
        for name in topology_gates
        if name in gate_by_name
    }

    if any(status == "NOT_VERIFIABLE" for status in statuses.values()):
        return "BLOCKED"
    if any(status == "FAIL" for status in statuses.values()):
        return "REGENERATE_MAJOR"
    return None


def packet_topology(asset: dict[str, Any]) -> dict[str, Any]:
    topology = asset.get("topology", {})
    return {
        "required_components": [
            {
                "id": component["id"],
                "count": component.get("count"),
                "count_unit": component.get("count_unit", "piece"),
                "visual_definition": component.get(
                    "visual_definition", component["id"]
                ),
                "excludes": list(component.get("excludes", [])),
            }
            for component in topology.get("components", [])
            if component.get("required", False)
        ],
        "structural_relationships": [
            {
                "id": relation["id"],
                "type": relation["type"],
                "members": list(relation["members"]),
            }
            for relation in topology.get("relationships", [])
            if relation.get("required", False)
        ],
        "forbid_extra_components": bool(
            topology.get("forbid_extra_components", False)
        ),
        "allowed_visible_details": list(
            topology.get("allowed_visible_details", [])
        ),
    }
