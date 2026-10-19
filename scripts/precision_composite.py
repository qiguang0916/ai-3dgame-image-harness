#!/usr/bin/env python3
"""v0.12 opt-in exact pixel preservation. No image model or Master promotion."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
from typing import Any

from artifact_integrity import resolve_in_workspace, sha256_bytes, sha256_file
from region_quality import _pixel_rect, validate_region_contract
from runtime_preflight import validate_image_file
from validate_project import ValidationError, load_document, validate_document


def strict_composite(reference: Path, candidate: Path, contract: dict[str, Any],
                     workspace_root: Path, output: Path, report: Path) -> dict[str, Any]:
    """Replace only allowed ROI pixels with model output; preserve others exactly.

    Images must share identical pixel coordinates, size, mode and ICC profile.
    Independent visual seam/game-art approval remains REQUIRED.
    """
    root = Path(workspace_root).expanduser().resolve()
    validate_region_contract({"operation": "local_edit", "region_contract": contract},
                             "strict composite")
    policy = contract.get("strict_mask")
    if not isinstance(policy, dict):
        raise ValidationError("strict composite requires a SHA-bound strict_mask")
    source = resolve_in_workspace(root, reference)
    generated = resolve_in_workspace(root, candidate)
    mask_path = resolve_in_workspace(root, policy["path"])
    dest = resolve_in_workspace(root, output)
    report_path = resolve_in_workspace(root, report)

    inputs = {source, generated, mask_path}
    if len(inputs) != 3:
        raise ValidationError("source, candidate and mask must be distinct files")
    if (dest == report_path or dest in inputs or report_path in inputs
            or dest.suffix.lower() != ".png" or report_path.suffix.lower() != ".json"):
        raise ValidationError("invalid or colliding precision artifact paths")
    if dest.exists() or dest.is_symlink() or report_path.exists() or report_path.is_symlink():
        raise ValidationError("existing output or report must never be overwritten")

    for name, path in (("reference", source), ("candidate", generated), ("mask", mask_path)):
        valid, detail = validate_image_file(path)
        if not valid:
            raise ValidationError(f"{name} is not a valid PNG: {detail}")
    source_sha, generated_sha, mask_sha = (
        sha256_file(source), sha256_file(generated), sha256_file(mask_path))
    if policy["reference_sha256"] != source_sha or policy["sha256"] != mask_sha:
        raise ValidationError("reference/mask SHA does not match pinned contract")

    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise ValidationError("strict composite requires Pillow and NumPy") from exc

    with Image.open(source) as im:
        im.load()
        original_mode, original_size = im.mode, im.size
        original_profile = im.info.get("icc_profile")
        reference_data = np.asarray(im, dtype=np.uint8).copy()
    with Image.open(generated) as im:
        im.load()
        if im.mode != original_mode or im.size != original_size:
            raise ValidationError("candidate size/mode differs; NOT_COMPARABLE")
        if im.info.get("icc_profile") != original_profile:
            raise ValidationError("candidate ICC profile differs; NOT_COMPARABLE")
        candidate_data = np.asarray(im, dtype=np.uint8).copy()
    if original_mode not in {"RGB", "RGBA"}:
        raise ValidationError("source must be RGB or RGBA PNG")
    with Image.open(mask_path) as im:
        im.load()
        if im.mode != "L" or im.size != original_size:
            raise ValidationError("protection mask must be same-size 8-bit grayscale PNG")
        mask_data = np.asarray(im, dtype=np.uint8)
    if not np.all((mask_data == 0) | (mask_data == 255)):
        raise ValidationError("protection mask must contain binary 0 editable / 255 locked")

    height, width = reference_data.shape[:2]
    targets = np.zeros((height, width), dtype=bool)
    for item in contract["targets"]:
        x0, y0, x1, y1 = _pixel_rect(item["bbox"], width, height)
        targets[y0:y1, x0:x1] = True
    permitted = targets & (mask_data == 0)
    if not bool(permitted.any()):
        raise ValidationError("no editable target pixels remain after mask")
    composed = reference_data.copy()
    composed[permitted] = candidate_data[permitted]
    changed = np.any(composed != reference_data, axis=2)
    changed_count = int((changed & permitted).sum())
    if changed_count == 0:
        raise ValidationError("no target pixels changed; no candidate to review")
    outside_mismatch = int((changed & ~targets).sum())
    protected_mismatch = int((changed & (mask_data == 255)).sum())
    if outside_mismatch or protected_mismatch:
        raise ValidationError("pixel preservation invariants failed")

    interior = permitted.copy()
    interior[1:, :] &= permitted[:-1, :]
    interior[:-1, :] &= permitted[1:, :]
    interior[:, 1:] &= permitted[:, :-1]
    interior[:, :-1] &= permitted[:, 1:]
    boundary = permitted & ~interior
    boundary_changed = int((changed & boundary).sum())

    buf = io.BytesIO()
    params: dict[str, Any] = {"format": "PNG"}
    if original_profile:
        params["icc_profile"] = original_profile
    Image.fromarray(composed, mode=original_mode).save(buf, **params)
    payload = buf.getvalue()
    output_sha = sha256_bytes(payload)
    result = {
        "schema_version": 1, "state": "CANDIDATE_NEEDS_VISUAL_REVIEW",
        "original_sha256": source_sha, "candidate_sha256": generated_sha,
        "mask_sha256": mask_sha, "output_sha256": output_sha,
        "width": width, "height": height, "image_mode": original_mode,
        "editable_pixels": int(permitted.sum()),
        "changed_editable_pixels": changed_count,
        "outside_target_pixel_mismatches": outside_mismatch,
        "protected_pixel_mismatches": protected_mismatch,
        "boundary_pixels": int(boundary.sum()),
        "boundary_changed_pixels": boundary_changed,
        "visual_seam_review_required": True,
        "texture_and_geometry_approval": "NOT_VERIFIED",
        "commercial_release_certified": False, "steam_approved": False,
        "notes": [
            "Outside-ROI and protected pixels are copied exactly from the original.",
            "Pixel equality does not certify seams, lighting, geometry, rights or game quality.",
            "An independent visual QA and explicit Master approval are required."
        ],
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink() or report_path.exists() or report_path.is_symlink():
        raise ValidationError("concurrent evidence appeared; refusing overwrite")
    # Exclusive creation. If interrupted, partial evidence blocks retries until reconciled.
    with dest.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    if sha256_file(dest) != output_sha:
        raise ValidationError("written output differs; manual reconciliation required")
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("edit", "reference", "candidate", "workspace-root", "output", "report"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.workspace_root.expanduser().resolve()
        source = resolve_in_workspace(root, args.edit)
        document = load_document(source)
        validate_document(document.data, document.path)
        contract = document.data.get("region_contract")
        if not contract:
            raise ValidationError("edit must declare a region_contract")
        value = strict_composite(args.reference, args.candidate, contract, root,
                                 args.output, args.report)
        print(json.dumps(value, ensure_ascii=False))
        return 0
    except (ValidationError, OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"state": "BLOCKED",
                          "message": "Invalid mask/image/digest or output path; no overwrite."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
