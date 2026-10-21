#!/usr/bin/env python3
"""Read-only verifier for external human ROI/mask decisions.

A matching JSON receipt + SHA means specified bytes are bound to a recorded
decision. It does NOT cryptographically authenticate a reviewer or certify the
image, its origin, source rights, the target geometry, or Steam readiness.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from artifact_integrity import canonical_json_bytes, resolve_in_workspace, sha256_file
from validate_project import ValidationError


def verify_roi_mask_approval(*, workspace_root: Path, approval_path: Path,
                             approval_sha256: str, asset_id: str,
                             reference: Path, mask_path: Path,
                             contract: dict[str, Any]) -> dict[str, Any]:
    if (not isinstance(approval_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", approval_sha256) is None):
        raise ValidationError("ROI/Mask review receipt SHA must be 64 lowercase hex chars")
    if not isinstance(asset_id, str) or not re.fullmatch(r"[A-Za-z0-9_\-]{3,80}", asset_id):
        raise ValidationError("valid asset_id is required to bind ROI approval")
    root = Path(workspace_root).expanduser().resolve()
    path = resolve_in_workspace(root, approval_path)
    source = resolve_in_workspace(root, reference)
    mask = resolve_in_workspace(root, mask_path)
    if len({path, source, mask}) != 3 or path.suffix.lower() != ".json":
        raise ValidationError("ROI approval, source and Mask files must be distinct")
    if sha256_file(path) != approval_sha256:
        raise ValidationError("ROI approval record SHA mismatch")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError, OSError) as exc:
        raise ValidationError("ROI approval record is not readable JSON") from exc
    if not isinstance(document, dict):
        raise ValidationError("ROI approval record must be a JSON object")
    required = {
        "schema_version": 1,
        "document_type": "human_review_decision",
        "decision": "APPROVE_ROI_AND_PROTECTION_MASK",
        "inputs_immutable": True,
    }
    for key, expected in required.items():
        actual = document.get(key)
        if type(actual) is not type(expected) or actual != expected:
            raise ValidationError(f"ROI approval record missing/incorrect {key}")
    if (not isinstance(document.get("decision_source"), str)
            or not document["decision_source"].strip()
            or not isinstance(document.get("scope"), str)
            or not document["scope"].strip()
            or not isinstance(document.get("not_approved"), list)
            or len(document["not_approved"]) < 3):
        raise ValidationError("ROI approval scope and exclusions must be explicit")
    cases = document.get("assets")
    if (not isinstance(cases, list)
            or not cases
            or any(not isinstance(a, dict) for a in cases)):
        raise ValidationError("ROI approval requires nonempty asset decision entries")
    matches = [a for a in cases if a.get("asset_id") == asset_id]
    if len(matches) != 1:
        raise ValidationError("ROI approval asset binding missing or duplicated")
    entry = matches[0]
    policy = contract.get("strict_mask")
    if not isinstance(policy, dict):
        raise ValidationError("ROI approval requires a strict_mask contract")
    source_sha = sha256_file(source)
    mask_sha = sha256_file(mask)
    if (policy.get("reference_sha256") != source_sha
            or policy.get("sha256") != mask_sha):
        raise ValidationError("ROI approval input SHA differs from current strict contract")
    if (entry.get("pinned_master_sha256") != source_sha
            or entry.get("approved_binary_mask_sha256") != mask_sha):
        raise ValidationError("ROI approval is not bound to the actual source and Mask")
    if (canonical_json_bytes(entry.get("approved_roi_targets"))
            != canonical_json_bytes(contract.get("targets"))):
        raise ValidationError("ROI approval contract targets differ from approved rectangles")
    if (entry.get("approval_granted") != "ROI_AND_MASK_ONLY"
            or entry.get("final_art_qa") != "REVIEW_REQUIRED"
            or entry.get("visual_alignment_review") != "REVIEW_REQUIRED"
            or entry.get("steam_approved") is not False):
        raise ValidationError("ROI approval attempted to upgrade external QA/release status")
    return {
        "status": "ROI_MASK_DECISION_RECORD_BOUND",
        "review_scope": "ROI_AND_MASK_ONLY",
        "asset_id": asset_id,
        "approval_receipt_sha256": approval_sha256,
        "approved_master_sha256": source_sha,
        "approved_mask_sha256": mask_sha,
        "reviewer_identity_cryptographically_attested": False,
        "independent_visual_qa": "REQUIRED",
        "master_promotion": False,
        "steam_approved": False,
    }
