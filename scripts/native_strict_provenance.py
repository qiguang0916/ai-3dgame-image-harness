#!/usr/bin/env python3
"""Opt-in native-to-strict-composite lineage; not a material or rights approval.

A Codex-generated PNG remains immutable as native-generated.png. The separately
derived generated.png contains only editable ROI pixels from that native image.
Production audit independently recomputes the derived pixels, rather than
trusting a report's PASS string. Legacy non-mask runs are untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from artifact_integrity import (
    canonical_json_bytes, receipt_digest, resolve_in_workspace, sha256_bytes,
    sha256_file, workspace_relative,
)
from precision_composite import strict_composite
from precision_quality import _verify_compose_report
from region_quality import _pixel_rect, validate_region_contract, verify_required_edit_points
from validate_project import ValidationError, load_document


def is_strict_native_run(run: dict[str, Any]) -> bool:
    contract = run.get("region_contract")
    return isinstance(contract, dict) and isinstance(contract.get("strict_mask"), dict)


def _context(run: dict[str, Any], packet: dict[str, Any]):
    root = Path(run["workspace_root"]).expanduser().resolve()
    contract = run.get("region_contract")
    if not isinstance(contract, dict) or not isinstance(contract.get("strict_mask"), dict):
        raise ValidationError("strict native composite requires an approved SHA-bound mask contract")
    if run.get("execution_mode") != "edit":
        raise ValidationError("strict native composite is only supported for editing")
    validate_region_contract({"operation": "local_edit", "region_contract": contract},
                             "native strict production")
    checks = [c for c in (run.get("preflight") or {}).get("checks", [])
              if isinstance(c, dict) and c.get("kind") == "edit_target"]
    if len(checks) != 1:
        raise ValidationError("native strict composite requires one original edit target")
    source = resolve_in_workspace(root, checks[0]["path"])
    if not source.is_file() or sha256_file(source) != checks[0].get("sha256"):
        raise ValidationError("original edit target is absent or SHA changed")
    # A first generation edits the approved Master. A bounded repair edits
    # the last SHA-bound derived result, with the original Master supplied as
    # support_reference. Never confuse that local repair image with a Master.
    bindings = packet.get("input_bindings")
    if not isinstance(bindings, list):
        raise ValidationError("native Host packet input bindings missing")
    action_state = packet.get("state")
    original_sha = checks[0]["sha256"]
    if action_state == "REPAIR_READY":
        pinned_original = [b for b in bindings if isinstance(b, dict)
                           and b.get("kind") == "support_reference"
                           and b.get("sha256") == original_sha]
        repair_target = [b for b in bindings if isinstance(b, dict)
                         and b.get("kind") == "edit_target"]
        step_index = packet.get("iteration")
        if (len(pinned_original) != 1 or len(repair_target) != 1
                or not isinstance(step_index, int) or isinstance(step_index, bool)
                or step_index < 1):
            raise ValidationError("repair must bind original Master and one prior target")
        current = repair_target[0]
        previous = resolve_in_workspace(root, current["path"])
        if (previous.is_symlink() or not previous.is_file()
                or previous.name != "generated.png"
                or previous.parent.name != f"{step_index - 1:04d}-imagegen_edit"
                or sha256_file(previous) != current.get("sha256")):
            raise ValidationError("repair must bind exact previous derived PNG")
        prior_record = previous.parent / "receipt.json"
        if not prior_record.is_file() or prior_record.is_symlink():
            raise ValidationError("repair previous generation receipt missing")
        previous_receipt = json.loads(prior_record.read_text(encoding="utf-8"))
        if (not isinstance(previous_receipt, dict)
                or previous_receipt.get("receipt_id") != receipt_digest(previous_receipt)
                or previous_receipt.get("run_id") != run.get("run_id")
                or previous_receipt.get("iteration") != step_index
                or previous_receipt.get("result_sha256") != current["sha256"]
                or (previous_receipt.get("result") or {}).get("path")
                   != workspace_relative(root, previous)):
            raise ValidationError("repair prior native/derived receipt lineage invalid")
    elif action_state in {"READY", "REGENERATE_READY"}:
        if not any(isinstance(b, dict) and b.get("kind") == "edit_target"
                   and b.get("sha256") == original_sha
                   for b in bindings):
            raise ValidationError("native Host packet omitted authoritative edit target")
    else:
        raise ValidationError("unsupported strict-mask native Host action state")
    mask_policy = contract["strict_mask"]
    mask = resolve_in_workspace(root, mask_policy["path"])
    if (mask_policy.get("reference_sha256") != sha256_file(source) or
            not mask.is_file() or mask_policy.get("sha256") != sha256_file(mask)):
        raise ValidationError("native strict Master or approved Mask SHA mismatch")
    # On audit, do not trust an edited run.json that no longer matches the
    # original TOML whose digest was frozen at Run initialization.
    edit = load_document(resolve_in_workspace(root, run["edit_document_path"])).data
    asset = load_document(resolve_in_workspace(root, run["asset_document_path"])).data
    digests = run.get("input_spec_sha256") or {}
    if (digests.get("edit") != sha256_bytes(canonical_json_bytes(edit))
            or digests.get("asset") != sha256_bytes(canonical_json_bytes(asset))
            or canonical_json_bytes(edit.get("region_contract")) != canonical_json_bytes(contract)):
        raise ValidationError("native strict source contract changed after Run initialization")
    return root, contract, source, mask


def preflight_native_strict(run: dict[str, Any], packet: dict[str, Any]) -> None:
    """Fail before consuming a native call on stale repair, Mask or ROI inputs."""
    import numpy as np
    from PIL import Image

    _, contract, source, mask = _context(run, packet)
    with Image.open(source) as im:
        im.load()
        if im.format != "PNG" or im.mode not in ("RGB", "RGBA"):
            raise ValidationError("native strict source must be RGB/RGBA PNG")
        width, height = im.size
    with Image.open(mask) as im:
        im.load()
        if im.format != "PNG" or im.mode != "L" or im.size != (width, height):
            raise ValidationError("approved Mask must match original source pixel coordinates")
        protected = np.asarray(im, dtype=np.uint8)
    if not np.all((protected == 0) | (protected == 255)):
        raise ValidationError("approved strict Mask must be binary before native generation")
    targets = np.zeros((height, width), dtype=bool)
    for box in contract["targets"]:
        x0, y0, x1, y1 = _pixel_rect(box["bbox"], width, height)
        targets[y0:y1, x0:x1] = True
    editable = targets & (protected == 0)
    if not editable.any():
        raise ValidationError("no editable Mask pixels before native generation")
    verify_required_edit_points(contract, editable)


def _expected_paths(root: Path, step: Path):
    return {
        "native_path": workspace_relative(root, step / "native-generated.png"),
        "result_path": workspace_relative(root, step / "generated.png"),
        "compose_report_path": workspace_relative(root, step / "precision-compose-report.json"),
    }


def _proof(root: Path, step: Path, contract: dict[str, Any], source: Path, mask: Path):
    paths = _expected_paths(root, step)
    return {
        "schema_version": 1,
        "kind": "sha_bound_strict_composite",
        **paths,
        "native_sha256": sha256_file(step / "native-generated.png"),
        "result_sha256": sha256_file(step / "generated.png"),
        "compose_report_sha256": sha256_file(step / "precision-compose-report.json"),
        "source_sha256": sha256_file(source),
        "mask_sha256": sha256_file(mask),
        "contract_sha256": sha256_bytes(canonical_json_bytes(contract)),
        "artistic_approval": "REQUIRED",
        "model_generated_composite_directly": False,
    }


def compose_native_generation(run: dict[str, Any], packet: dict[str, Any],
                              step: Path) -> dict[str, Any]:
    """Act on an already persisted native-generated.png. NEVER calls ImageGen."""
    root, contract, source, mask = _context(run, packet)
    step = resolve_in_workspace(root, step)
    raw = step / "native-generated.png"
    result = step / "generated.png"
    report = step / "precision-compose-report.json"
    if not raw.is_file() or raw.is_symlink():
        raise ValidationError("native original is missing or symlinked")
    strict_composite(source, raw, contract, root, result, report)
    return _proof(root, step, contract, source, mask)


def verify_native_strict_derivation(run: dict[str, Any], packet: dict[str, Any],
                                    receipt: dict[str, Any], attestation: dict[str, Any],
                                    step: Path) -> dict[str, Any]:
    """Independently recalculate every derived pixel and recorded hash; read-only."""
    import numpy as np
    from PIL import Image

    root, contract, source, mask = _context(run, packet)
    step = resolve_in_workspace(root, step)
    proof = attestation.get("postprocess")
    if not isinstance(proof, dict) or proof.get("kind") != "sha_bound_strict_composite":
        raise ValidationError("native strict derivation proof missing or malformed")
    raw = step / "native-generated.png"
    output = step / "generated.png"
    report = step / "precision-compose-report.json"
    if any(not f.is_file() or f.is_symlink() for f in (raw, output, report)):
        raise ValidationError("native, derived PNG or compose receipt missing or symlinked")
    expected = _proof(root, step, contract, source, mask)
    if proof != expected:
        raise ValidationError("native strict derived evidence SHA or lineage mismatch")
    if (receipt.get("result_sha256") != expected["result_sha256"]
            or (receipt.get("result") or {}).get("path") != expected["result_path"]
            or (receipt.get("host_attestation") or {}).get("postprocess") != proof
            or attestation.get("result_sha256") != expected["native_sha256"]):
        raise ValidationError("native source and derived output receipt binding invalid")
    with Image.open(source) as im:
        im.load()
        if im.format != "PNG" or im.mode not in ("RGB", "RGBA"):
            raise ValidationError("strict source RGB/RGBA PNG required")
        mode, size, icc = im.mode, im.size, im.info.get("icc_profile")
        original = np.asarray(im, dtype=np.uint8).copy()
    with Image.open(raw) as im:
        im.load()
        if (im.format, im.mode, im.size, im.info.get("icc_profile")) != ("PNG", mode, size, icc):
            raise ValidationError("native candidate dimensions/mode/ICC not comparable")
        generated = np.asarray(im, dtype=np.uint8).copy()
    with Image.open(output) as im:
        im.load()
        if (im.format, im.mode, im.size, im.info.get("icc_profile")) != ("PNG", mode, size, icc):
            raise ValidationError("derived candidate dimensions/mode/ICC not comparable")
        derived = np.asarray(im, dtype=np.uint8).copy()
    with Image.open(mask) as im:
        im.load()
        if im.format != "PNG" or im.mode != "L" or im.size != size:
            raise ValidationError("approved binary mask geometry is not comparable")
        protect = np.asarray(im, dtype=np.uint8)
    if not np.all((protect == 0) | (protect == 255)):
        raise ValidationError("native strict mask must be exactly binary")
    height, width = original.shape[:2]
    targets = np.zeros((height, width), dtype=bool)
    for item in contract["targets"]:
        x0, y0, x1, y1 = _pixel_rect(item["bbox"], width, height)
        targets[y0:y1, x0:x1] = True
    editable = targets & (protect == 0)
    verify_required_edit_points(contract, editable)
    if not editable.any():
        raise ValidationError("native strict contract has no editable pixels")
    recalculated = original.copy()
    recalculated[editable] = generated[editable]
    if not np.array_equal(derived, recalculated):
        raise ValidationError("derived pixels differ from deterministic native/mask composite")
    changed = int(np.any(derived != original, axis=2)[editable].sum())
    if changed == 0:
        raise ValidationError("strict native edit has no effective target modification")
    report_check = _verify_compose_report(
        report,
        {"source": expected["source_sha256"], "candidate": expected["native_sha256"],
         "composite": expected["result_sha256"], "mask": expected["mask_sha256"]},
        expected["contract_sha256"], width, height, mode, changed,
    )
    if report_check["status"] != "SHA_BOUND_REPORT_MATCH":
        raise ValidationError("strict native compose report disagrees with recomputed pixels")
    return {
        "status": "PASS",
        "native_source_sha256": expected["native_sha256"],
        "derived_sha256": expected["result_sha256"],
        "changed_editable_pixels": changed,
        "protected_pixel_mismatches": 0,
        "artistic_approval": "NOT_VERIFIED",
    }

