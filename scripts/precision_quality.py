#!/usr/bin/env python3
"""v0.12 technical A/B image-quality evidence; NEVER an independent art PASS.

Given an approved source, raw ImageGen candidate, strict composite and SHA-pinned
ROI/mask contract, compare real decoded pixels. This does NOT attest ImageGen
origin, approve spatial alignment, certify rights, or approve artistic seams.
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
from typing import Any

from artifact_integrity import canonical_json_bytes, resolve_in_workspace, sha256_bytes, sha256_file
from region_quality import _pixel_rect, validate_region_contract
from validate_project import ValidationError, load_document


THRESHOLDS = (0, 5, 15, 30)
WINDOW = 7


def _box_mean(values: Any, size: int) -> Any:
    """Uniform-window mean via integral image, including image boundaries."""
    import numpy as np

    pad = size // 2
    area = np.pad(values.astype(np.float64), ((pad, pad), (pad, pad)), mode="edge")
    integral = np.pad(area, ((1, 0), (1, 0)), mode="constant").cumsum(0).cumsum(1)
    return (integral[size:, size:] - integral[:-size, size:]
            - integral[size:, :-size] + integral[:-size, :-size]) / (size * size)


def _ssim_map(rgb_a: Any, rgb_b: Any) -> Any:
    """Seven-pixel uniform-window luminance SSIM; diagnostic, not art approval."""
    import numpy as np

    weights = np.asarray((.2126, .7152, .0722), dtype=np.float64)
    a = rgb_a.astype(np.float64) @ weights
    b = rgb_b.astype(np.float64) @ weights
    mean_a, mean_b = _box_mean(a, WINDOW), _box_mean(b, WINDOW)
    variance_a = np.maximum(0.0, _box_mean(a * a, WINDOW) - mean_a * mean_a)
    variance_b = np.maximum(0.0, _box_mean(b * b, WINDOW) - mean_b * mean_b)
    covariance = _box_mean(a * b, WINDOW) - mean_a * mean_b
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    return np.clip(((2 * mean_a * mean_b + c1) * (2 * covariance + c2)) /
                   ((mean_a ** 2 + mean_b ** 2 + c1) *
                    (variance_a + variance_b + c2)), -1.0, 1.0)


def _lab_srgb(rgb: Any) -> Any:
    """Convert assumed sRGB uint8 pixels to CIE Lab D65 for DeltaE76."""
    import numpy as np

    scaled = rgb.astype(np.float32) / 255.0
    linear = np.where(scaled <= .04045, scaled / 12.92,
                      ((scaled + .055) / 1.055) ** 2.4)
    matrix = np.array(((.4124564, .3575761, .1804375),
                       (.2126729, .7151522, .0721750),
                       (.0193339, .1191920, .9503041)), dtype=np.float32)
    xyz = (linear @ matrix.T) / np.array((.95047, 1.0, 1.08883), dtype=np.float32)
    delta = 6 / 29
    f = np.where(xyz > delta ** 3, np.cbrt(xyz),
                 xyz / (3 * delta ** 2) + 4 / 29)
    return np.stack((116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])), axis=-1)


def _read_png(path: Path) -> tuple[Any, tuple[int, int], str, bytes | None]:
    import numpy as np
    from PIL import Image

    try:
        with Image.open(path) as image:
            image.load()
            if image.format != "PNG" or image.mode not in {"RGB", "RGBA"}:
                raise ValidationError(f"{path.name}: expected 8-bit RGB/RGBA PNG")
            return (np.asarray(image, dtype=np.uint8).copy(), image.size,
                    image.mode, image.info.get("icc_profile"))
    except (OSError, ValueError) as exc:
        raise ValidationError(f"cannot decode {path.name} as PNG") from exc


def _seam_excess(original: Any, composed: Any, editable: Any) -> tuple[Any, dict[str, Any]]:
    """Excess maximum-channel RGB gradient over pairs crossing strict boundaries."""
    import numpy as np

    heat = np.zeros(editable.shape, dtype=np.uint8)
    jumps: list[Any] = []
    for axis in (0, 1):
        if axis == 1:
            p, q = np.s_[:, :-1], np.s_[:, 1:]
        else:
            p, q = np.s_[:-1, :], np.s_[1:, :]
        crossing = editable[p] ^ editable[q]
        if not bool(crossing.any()):
            continue
        first = np.abs(composed[p][..., :3].astype(np.int16) -
                       composed[q][..., :3].astype(np.int16)).max(axis=2)
        baseline = np.abs(original[p][..., :3].astype(np.int16) -
                          original[q][..., :3].astype(np.int16)).max(axis=2)
        excess = np.maximum(first - baseline, 0).astype(np.uint8)
        jumps.extend(excess[crossing].tolist())
        for part in (p, q):
            heat[part] = np.maximum(heat[part], np.where(crossing, excess, 0))
    return heat, {
        "crossing_pairs": len(jumps),
        "excess_max_rgb_gradient": int(max(jumps, default=0)),
        "excess_mean_rgb_gradient": (round(float(sum(jumps) / len(jumps)), 4)
                                     if jumps else 0.0),
        "visual_seam_review_required": True,
    }


def _alpha_seam_excess(original: Any, composed: Any, editable: Any) -> tuple[Any | None, dict[str, Any]]:
    """RGBA boundary alpha discontinuity diagnostic, not a blending/art PASS."""
    import numpy as np

    if original.shape[2] != 4:
        return None, {"applicable": False}
    heat = np.zeros(editable.shape, dtype=np.uint8)
    jumps: list[Any] = []
    for axis in (0, 1):
        if axis == 1:
            p, q = np.s_[:, :-1], np.s_[:, 1:]
        else:
            p, q = np.s_[:-1, :], np.s_[1:, :]
        crossing = editable[p] ^ editable[q]
        if not bool(crossing.any()):
            continue
        new_jump = np.abs(composed[p][..., 3].astype(np.int16) -
                          composed[q][..., 3].astype(np.int16))
        old_jump = np.abs(original[p][..., 3].astype(np.int16) -
                          original[q][..., 3].astype(np.int16))
        excess = np.maximum(0, new_jump - old_jump).astype(np.uint8)
        jumps.extend(excess[crossing].tolist())
        for part in (p, q):
            heat[part] = np.maximum(heat[part], np.where(crossing, excess, 0))
    return heat, {
        "applicable": True, "boundary_pairs": len(jumps),
        "max_excess_alpha_jump": int(max(jumps, default=0)),
        "mean_excess_alpha_jump": (round(float(sum(jumps) / len(jumps)), 4)
                                   if jumps else 0.0),
        "visual_alpha_halo_review_required": True,
    }


def _measure(reference: Any, image: Any, regions: dict[str, Any],
             ssim: Any, delta_e: Any | None) -> dict[str, Any]:
    import numpy as np

    diff = np.abs(reference.astype(np.int16) - image.astype(np.int16))
    pixel_diff = diff.max(axis=2)
    metrics: dict[str, Any] = {}
    for name, selected in regions.items():
        size = int(selected.sum())
        if not size:
            metrics[name] = {"pixels": 0, "status": "NOT_APPLICABLE"}
            continue
        part = pixel_diff[selected]
        counts = {str(t): {"changed_pixels": int((part > t).sum()),
                           "changed_fraction": round(float((part > t).mean()), 7)}
                  for t in THRESHOLDS}
        metric: dict[str, Any] = {
            "pixels": size,
            "thresholds_max_channel": counts,
            "mean_absolute_rgb_change": round(float(diff[..., :3][selected].mean()), 4),
            "ssim_luma_window7_mean": round(float(ssim[selected].mean()), 6),
        }
        if delta_e is not None:
            metric["delta_e76_srgb_mean"] = round(float(delta_e[selected].mean()), 4)
            metric["delta_e76_srgb_p95"] = round(float(np.percentile(delta_e[selected], 95)), 4)
        if image.shape[2] == 4:
            alpha_change = np.abs(reference[..., 3].astype(np.int16) -
                                  image[..., 3].astype(np.int16))[selected]
            metric["alpha_changed_pixels"] = int((alpha_change > 0).sum())
            metric["alpha_abs_change_mean"] = round(float(alpha_change.mean()), 4)
        else:
            metric["alpha_applicable"] = False
        metrics[name] = metric
    return metrics


def _png_bytes(grayscale: Any) -> bytes:
    from PIL import Image

    file = io.BytesIO()
    Image.fromarray(grayscale).save(file, format="PNG")
    return file.getvalue()


def _exclusive_bytes(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _verify_compose_report(path: Path, hashes: dict[str, str],
                           contract_sha: str, width: int, height: int,
                           image_mode: str, changed_pixels: int) -> dict[str, Any]:
    """Bind a precision-compose report to measured files, not to model identity.

    The report remains self-reported and cannot establish native ImageGen origin,
    actual artwork semantics, or human signoff.
    """
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValidationError("composition report is missing or invalid JSON") from exc
    if not isinstance(record, dict):
        raise ValidationError("composition report must be a JSON object")
    required = {
        "schema_version": 1,
        "state": "CANDIDATE_NEEDS_VISUAL_REVIEW",
        "original_sha256": hashes["source"],
        "candidate_sha256": hashes["candidate"],
        "mask_sha256": hashes["mask"],
        "output_sha256": hashes["composite"],
        "contract_sha256": contract_sha,
        "width": width,
        "height": height,
        "image_mode": image_mode,
        "changed_editable_pixels": changed_pixels,
        "outside_target_pixel_mismatches": 0,
        "protected_pixel_mismatches": 0,
        "visual_seam_review_required": True,
        "commercial_release_certified": False,
        "steam_approved": False,
    }
    for key, expected in required.items():
        actual = record.get(key)
        if type(actual) is not type(expected) or actual != expected:
            raise ValidationError(f"composition report {key} disagrees with measured evidence")
    return {
        "status": "SHA_BOUND_REPORT_MATCH",
        "sha256": sha256_file(path),
        "provenance_note": "Composition JSON may be independently reproduced; native origin and visual QA not proven.",
    }


def build_quality_report(reference: Path, candidate: Path, composite: Path,
                         contract: dict[str, Any], workspace_root: Path,
                         report_path: Path, heatmap_dir: Path,
                         *, compose_report: Path | None = None) -> dict[str, Any]:
    """Produce immutable measurement evidence, never an artistic/commercial PASS."""
    import numpy as np

    validate_region_contract({"operation": "local_edit", "region_contract": contract},
                             "precision quality")
    policy = contract.get("strict_mask")
    if not isinstance(policy, dict):
        raise ValidationError("quality A/B needs an SHA-pinned strict_mask")
    root = Path(workspace_root).expanduser().resolve()
    source = resolve_in_workspace(root, reference)
    raw = resolve_in_workspace(root, candidate)
    merged = resolve_in_workspace(root, composite)
    mask_path = resolve_in_workspace(root, policy["path"])
    report = resolve_in_workspace(root, report_path)
    heatmaps = resolve_in_workspace(root, heatmap_dir)
    composition_path = (resolve_in_workspace(root, compose_report)
                        if compose_report is not None else None)
    inputs = {source, raw, merged, mask_path}
    if len(inputs) != 4:
        raise ValidationError("source/candidate/composite/mask must be four distinct files")
    if (report in inputs or heatmaps in inputs or report == heatmaps
            or report.is_relative_to(heatmaps) or heatmaps.is_relative_to(report)
            or report.suffix.lower() != ".json"):
        raise ValidationError("output collides with source inputs or report directory")
    if composition_path is not None and (
            composition_path in inputs or composition_path == report
            or composition_path == heatmaps or composition_path.is_relative_to(heatmaps)
            or composition_path.suffix.lower() != ".json"):
        raise ValidationError("composition report path collides with input/output files")
    if report.exists() or report.is_symlink() or heatmaps.exists() or heatmaps.is_symlink():
        raise ValidationError("existing report/heatmap path must not be overwritten")

    hashes = {key: sha256_file(path) for key, path in (
        ("source", source), ("candidate", raw), ("composite", merged), ("mask", mask_path))}
    if policy["reference_sha256"] != hashes["source"] or policy["sha256"] != hashes["mask"]:
        raise ValidationError("source or mask digest disagrees with approved contract")
    original, size, mode, profile = _read_png(source)
    generated, size_raw, mode_raw, profile_raw = _read_png(raw)
    composed, size_out, mode_out, profile_out = _read_png(merged)
    if ((size_raw, mode_raw, profile_raw) != (size, mode, profile) or
            (size_out, mode_out, profile_out) != (size, mode, profile)):
        raise ValidationError("NOT_COMPARABLE: size, pixel mode or ICC profile differs")
    from PIL import Image
    with Image.open(mask_path) as im:
        im.load()
        if im.format != "PNG" or im.mode != "L" or im.size != size:
            raise ValidationError("strict mask must be same-size grayscale PNG")
        protect = np.asarray(im, dtype=np.uint8).copy()
    if not bool(np.all((protect == 0) | (protect == 255))):
        raise ValidationError("strict mask must be binary 0 or 255")
    width, height = size
    target = np.zeros((height, width), dtype=bool)
    for region in contract["targets"]:
        x0, y0, x1, y1 = _pixel_rect(region["bbox"], width, height)
        target[y0:y1, x0:x1] = True
    editable = target & (protect == 0)
    if not bool(editable.any()):
        raise ValidationError("strict contract has no editable pixels")
    locked = ~editable
    composite_delta = np.any(original != composed, axis=2)
    protect_changed = int((composite_delta & (protect == 255)).sum())
    outside_changed = int((composite_delta & ~target).sum())
    locked_changed = int((composite_delta & locked).sum())
    edit_changed = int((composite_delta & editable).sum())
    raw_edit_mismatch = int((np.any(composed != generated, axis=2) & editable).sum())
    composition_evidence = (
        _verify_compose_report(
            composition_path, hashes, sha256_bytes(canonical_json_bytes(contract)),
            width, height, mode, edit_changed)
        if composition_path is not None else {"status": "NOT_SUPPLIED"}
    )
    if profile is None:
        color_a = _lab_srgb(original[..., :3])
        raw_de = np.linalg.norm(color_a - _lab_srgb(generated[..., :3]), axis=2)
        composed_de = np.linalg.norm(color_a - _lab_srgb(composed[..., :3]), axis=2)
        color_note = "DeltaE76 assumes untagged PNG input is sRGB/D65; NOT color-managed."
    else:
        raw_de, composed_de = None, None
        color_note = "ICC profile present: untransformed DeltaE76 omitted; color QA is NOT_VERIFIABLE."
    masks = {"editable": editable, "strictly_locked": locked,
             "outside_target": ~target, "mask_protected": protect == 255}
    candidate_metrics = _measure(original, generated, masks,
                                 _ssim_map(original[..., :3], generated[..., :3]), raw_de)
    composite_metrics = _measure(original, composed, masks,
                                 _ssim_map(original[..., :3], composed[..., :3]), composed_de)
    seam_image, seam = _seam_excess(original, composed, editable)
    alpha_image, alpha_seam = _alpha_seam_excess(original, composed, editable)
    state = ("BLOCKED" if (locked_changed != 0 or edit_changed == 0 or raw_edit_mismatch != 0)
             else "MEASURED_NEEDS_VISUAL_REVIEW")
    result: dict[str, Any] = {
        "schema_version": 1, "state": state,
        "comparison_status": "NOT_COMPARABLE_UNTIL_SPATIAL_ALIGNMENT_REVIEW",
        "native_imagegen_provenance": "NOT_VERIFIED_BY_THIS_TOOL",
        "artistic_visual_qa": "REQUIRED", "geometry_material_approval": "NOT_VERIFIED",
        "rights_review": "REQUIRED", "unity_player_verification": "NOT_VERIFIED",
        "steam_approved": False, "commercial_release_certified": False,
        "source_sha256": hashes["source"], "raw_candidate_sha256": hashes["candidate"],
        "composited_sha256": hashes["composite"], "mask_sha256": hashes["mask"],
        "contract_sha256": sha256_bytes(canonical_json_bytes(contract)),
        "composition_evidence": composition_evidence,
        "width": width, "height": height, "pixel_mode": mode,
        "strict_preservation": {
            "locked_pixels": int(locked.sum()), "locked_mismatches": locked_changed,
            "outside_target_mismatches": outside_changed,
            "mask_protected_mismatches": protect_changed,
            "editable_pixels": int(editable.sum()), "changed_editable_pixels": edit_changed,
            "candidate_pixel_mismatches_in_editable": raw_edit_mismatch,
            "objective_gate": ("PASS" if locked_changed == 0 and edit_changed > 0
                               and raw_edit_mismatch == 0 else "FAIL"),
        },
        "thresholds": list(THRESHOLDS), "ssim_method": "uniform_7x7_luminance",
        "color_metric_note": color_note,
        "raw_image": candidate_metrics, "composited_image": composite_metrics,
        "seam_diagnostics": seam, "alpha_boundary_diagnostics": alpha_seam,
        "limitations": [
            "Numeric pixel measurements do NOT confirm that model subjects remain aligned.",
            "Seam heatmaps are risk indicators; independent visual review is mandatory.",
            "An exact mask does not certify artistic geometry, material, rights or Unity output.",
            "No native ImageGen provenance is asserted from a locally supplied candidate."
        ],
    }
    # Outputs are new files only. Interrupted partial evidence requires manual reconciliation.
    heatmaps.mkdir(parents=True, exist_ok=False)
    artifacts = {
        "raw_diff_max_channel.png": np.abs(
            original.astype(np.int16) - generated.astype(np.int16)).max(axis=2).astype(np.uint8),
        "composite_diff_max_channel.png": np.abs(
            original.astype(np.int16) - composed.astype(np.int16)).max(axis=2).astype(np.uint8),
        "seam_excess.png": seam_image,
        "editable_mask.png": (editable.astype(np.uint8) * 255),
    }
    if composed_de is not None:
        artifacts["composite_delta_e76.png"] = np.clip(composed_de * 5.0, 0, 255).astype(np.uint8)
    if alpha_image is not None:
        artifacts["alpha_seam_excess.png"] = alpha_image
    result["heatmaps"] = {}
    for filename, image in artifacts.items():
        payload = _png_bytes(image)
        path = heatmaps / filename
        _exclusive_bytes(path, payload)
        result["heatmaps"][filename] = {
            "path": str(path.relative_to(root)),
            "sha256": sha256_bytes(payload)
        }
    report.parent.mkdir(parents=True, exist_ok=True)
    _exclusive_bytes(report, (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("workspace-root", "edit", "reference", "candidate",
                 "composite", "report", "heatmap-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--compose-report", type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.workspace_root.expanduser().resolve()
        path = resolve_in_workspace(root, args.edit)
        edit = load_document(path).data
        report = build_quality_report(args.reference, args.candidate,
                                      args.composite, edit["region_contract"],
                                      root, args.report, args.heatmap_dir,
                                      compose_report=args.compose_report)
        print(json.dumps({"state": report["state"], "report": str(args.report)}))
        return 0 if report["state"] == "MEASURED_NEEDS_VISUAL_REVIEW" else 2
    except (ValidationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
