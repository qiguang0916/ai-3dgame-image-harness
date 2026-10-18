#!/usr/bin/env python3
"""Persist and route the ai-3dgame-image-harness execution state machine.

This script never calls an image model. The Agent/host owns the image tool call.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifact_integrity import (
    file_binding,
    packet_digest,
    png_metadata,
    receipt_digest,
    resolve_in_workspace,
    sha256_file,
    workspace_relative,
)
from validate_project import (
    ValidationError,
    cross_validate,
    load_document,
    validate_document,
)


STATES = {
    "READY",
    "QA_PENDING",
    "REPAIR_READY",
    "REGENERATE_READY",
    "ACCEPTED",
    "BLOCKED",
}

HOST_BLOCK_REASON_CODES = {
    "host_native_imagegen_unavailable",
    "host_native_imagegen_failed",
    "host_native_imagegen_moderation_blocked",
    "generated_result_missing",
    "generated_result_unreadable",
    "visual_inspection_unavailable",
    "required_reference_missing",
    "edit_target_missing",
    "reference_unreadable",
    "reference_image_invalid",
    "reference_sufficiency_failed",
    "path_outside_workspace",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _execution_mode(operation: str) -> str:
    return "generate" if operation == "create" else "edit"


def _next_action_for_ready(operation: str) -> str:
    return (
        "invoke_imagegen_generate"
        if _execution_mode(operation) == "generate"
        else "invoke_imagegen_edit"
    )


def init_run(
    asset: dict[str, Any],
    edit: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    if asset["document_type"] != "asset_manifest":
        raise ValidationError("asset document must be asset_manifest")
    if edit["document_type"] != "edit_request":
        raise ValidationError("edit document must be edit_request")
    if asset["asset_id"] != edit["asset_id"]:
        raise ValidationError("asset_id mismatch between manifest and edit request")

    if asset.get("status") == "bootstrap" and (
        edit["operation"] != "create" or edit.get("reference_bindings")
    ):
        raise ValidationError("bootstrap asset only supports create without production references")

    qa = asset.get("qa", {})
    max_repairs = qa.get("max_repair_passes", 2)
    max_regenerations = qa.get("max_regeneration_passes", 1)

    if not isinstance(max_repairs, int) or not 0 <= max_repairs <= 5:
        raise ValidationError("max_repair_passes must be an integer 0..5")
    if not isinstance(max_regenerations, int) or not 0 <= max_regenerations <= 3:
        raise ValidationError("max_regeneration_passes must be an integer 0..3")

    from topology_contract import (
        expected_hard_gates,
        expected_topology_hard_gates,
    )

    operation = edit["operation"]
    state = {
        "schema_version": 1,
        "run_id": run_id or f"{asset['asset_id']}__{edit['request_id']}",
        "asset_id": asset["asset_id"],
        "request_id": edit["request_id"],
        "state": "READY",
        "iteration": 0,
        "repair_passes": 0,
        "regeneration_passes": 0,
        "max_repair_passes": max_repairs,
        "max_regeneration_passes": max_regenerations,
        "backend_mode": "host_native_imagegen",
        "bootstrap_asset": asset.get("status") == "bootstrap",
        "region_contract": deepcopy(edit.get("region_contract")),
        "output_contract": deepcopy(edit.get("output", {})),
        "execution_mode": _execution_mode(operation),
        "current_result_path": None,
        "last_qa": None,
        "preflight": None,
        "blocker": None,
        "required_hard_gates": expected_hard_gates(asset, edit),
        "topology_hard_gates": expected_topology_hard_gates(asset),
        "next_action": _next_action_for_ready(operation),
        "history": [
            {
                "event": "initialized",
                "state": "READY",
                "operation": operation,
            }
        ],
    }
    validate_run_state(state)
    return state


def validate_run_state(run: dict[str, Any]) -> None:
    required = [
        "schema_version",
        "run_id",
        "asset_id",
        "request_id",
        "state",
        "iteration",
        "repair_passes",
        "regeneration_passes",
        "max_repair_passes",
        "max_regeneration_passes",
        "backend_mode",
        "execution_mode",
        "next_action",
        "history",
    ]
    for key in required:
        if key not in run:
            raise ValidationError(f"run state missing '{key}'")

    if run["schema_version"] != 1:
        raise ValidationError("run schema_version must be 1")
    if run["state"] not in STATES:
        raise ValidationError(f"invalid run state '{run['state']}'")
    if run["execution_mode"] not in {"generate", "edit"}:
        raise ValidationError("execution_mode must be generate or edit")

    for key in (
        "iteration",
        "repair_passes",
        "regeneration_passes",
        "max_repair_passes",
        "max_regeneration_passes",
    ):
        if not isinstance(run[key], int) or run[key] < 0:
            raise ValidationError(f"{key} must be a non-negative integer")

    if run["repair_passes"] > run["max_repair_passes"]:
        raise ValidationError("repair_passes exceeds max_repair_passes")
    if run["regeneration_passes"] > run["max_regeneration_passes"]:
        raise ValidationError(
            "regeneration_passes exceeds max_regeneration_passes"
        )
    if not isinstance(run["history"], list):
        raise ValidationError("history must be a list")

    last_qa = run.get("last_qa")
    if last_qa is not None and not isinstance(last_qa, dict):
        raise ValidationError("last_qa must be an object or null")

    blocker = run.get("blocker")
    if blocker is not None and not isinstance(blocker, dict):
        raise ValidationError("blocker must be an object or null")

    if run.get("auditable"):
        workspace_root = run.get("workspace_root")
        if not isinstance(workspace_root, str) or not workspace_root.strip():
            raise ValidationError("auditable run requires workspace_root")
        if not Path(workspace_root).is_absolute():
            raise ValidationError("workspace_root must be absolute")
        if "current_receipt" not in run:
            raise ValidationError("auditable run requires current_receipt")
        current_receipt = run.get("current_receipt")
        if current_receipt is not None and not isinstance(
            current_receipt, dict
        ):
            raise ValidationError("current_receipt must be an object or null")


def mark_blocked(
    run: dict[str, Any],
    *,
    reason_code: str,
    action: str,
    message: str,
    retryable: bool,
) -> dict[str, Any]:
    validate_run_state(run)
    if reason_code not in HOST_BLOCK_REASON_CODES:
        raise ValidationError(f"unsupported blocker reason_code '{reason_code}'")
    if run["state"] == "ACCEPTED":
        raise ValidationError("cannot block an ACCEPTED run")

    updated = deepcopy(run)
    updated["state"] = "BLOCKED"
    updated["next_action"] = "report_blocked"
    updated["blocker"] = {
        "reason_code": reason_code,
        "action": action,
        "message": message.strip(),
        "retryable": bool(retryable),
        "timestamp": _utc_now(),
        "budget_snapshot": {
            "repair_passes": updated["repair_passes"],
            "max_repair_passes": updated["max_repair_passes"],
            "regeneration_passes": updated["regeneration_passes"],
            "max_regeneration_passes": updated["max_regeneration_passes"],
        },
    }
    updated["history"].append(
        {
            "event": "blocked",
            "state": "BLOCKED",
            "reason_code": reason_code,
            "action": action,
            "retryable": bool(retryable),
            "timestamp": updated["blocker"]["timestamp"],
        }
    )
    validate_run_state(updated)
    return updated


def mark_generated(
    run: dict[str, Any],
    result_path: str,
    *,
    receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_run_state(run)
    if run.get("auditable") and receipt is None:
        raise ValidationError(
            "auditable runs must record generation through a receipt"
        )
    if run["state"] not in {"READY", "REPAIR_READY", "REGENERATE_READY"}:
        raise ValidationError(
            f"cannot record generation while run is {run['state']}"
        )
    if not result_path.strip():
        raise ValidationError("result_path must not be empty")

    updated = deepcopy(run)
    source_state = updated["state"]
    updated["iteration"] += 1
    updated["state"] = "QA_PENDING"
    updated["current_result_path"] = result_path
    if receipt is not None:
        updated["current_receipt"] = deepcopy(receipt)
    updated["last_qa"] = None
    updated["blocker"] = None
    updated["next_action"] = "inspect_pixels_and_write_qa"
    updated["history"].append(
        {
            "event": "generated",
            "from_state": source_state,
            "state": "QA_PENDING",
            "result_path": result_path,
            "iteration": updated["iteration"],
        }
    )
    validate_run_state(updated)
    return updated


def _required_gate_statuses(
    run: dict[str, Any],
    qa: dict[str, Any],
) -> dict[str, str]:
    by_name = {
        gate["name"]: gate.get("status")
        for gate in qa.get("gates", [])
    }
    return {
        name: by_name[name]
        for name in run.get("required_hard_gates", [])
        if name in by_name
    }


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_auditable_qa(
    run: dict[str, Any],
    qa: dict[str, Any],
) -> None:
    receipt = run.get("current_receipt")
    if not isinstance(receipt, dict):
        raise ValidationError("auditable QA requires a current receipt")
    if receipt_digest(receipt) != receipt.get("receipt_id"):
        raise ValidationError("current receipt integrity check failed")

    expected = {
        "run_id": run["run_id"],
        "iteration": run["iteration"],
        "receipt_id": receipt["receipt_id"],
        "result_sha256": receipt["result_sha256"],
    }
    for key, value in expected.items():
        if qa.get(key) != value:
            raise ValidationError(f"QA {key} does not match current receipt")

    result_path = resolve_in_workspace(
        run["workspace_root"], receipt["result"]["path"]
    )
    if not result_path.is_file():
        raise ValidationError("receipt result is missing during QA")
    if sha256_file(result_path) != receipt["result_sha256"]:
        raise ValidationError("receipt result was replaced before QA")

    for binding in receipt.get("input_bindings", []):
        input_path = resolve_in_workspace(
            run["workspace_root"], binding.get("path", "")
        )
        if not input_path.is_file():
            raise ValidationError("receipt input is missing during QA")
        if sha256_file(input_path) != binding.get("sha256"):
            raise ValidationError("receipt input was replaced before QA")
        if png_metadata(input_path) != binding.get("png"):
            raise ValidationError("receipt input PNG metadata changed before QA")

    gate_by_name = {gate["name"]: gate for gate in qa.get("gates", [])}
    allowed_reference_digests = {
        binding["sha256"] for binding in receipt.get("input_bindings", [])
    }
    for name in run.get("required_hard_gates", []):
        gate = gate_by_name.get(name, {})
        if gate.get("status") != "PASS":
            continue
        if not (
            _non_empty(gate.get("note"))
            or _non_empty(gate.get("evidence"))
        ):
            raise ValidationError(
                f"required PASS gate '{name}' needs non-empty note or evidence"
            )
        if not _non_empty(gate.get("inspection_method")):
            raise ValidationError(
                f"required PASS gate '{name}' needs inspection_method"
            )
        reference_digest = gate.get("reference_digest")
        observation = gate.get("observation")
        if not (_non_empty(reference_digest) or _non_empty(observation)):
            raise ValidationError(
                f"required PASS gate '{name}' needs reference_digest or observation"
            )
        if (
            _non_empty(reference_digest)
            and reference_digest not in allowed_reference_digests
        ):
            raise ValidationError(
                f"required PASS gate '{name}' has an unbound reference_digest"
            )


def apply_qa(
    run: dict[str, Any],
    qa: dict[str, Any],
) -> dict[str, Any]:
    validate_run_state(run)
    if run["state"] != "QA_PENDING":
        raise ValidationError(f"cannot apply QA while run is {run['state']}")
    if qa["document_type"] != "qa_report":
        raise ValidationError("QA document must be qa_report")
    if qa["asset_id"] != run["asset_id"]:
        raise ValidationError("QA asset_id does not match run")
    if qa["request_id"] != run["request_id"]:
        raise ValidationError("QA request_id does not match run")

    from topology_contract import validate_qa_completeness

    validate_qa_completeness(
        list(run.get("required_hard_gates", [])),
        qa,
    )
    if run.get("auditable"):
        _validate_auditable_qa(run, qa)
    region_result = None
    contract = run.get("region_contract")
    if run.get("auditable") and isinstance(contract, dict):
        preflight = run.get("preflight") or {}
        targets = [x for x in preflight.get("checks", []) if x.get("kind") == "edit_target"]
        if len(targets) != 1:
            raise ValidationError("region QA requires one bound original edit target")
        from region_quality import verify_region_gate
        from artifact_integrity import resolve_in_workspace
        source_path = resolve_in_workspace(run["workspace_root"], targets[0]["path"])
        result_path = resolve_in_workspace(run["workspace_root"], run["current_result_path"])
        gate = next((g for g in qa.get("gates",[]) if g.get("name") == "visual.region_preservation"),{})
        region_result = verify_region_gate(contract, source_path, result_path, gate.get("status", ""))
        if region_result["status"] == "FAIL" and qa.get("status") in {"PASS","PASS_WITH_NOTES"}:
            raise ValidationError("deterministic region QA FAIL forbids overall PASS")

    output_result = None
    if run.get("auditable"):
        output_contract = run.get("output_contract") or {}
        if "expected_size" in output_contract or "require_transparency" in output_contract:
            from asset_report import verify_output_gate
            from artifact_integrity import resolve_in_workspace
            result_path = resolve_in_workspace(run["workspace_root"], run["current_result_path"])
            gate = next((g for g in qa.get("gates", []) if g.get("name")=="image.technical_output"),{})
            output_result = verify_output_gate(output_contract, result_path, gate.get("status",""))
            if output_result["status"] == "FAIL" and qa.get("status") in {"PASS","PASS_WITH_NOTES"}:
                raise ValidationError("deterministic technical QA FAIL forbids overall PASS")

    qa_status = qa["status"]
    updated = deepcopy(run)
    updated["last_qa"] = {
        "document_type": "qa_report",
        "schema_version": qa["schema_version"],
        "report_id": qa["report_id"],
        "asset_id": qa["asset_id"],
        "request_id": qa["request_id"],
        "status": qa_status,
        "reported_status": qa["status"],
        "summary": qa.get("summary", ""),
        "gates": deepcopy(qa.get("gates", [])),
        "repair_directives": deepcopy(qa.get("repair_directives", [])),
    }
    for key in ("run_id", "iteration", "receipt_id", "result_sha256"):
        if key in qa:
            updated["last_qa"][key] = qa[key]
    if region_result is not None:
        updated["last_qa"]["region_quality"] = region_result
    if output_result is not None:
        updated["last_qa"]["technical_output"] = output_result

    required_statuses = _required_gate_statuses(run, qa)
    if any(
        status == "NOT_VERIFIABLE"
        for status in required_statuses.values()
    ):
        return mark_blocked(
            updated,
            reason_code="visual_inspection_unavailable",
            action="visual_qa",
            message="A required hard gate was NOT_VERIFIABLE.",
            retryable=False,
        )

    topology_names = set(run.get("topology_hard_gates", []))
    topology_statuses = {
        name: required_statuses.get(name)
        for name in topology_names
        if name in required_statuses
    }

    if any(status == "FAIL" for status in topology_statuses.values()):
        qa_status = "REGENERATE_MAJOR"
        updated["last_qa"]["status"] = qa_status

    if qa_status in {"PASS", "PASS_WITH_NOTES"}:
        updated["state"] = "ACCEPTED"
        updated["next_action"] = "deliver_final_asset"

    elif qa_status == "REPAIR_MINOR":
        if updated["repair_passes"] < updated["max_repair_passes"]:
            updated["repair_passes"] += 1
            updated["state"] = "REPAIR_READY"
            updated["next_action"] = (
                "compile_repair_brief_and_invoke_imagegen_edit"
            )
        else:
            updated["state"] = "BLOCKED"
            updated["next_action"] = "report_repair_budget_exhausted"
            updated["blocker"] = {
                "reason_code": "repair_budget_exhausted",
                "action": "visual_qa",
                "message": "Repair budget exhausted.",
                "retryable": False,
                "timestamp": _utc_now(),
            }

    elif qa_status == "REGENERATE_MAJOR":
        if (
            updated["regeneration_passes"]
            < updated["max_regeneration_passes"]
        ):
            updated["regeneration_passes"] += 1
            updated["state"] = "REGENERATE_READY"
            updated["next_action"] = (
                "restart_from_approved_master_with_original_brief"
            )
        else:
            updated["state"] = "BLOCKED"
            updated["next_action"] = "report_regeneration_budget_exhausted"
            updated["blocker"] = {
                "reason_code": "regeneration_budget_exhausted",
                "action": "visual_qa",
                "message": "Regeneration budget exhausted.",
                "retryable": False,
                "timestamp": _utc_now(),
            }

    elif qa_status == "BLOCKED":
        return mark_blocked(
            updated,
            reason_code="visual_inspection_unavailable",
            action="visual_qa",
            message=qa.get("summary", "Visual QA blocked."),
            retryable=False,
        )

    else:
        raise ValidationError(f"unsupported QA status '{qa_status}'")

    updated["history"].append(
        {
            "event": "qa_applied",
            "qa_report_id": qa["report_id"],
            "qa_status": qa_status,
            "reported_status": qa["status"],
            "state": updated["state"],
        }
    )
    validate_run_state(updated)
    return updated


def load_run(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        run = json.load(handle)
    if not isinstance(run, dict):
        raise ValidationError("run JSON root must be an object")
    validate_run_state(run)
    return run


def save_run(path: Path, run: dict[str, Any]) -> None:
    validate_run_state(run)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


@contextmanager
def _exclusive_run_lock(path: Path):
    """Serialize state-changing CLI operations for one run file."""
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def init_from_paths(
    asset_path: Path,
    edit_path: Path,
    run_id: str | None = None,
    *,
    dry_run: bool = False,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    asset_doc = load_document(asset_path)
    edit_doc = load_document(edit_path)
    validate_document(asset_doc.data, asset_doc.path)
    validate_document(edit_doc.data, edit_doc.path)
    cross_validate([asset_doc, edit_doc])

    run = init_run(asset_doc.data, edit_doc.data, run_id=run_id)

    from runtime_preflight import run_preflight

    base_dir = (workspace_root or asset_path.parent).expanduser().resolve()
    resolve_in_workspace(base_dir, asset_path.expanduser().resolve())
    resolve_in_workspace(base_dir, edit_path.expanduser().resolve())
    run["workspace_root"] = str(base_dir)
    run["auditable"] = not dry_run
    if not dry_run:
        # Bind the parsed production specification to the run. The host must
        # never receive a silently changed user intent after preflight.
        from artifact_integrity import canonical_json_bytes, sha256_bytes
        run["input_spec_sha256"] = {
            "asset": sha256_bytes(canonical_json_bytes(asset_doc.data)),
            "edit": sha256_bytes(canonical_json_bytes(edit_doc.data)),
        }
    run["current_receipt"] = None
    run["asset_document_path"] = workspace_relative(
        base_dir, asset_path.expanduser().resolve()
    )
    run["edit_document_path"] = workspace_relative(
        base_dir, edit_path.expanduser().resolve()
    )
    preflight = run_preflight(
        asset_doc.data,
        edit_doc.data,
        base_dir,
        dry_run=dry_run,
    )
    run["preflight"] = preflight

    if preflight["status"] == "BLOCKED":
        run = mark_blocked(
            run,
            reason_code=preflight["reason_code"],
            action=run["next_action"],
            message=preflight.get(
                "detail",
                f"Runtime preflight blocked: {preflight['reason_code']}",
            ),
            retryable=False,
        )
    return run


def apply_qa_from_path(
    run: dict[str, Any],
    qa_path: Path,
) -> dict[str, Any]:
    qa_doc = load_document(qa_path)
    validate_document(qa_doc.data, qa_doc.path)
    return apply_qa(run, qa_doc.data)


def _load_json_object(
    value: dict[str, Any] | Path | str,
    workspace_root: Path,
    label: str,
) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    raw = str(value)
    if raw.lstrip().startswith("{"):
        loaded = json.loads(raw)
    else:
        path = resolve_in_workspace(workspace_root, raw)
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValidationError(f"{label} must be a JSON object")
    return loaded


def _load_host_attestation(
    value: dict[str, Any] | Path | str,
    workspace_root: Path,
) -> dict[str, Any]:
    if isinstance(value, dict):
        attestation = deepcopy(value)
    else:
        raw = str(value).strip()
        if not raw:
            raise ValidationError("host attestation must not be empty")
        if raw.startswith("{"):
            attestation = _load_json_object(raw, workspace_root, "host attestation")
        else:
            possible_path = resolve_in_workspace(workspace_root, raw)
            if possible_path.is_file():
                attestation = _load_json_object(
                    possible_path, workspace_root, "host attestation"
                )
            else:
                attestation = {"statement": raw}
    if not attestation:
        raise ValidationError("host attestation must not be empty")
    return attestation


def _expected_packet_action(run: dict[str, Any]) -> str:
    if run["state"] == "REPAIR_READY":
        return "imagegen_edit"
    if run["state"] in {"READY", "REGENERATE_READY"}:
        return f"imagegen_{run['execution_mode']}"
    raise ValidationError(
        f"cannot record generation while run is {run['state']}"
    )


def _record_auditable_generation(
    run: dict[str, Any],
    result: str,
    *,
    packet: dict[str, Any] | Path | str,
    receipt_path: Path | str,
    host_attestation: dict[str, Any] | Path | str,
) -> dict[str, Any]:
    workspace_root = Path(run["workspace_root"]).resolve()
    packet_data = _load_json_object(packet, workspace_root, "packet")
    if packet_data.get("packet_id") != packet_digest(packet_data):
        raise ValidationError("packet integrity check failed")
    issued_packet = run.get("issued_packet")
    if not isinstance(issued_packet, dict):
        raise ValidationError("run has no issued action packet binding")
    expected_issued = {
        "packet_id": packet_data.get("packet_id"),
        "action": packet_data.get("action"),
        "state": run.get("state"),
        "iteration": run.get("iteration"),
    }
    if issued_packet != expected_issued:
        raise ValidationError("packet does not match the action issued for this run")
    for key in ("run_id", "asset_id", "request_id", "state", "iteration"):
        if packet_data.get(key) != run.get(key):
            raise ValidationError(f"packet {key} does not match run")
    if packet_data.get("action") != _expected_packet_action(run):
        raise ValidationError("packet action does not match run")
    if packet_data.get("fallback_policy") != "none":
        raise ValidationError("packet fallback_policy must be none")
    if packet_data.get("backend") != "host_native_imagegen":
        raise ValidationError("packet backend must be host_native_imagegen")

    verified_inputs: list[dict[str, Any]] = []
    input_bindings = packet_data.get("input_bindings")
    if not isinstance(input_bindings, list):
        raise ValidationError("auditable packet input_bindings must be a list")
    for binding in input_bindings:
        if not isinstance(binding, dict):
            raise ValidationError("packet input binding must be an object")
        input_path = resolve_in_workspace(workspace_root, binding.get("path", ""))
        if not input_path.is_file():
            raise ValidationError("packet input is missing")
        current_digest = sha256_file(input_path)
        if current_digest != binding.get("sha256"):
            raise ValidationError("packet input was replaced after packet creation")
        current_png = png_metadata(input_path)
        if current_png != binding.get("png"):
            raise ValidationError("packet input PNG metadata changed")
        verified = deepcopy(binding)
        verified["path"] = workspace_relative(workspace_root, input_path)
        verified_inputs.append(verified)

    result_path = resolve_in_workspace(workspace_root, result)
    if not result_path.exists():
        return mark_blocked(
            run,
            reason_code="generated_result_missing",
            action=run["next_action"],
            message=f"Generated result does not exist: {result_path}",
            retryable=True,
        )
    if not result_path.is_file() or not os.access(result_path, os.R_OK):
        return mark_blocked(
            run,
            reason_code="generated_result_unreadable",
            action=run["next_action"],
            message=f"Generated result is unreadable: {result_path}",
            retryable=True,
        )
    from runtime_preflight import validate_image_file

    valid, detail = validate_image_file(result_path)
    if not valid:
        return mark_blocked(
            run,
            reason_code="generated_result_unreadable",
            action=run["next_action"],
            message=f"Generated image is invalid: {detail}",
            retryable=True,
        )

    attestation = _load_host_attestation(host_attestation, workspace_root)

    result_binding = file_binding(workspace_root, result_path)
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run["run_id"],
        "iteration": run["iteration"] + 1,
        "packet_id": packet_data["packet_id"],
        "packet_sha256": packet_digest(packet_data),
        "action": packet_data["action"],
        "fallback_policy": packet_data["fallback_policy"],
        "input_bindings": verified_inputs,
        "result": result_binding,
        "result_sha256": result_binding["sha256"],
        "created_at": _utc_now(),
        "host_attestation": attestation,
    }
    receipt["receipt_id"] = receipt_digest(receipt)

    destination = resolve_in_workspace(workspace_root, receipt_path)
    protected_paths = {
        resolve_in_workspace(workspace_root, binding["path"]).resolve()
        for binding in verified_inputs
    }
    protected_paths.add(result_path.resolve())
    if destination.resolve() in protected_paths:
        raise ValidationError("receipt path collides with a bound artifact")
    if destination.exists():
        raise ValidationError(f"refusing to overwrite existing receipt: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    except FileExistsError as exc:
        raise ValidationError(
            f"refusing to overwrite existing receipt: {destination}"
        ) from exc
    updated = mark_generated(
        run,
        result_binding["path"],
        receipt=receipt,
    )
    updated["current_receipt_path"] = workspace_relative(
        workspace_root, destination
    )
    updated["history"][-1]["receipt_id"] = receipt["receipt_id"]
    return updated


def _record_generated_cli(
    run: dict[str, Any],
    result: str,
    *,
    dry_run: bool,
    packet: dict[str, Any] | Path | str | None = None,
    receipt_path: Path | str | None = None,
    host_attestation: dict[str, Any] | Path | str | None = None,
) -> dict[str, Any]:
    if dry_run:
        return mark_generated(run, result)

    if run.get("auditable") is not True:
        raise ValidationError(
            "real mark-generated requires an auditable run; use --dry-run only for fixtures"
        )
    if packet is None or receipt_path is None or host_attestation is None:
        raise ValidationError(
            "real auditable mark-generated requires --packet, --receipt, "
            "and --host-attestation"
        )
    return _record_auditable_generation(
        run,
        result,
        packet=packet,
        receipt_path=receipt_path,
        host_attestation=host_attestation,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a new execution run JSON.")
    init.add_argument("--asset", required=True, type=Path)
    init.add_argument("--edit", required=True, type=Path)
    init.add_argument("--output", required=True, type=Path)
    init.add_argument("--run-id")
    init.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip real reference file checks; for tests/examples only.",
    )
    init.add_argument(
        "--workspace-root",
        type=Path,
        help="Resolve reference paths relative to this directory.",
    )

    generated = sub.add_parser(
        "mark-generated",
        help="Record the selected generated/edited image and enter QA_PENDING.",
    )
    generated.add_argument("--run", required=True, type=Path)
    generated.add_argument("--result", required=True)
    generated.add_argument("--packet")
    generated.add_argument("--receipt")
    generated.add_argument("--host-attestation")
    generated.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip real result-file checks; for tests/examples only.",
    )

    qa = sub.add_parser(
        "apply-qa",
        help="Apply a QA TOML report and route the next action.",
    )
    qa.add_argument("--run", required=True, type=Path)
    qa.add_argument("--qa", required=True, type=Path)

    blocked = sub.add_parser(
        "mark-blocked",
        help="Persist a host/backend blocker without editing run JSON by hand.",
    )
    blocked.add_argument("--run", required=True, type=Path)
    blocked.add_argument(
        "--reason-code",
        required=True,
        choices=sorted(HOST_BLOCK_REASON_CODES),
    )
    blocked.add_argument("--action", required=True)
    blocked.add_argument("--message", required=True)
    blocked.add_argument("--retryable", action="store_true")

    status = sub.add_parser("status", help="Print current run state.")
    status.add_argument("--run", required=True, type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            run = init_from_paths(
                args.asset,
                args.edit,
                args.run_id,
                dry_run=args.dry_run,
                workspace_root=args.workspace_root,
            )
            save_run(args.output, run)
        elif args.command == "mark-generated":
            if not args.dry_run and not all(
                (args.packet, args.receipt, args.host_attestation)
            ):
                raise ValidationError(
                    "real mark-generated requires --packet, --receipt, "
                    "and --host-attestation"
                )
            with _exclusive_run_lock(args.run):
                run = load_run(args.run)
                if run.get("auditable"):
                    resolve_in_workspace(
                        run["workspace_root"], args.run.expanduser().resolve()
                    )
                run = _record_generated_cli(
                    run,
                    args.result,
                    dry_run=args.dry_run,
                    packet=args.packet,
                    receipt_path=args.receipt,
                    host_attestation=args.host_attestation,
                )
                save_run(args.run, run)
        elif args.command == "apply-qa":
            with _exclusive_run_lock(args.run):
                run = load_run(args.run)
                qa_path = args.qa
                if run.get("auditable"):
                    resolve_in_workspace(
                        run["workspace_root"], args.run.expanduser().resolve()
                    )
                    qa_path = resolve_in_workspace(
                        run["workspace_root"], args.qa
                    )
                run = apply_qa_from_path(run, qa_path)
                save_run(args.run, run)
        elif args.command == "mark-blocked":
            with _exclusive_run_lock(args.run):
                run = load_run(args.run)
                run = mark_blocked(
                    run,
                    reason_code=args.reason_code,
                    action=args.action,
                    message=args.message,
                    retryable=args.retryable,
                )
                save_run(args.run, run)
        elif args.command == "status":
            run = load_run(args.run)
            print(json.dumps(run, indent=2, ensure_ascii=False))
            return 0
        else:
            raise ValidationError(f"unknown command '{args.command}'")
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.command != "status":
        print(
            json.dumps(
                {
                    "state": run["state"],
                    "next_action": run["next_action"],
                    "iteration": run["iteration"],
                    "repair_passes": run["repair_passes"],
                    "regeneration_passes": run["regeneration_passes"],
                    "blocker": run.get("blocker"),
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
