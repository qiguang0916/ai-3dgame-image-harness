#!/usr/bin/env python3
"""Dry-run the full ai-3dgame-image-harness host protocol without calling an image model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import execution_loop
import next_action
import topology_contract
import validate_project


def _qa(asset: dict, edit: dict, status: str) -> dict:
    required = topology_contract.expected_hard_gates(asset, edit)
    gates = [
        {
            "name": name,
            "severity": "hard",
            "status": "PASS",
            "note": "",
        }
        for name in required
    ]
    directives: list[str] = []
    summary = "Requested edit passed all hard gates."

    if status == "REPAIR_MINOR":
        next(
            gate
            for gate in gates
            if gate["name"] == "exact rivet centers"
        )["status"] = "FAIL"
        directives = [
            "Restore only the rear rivet center to the approved master position."
        ]
        summary = "Rear rivet center drifted."

    qa = {
        "document_type": "qa_report",
        "schema_version": 1,
        "report_id": f"DEMO_QA_{status}",
        "asset_id": "KNIFE_001",
        "request_id": "KNIFE_001_EDIT_RIVETS_001",
        "status": status,
        "summary": summary,
        "repair_directives": directives,
        "gates": gates,
    }
    validate_project.validate_document(
        qa, Path(f"demo-{status.lower()}.toml")
    )
    return qa


def main() -> int:
    asset = validate_project.load_document(
        ROOT / "examples" / "KNIFE_001" / "asset.toml"
    ).data
    edit = validate_project.load_document(
        ROOT
        / "examples"
        / "KNIFE_001"
        / "edits"
        / "rivets-brushed-silver.toml"
    ).data

    run = execution_loop.init_run(asset, edit)
    packet = next_action.build_action_packet(asset, edit, run)
    assert packet["action"] == "imagegen_edit"
    assert packet["edit_target"]["reference_id"] == "ASSEMBLED_MASTER"
    print("1 READY -> imagegen_edit")

    run = execution_loop.mark_generated(run, "demo/iteration-1.png")
    packet = next_action.build_action_packet(asset, edit, run)
    assert packet["action"] == "visual_qa"
    print("2 QA_PENDING -> visual_qa")

    run = execution_loop.apply_qa(
        run, _qa(asset, edit, "REPAIR_MINOR")
    )
    packet = next_action.build_action_packet(asset, edit, run)
    assert packet["action"] == "imagegen_edit"
    assert packet["edit_target"]["path"] == "demo/iteration-1.png"
    print("3 REPAIR_READY -> imagegen_edit(failed result)")

    run = execution_loop.mark_generated(run, "demo/iteration-2.png")
    packet = next_action.build_action_packet(asset, edit, run)
    assert packet["action"] == "visual_qa"
    print("4 QA_PENDING -> visual_qa")

    run = execution_loop.apply_qa(run, _qa(asset, edit, "PASS"))
    packet = next_action.build_action_packet(asset, edit, run)
    assert packet["action"] == "deliver"
    assert packet["result_path"] == "demo/iteration-2.png"
    print("5 ACCEPTED -> deliver")
    print("E2E DRY RUN PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
