#!/usr/bin/env python3
"""Compile the next machine-readable host action for a ai-3dgame-image-harness run."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from artifact_integrity import (
    packet_digest,
    canonical_json_bytes,
    sha256_bytes,
    resolve_in_workspace,
    workspace_relative,
)
from compile_brief import compile_brief
from compile_repair import compile_repair_brief
from execution_loop import (
    _exclusive_run_lock,
    load_run,
    save_run,
    validate_run_state,
)
from runtime_preflight import evaluate_reference_sufficiency
from topology_contract import packet_topology
from validate_project import (
    ValidationError,
    cross_validate,
    load_document,
    validate_document,
)


def _reference_packets(
    asset: dict[str, Any],
    edit: dict[str, Any],
) -> list[dict[str, Any]]:
    refs = {ref["id"]: ref for ref in asset.get("references", [])}
    packets: list[dict[str, Any]] = []
    for binding in edit.get("reference_bindings", []):
        ref = refs[binding["reference_id"]]
        packets.append(
            {
                "reference_id": ref["id"],
                "path": ref["path"],
                "roles": list(binding["roles"]),
                "state": ref["state"],
            }
        )
    return packets


def _base_edit_target(
    asset: dict[str, Any],
    edit: dict[str, Any],
) -> dict[str, str] | None:
    target_id = edit.get("execution", {}).get("edit_target_reference_id")
    if not target_id:
        return None

    refs = {ref["id"]: ref for ref in asset.get("references", [])}
    ref = refs[target_id]
    return {
        "reference_id": target_id,
        "path": ref["path"],
    }


def _merged_lock_list(
    asset: dict[str, Any],
    edit: dict[str, Any],
    key: str,
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in [
        *asset.get("locks", {}).get(key, []),
        *edit.get("preserve", {}).get(key, []),
    ]:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _knowledge_packet(
    asset: dict[str, Any],
    edit: dict[str, Any],
) -> dict[str, Any]:
    topology = packet_topology(asset)
    sufficiency_contract = edit.get("reference_sufficiency", {})

    authoritative: list[dict[str, Any]] = []
    for component in topology["required_components"]:
        authoritative.append(
            {
                "kind": "component",
                **component,
            }
        )
    for relation in topology["structural_relationships"]:
        authoritative.append(
            {
                "kind": "relationship",
                **relation,
            }
        )

    return {
        "authoritative_facts": authoritative,
        "provisional_fields": list(
            sufficiency_contract.get("provisional_fields", [])
        ),
        "prohibited_assumptions": list(
            sufficiency_contract.get("prohibited_assumptions", [])
        ),
    }


def _budget_packet(run: dict[str, Any]) -> dict[str, int]:
    return {
        "repair_passes_used": run["repair_passes"],
        "repair_passes_max": run["max_repair_passes"],
        "regeneration_passes_used": run["regeneration_passes"],
        "regeneration_passes_max": run["max_regeneration_passes"],
    }


def _auditable_input_bindings(
    asset: dict[str, Any],
    edit: dict[str, Any],
    run: dict[str, Any],
) -> list[dict[str, Any]]:
    checks = list((run.get("preflight") or {}).get("checks", []))
    roles_by_id = {
        binding["reference_id"]: list(binding.get("roles", []))
        for binding in edit.get("reference_bindings", [])
    }
    bindings = [
        {
            "reference_id": check["reference_id"],
            "kind": check["kind"],
            "path": workspace_relative(
                run["workspace_root"], check["path"]
            ),
            "resolved_path": str(
                resolve_in_workspace(run["workspace_root"], check["path"])
            ),
            "roles": roles_by_id.get(check["reference_id"], []),
            "sha256": check["sha256"],
            "png": check["png"],
        }
        for check in checks
    ]
    if run["state"] == "REPAIR_READY":
        receipt = run.get("current_receipt")
        if not receipt:
            raise ValidationError("auditable repair has no current receipt")
        repaired = {
            "kind": "edit_target",
            "path": receipt["result"]["path"],
            "resolved_path": str(
                resolve_in_workspace(
                    run["workspace_root"], receipt["result"]["path"]
                )
            ),
            "sha256": receipt["result_sha256"],
            "png": receipt["result"]["png"],
        }
        for binding in bindings:
            binding["kind"] = "support_reference"
        bindings.insert(0, repaired)
    return bindings


def build_action_packet(
    asset: dict[str, Any],
    edit: dict[str, Any],
    run: dict[str, Any],
) -> dict[str, Any]:
    validate_run_state(run)

    if asset["asset_id"] != run["asset_id"]:
        raise ValidationError("run asset_id does not match asset manifest")
    if edit["request_id"] != run["request_id"]:
        raise ValidationError("run request_id does not match edit request")

    state = run["state"]
    references = _reference_packets(asset, edit)
    base_target = _base_edit_target(asset, edit)
    hard_preserve = _merged_lock_list(asset, edit, "hard")
    soft_preserve = _merged_lock_list(asset, edit, "soft")
    topology = packet_topology(asset)
    sufficiency = (
        (run.get("preflight") or {}).get("reference_sufficiency")
        or evaluate_reference_sufficiency(edit)
    )

    auditable = bool(run.get("auditable", False))
    packet: dict[str, Any] = {
        "schema_version": 3 if auditable else 2,
        "run_id": run["run_id"],
        "iteration": run["iteration"],
        "state": state,
        "asset_id": run["asset_id"],
        "request_id": run["request_id"],
        "backend": "host_native_imagegen",
        "fallback_policy": "none",
        "operation": edit["operation"],
        "requested_delta": edit["change"],
        "hard_preserve": hard_preserve,
        "soft_preserve": soft_preserve,
        "required_hard_gates": list(
            run.get("required_hard_gates", [])
        ),
        "topology": topology,
        "reference_sufficiency": sufficiency,
        "knowledge": _knowledge_packet(asset, edit),
        "budget": _budget_packet(run),
    }

    if edit.get("asset_spec_v2"):
        from asset_spec_v2 import packet_contract
        packet["asset_spec_v2"] = packet_contract(asset, edit)
    if edit.get("prompt_intelligence"):
        from prompt_control import resolve_role_authority
        packet["prompt_intelligence"] = {
            "mode": "guided",
            "selected_style_profile": edit["prompt_intelligence"].get("style_profile", "none"),
            "role_authority": resolve_role_authority(asset, edit),
            "observations": deepcopy(edit["prompt_intelligence"].get("observations", [])),
        }
    if edit.get("region_contract"):
        packet["region_contract"] = deepcopy(edit["region_contract"])
    if edit.get("art_direction"):
        packet["art_direction"] = deepcopy(edit["art_direction"])
    if edit.get("reference_evidence"):
        packet["reference_evidence"] = deepcopy(edit["reference_evidence"])
    if edit.get("output",{}).get("expected_size") or "require_transparency" in edit.get("output",{}):
        packet["technical_output"] = deepcopy(edit["output"])

    if state == "READY":
        mode = "generate" if edit["operation"] == "create" else "edit"
        packet.update(
            {
                "action": f"imagegen_{mode}",
                "edit_target": base_target if mode == "edit" else None,
                "references": references,
                "prompt": compile_brief(asset, edit),
                "expected_post_action_transition": "QA_PENDING",
                "after_success": "mark_generated",
            }
        )

    elif state == "QA_PENDING":
        result_path = run.get("current_result_path")
        if not result_path:
            raise ValidationError("QA_PENDING run has no current_result_path")
        current_receipt = run.get("current_receipt") if auditable else None
        if auditable and not current_receipt:
            raise ValidationError("auditable QA has no current receipt")
        packet.update(
            {
                "action": "visual_qa",
                "result_path": result_path,
                "comparison_references": references,
                "requested_change": edit["change"],
                "hard_gates": hard_preserve,
                "soft_gates": soft_preserve,
                "allowed_gate_statuses": [
                    "PASS",
                    "FAIL",
                    "NOT_VERIFIABLE",
                ],
                "allowed_statuses": [
                    "PASS",
                    "PASS_WITH_NOTES",
                    "REPAIR_MINOR",
                    "REGENERATE_MAJOR",
                    "BLOCKED",
                ],
                "expected_post_action_transition": (
                    "ACCEPTED | REPAIR_READY | "
                    "REGENERATE_READY | BLOCKED"
                ),
                "after_success": "apply_qa",
            }
        )
        if current_receipt:
            packet.update(
                {
                    "receipt_id": current_receipt["receipt_id"],
                    "result_sha256": current_receipt["result_sha256"],
                    "result_binding": current_receipt["result"],
                }
            )

    elif state == "REPAIR_READY":
        failed_result = run.get("current_result_path")
        qa = run.get("last_qa")
        if not failed_result:
            raise ValidationError("REPAIR_READY run has no failed result path")
        if not qa:
            raise ValidationError("REPAIR_READY run has no stored QA report")
        packet.update(
            {
                "action": "imagegen_edit",
                "edit_target": {
                    "kind": "failed_generated_result",
                    "path": failed_result,
                },
                "references": references,
                "prompt": compile_repair_brief(asset, edit, qa),
                "repair_pass": run["repair_passes"],
                "expected_post_action_transition": "QA_PENDING",
                "after_success": "mark_generated",
            }
        )

    elif state == "REGENERATE_READY":
        mode = "generate" if edit["operation"] == "create" else "edit"
        packet.update(
            {
                "action": f"imagegen_{mode}",
                "edit_target": base_target if mode == "edit" else None,
                "references": references,
                "prompt": compile_brief(asset, edit),
                "regeneration_pass": run["regeneration_passes"],
                "restart_policy": "approved_source_not_failed_result",
                "expected_post_action_transition": "QA_PENDING",
                "after_success": "mark_generated",
            }
        )

    elif state == "ACCEPTED":
        result_path = run.get("current_result_path")
        if not result_path:
            raise ValidationError("ACCEPTED run has no current_result_path")
        packet.update(
            {
                "action": "deliver",
                "result_path": result_path,
                "qa": run.get("last_qa"),
                "expected_post_action_transition": "terminal",
            }
        )

    elif state == "BLOCKED":
        packet.update(
            {
                "action": "report_blocked",
                "blocker": run.get("blocker"),
                "qa": run.get("last_qa"),
                "current_result_path": run.get("current_result_path"),
                "expected_post_action_transition": "terminal",
            }
        )

    else:
        raise ValidationError(f"unsupported run state '{state}'")

    if auditable:
        packet["workspace_root"] = run["workspace_root"]
        packet["input_bindings"] = _auditable_input_bindings(
            asset, edit, run
        )
        packet["packet_id"] = packet_digest(packet)
        if str(packet.get("action", "")).startswith("imagegen_"):
            run["issued_packet"] = {
                "packet_id": packet["packet_id"],
                "action": packet["action"],
                "state": run["state"],
                "iteration": run["iteration"],
            }

    return packet


def build_from_paths(
    asset_path: Path,
    edit_path: Path,
    run_path: Path,
) -> dict[str, Any]:
    with _exclusive_run_lock(run_path):
        run = load_run(run_path)
        if run.get("auditable"):
            workspace_root = Path(run["workspace_root"])
            resolve_in_workspace(workspace_root, run_path.expanduser().resolve())
            asset_path = resolve_in_workspace(
                workspace_root, run["asset_document_path"]
            )
            edit_path = resolve_in_workspace(
                workspace_root, run["edit_document_path"]
            )
        asset_doc = load_document(asset_path)
        edit_doc = load_document(edit_path)
        for doc in (asset_doc, edit_doc):
            validate_document(doc.data, doc.path)
        cross_validate([asset_doc, edit_doc])

        digest_binding = run.get("input_spec_sha256")
        if run.get("auditable") and digest_binding is not None:
            actual = {
                "asset": sha256_bytes(canonical_json_bytes(asset_doc.data)),
                "edit": sha256_bytes(canonical_json_bytes(edit_doc.data)),
            }
            if actual != digest_binding:
                raise ValidationError(
                    "asset or edit specification changed after run initialization; "
                    "start a new auditable run rather than silently altering prompt"
                )

        packet = build_action_packet(asset_doc.data, edit_doc.data, run)
        if run.get("auditable") and str(packet.get("action", "")).startswith(
            "imagegen_"
        ):
            save_run(run_path, run)
        return packet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", required=True, type=Path)
    parser.add_argument("--edit", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        packet = build_from_paths(args.asset, args.edit, args.run)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(packet, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
