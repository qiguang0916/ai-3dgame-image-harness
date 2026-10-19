#!/usr/bin/env python3
"""Measured editing-region QA; never generates or repairs an image.

The only image operations here are reading actual pixels and writing QA artefacts.
No AI model and no OpenAI API credentials are required.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from artifact_integrity import canonical_json_bytes, sha256_bytes, sha256_file
from validate_project import ValidationError, load_document


def _bbox(value: Any, where: str) -> tuple[float, float, float, float]:
    if (
        not isinstance(value, list) or len(value) != 4 or
        any(isinstance(x, bool) or not isinstance(x, (float, int))
            or not math.isfinite(x) for x in value)
    ):
        raise ValidationError(f"{where}: bbox must contain four finite normalized coordinates")
    x0, y0, x1, y1 = [float(x) for x in value]
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValidationError(f"{where}: bbox must satisfy 0<=x0<x1<=1 and 0<=y0<y1<=1")
    return x0, y0, x1, y1


def _overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _fraction(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValidationError(f"{where}: expected finite number in 0..1")
    if not 0 <= value <= 1:
        raise ValidationError(f"{where}: expected finite number in 0..1")
    return float(value)


def validate_region_contract(edit: dict[str, Any], where: str) -> None:
    contract = edit.get("region_contract")
    if contract is None:
        return
    if edit.get("operation") == "create":
        raise ValidationError(f"{where}: region_contract requires an existing edit target")
    if not isinstance(contract, dict):
        raise ValidationError(f"{where}: region_contract must be a table")
    if contract.get("mode") not in {"report", "enforce"}:
        raise ValidationError(f"{where}: region_contract.mode must be report or enforce")
    threshold = contract.get("pixel_threshold")
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 255:
        raise ValidationError(f"{where}: pixel_threshold must be integer 0..255")
    if contract["mode"] == "enforce":
        _fraction(contract.get("max_outside_changed_fraction"),
                  f"{where}: max_outside_changed_fraction")
    elif "max_outside_changed_fraction" in contract:
        _fraction(contract["max_outside_changed_fraction"],
                  f"{where}: max_outside_changed_fraction")
    if "min_target_changed_fraction" in contract:
        _fraction(contract["min_target_changed_fraction"],
                  f"{where}: min_target_changed_fraction")
    targets = contract.get("targets", [])
    protected = contract.get("protected", [])
    if not isinstance(targets, list) or not isinstance(protected, list) or not (targets or protected):
        raise ValidationError(f"{where}: targets/protected must be arrays, at least one region")
    names: set[str] = set()
    target_boxes: list[tuple[float, ...]] = []
    for role, items in (("targets", targets), ("protected", protected)):
        for i, obj in enumerate(items):
            point = f"{where}: region_contract.{role}[{i}]"
            if not isinstance(obj, dict):
                raise ValidationError(f"{point}: expected table")
            ident = obj.get("id")
            if not isinstance(ident, str) or not ident.strip() or ident in names:
                raise ValidationError(f"{point}: expected unique nonempty id")
            names.add(ident)
            box = _bbox(obj.get("bbox"), point)
            if role == "targets":
                target_boxes.append(box)
            else:
                _fraction(obj.get("max_changed_fraction", 1.0),
                          f"{point}: max_changed_fraction")
                if any(_overlap(box, target) for target in target_boxes):
                    raise ValidationError(f"{point}: protected box overlaps an editable target")
    # Also catch a target added after protected definitions; this is independent
    # of the order in which input TOML tables were written.
    for item in protected:
        if any(_overlap(_bbox(item["bbox"], "protected"), t) for t in target_boxes):
            raise ValidationError(f"{where}: protected box overlaps an editable target")
    if targets and contract["mode"] == "enforce":
        area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in target_boxes)
        if area >= .95:
            raise ValidationError(f"{where}: editable target coverage is too broad to enforce preservation")

    strict = contract.get("strict_mask")
    if strict is not None:
        if contract["mode"] != "enforce" or not targets:
            raise ValidationError(f"{where}: strict_mask requires enforce mode and targets")
        if not isinstance(strict, dict) or set(strict) != {"path", "sha256", "reference_sha256"}:
            raise ValidationError(f"{where}: strict_mask requires path plus two SHA-256 digests")
        raw = strict["path"]
        if (not isinstance(raw, str) or not raw.strip() or
                Path(raw).is_absolute() or ".." in Path(raw).parts or
                Path(raw).suffix.lower() != ".png"):
            raise ValidationError(f"{where}: strict_mask.path must be workspace-relative PNG")
        import re
        for field in ("sha256", "reference_sha256"):
            value = strict[field]
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValidationError(f"{where}: strict_mask.{field} must be SHA-256")


def _pixel_rect(bbox: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    x0,y0,x1,y1 = bbox
    a,b = math.floor(x0*width), math.floor(y0*height)
    c,d = math.ceil(x1*width), math.ceil(y1*height)
    return max(0,a), max(0,b), min(width,c), min(height,d)


def compare_images(reference: Path, result: Path, contract: dict[str, Any],
                   *, diff_image: Path | None = None) -> dict[str, Any]:
    validate_region_contract({"operation": "local_edit", "region_contract": contract},
                             "region_quality")
    try:
        import numpy as np
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise ValidationError("region QA requires installed Pillow and numpy; cannot claim PASS") from exc

    reference, result = Path(reference), Path(result)
    with Image.open(reference) as source:
        source.load()
        baseline = source.convert("RGBA")
    with Image.open(result) as output:
        output.load()
        current = output.convert("RGBA")
    if baseline.size != current.size:
        return {
            "status": "NOT_VERIFIABLE", "reason": "image dimensions do not match",
            "reference_sha256": sha256_file(reference),
            "result_sha256": sha256_file(result),
            "contract_sha256": sha256_bytes(canonical_json_bytes(contract)),
            "reference_dimensions": list(baseline.size),
            "result_dimensions": list(current.size),
        }

    before = np.asarray(baseline).astype(np.int16)
    after = np.asarray(current).astype(np.int16)
    delta = np.abs(before-after)
    changed = np.max(delta, axis=2) > contract["pixel_threshold"]
    height, width = changed.shape
    target_mask_img = Image.new("1",(width,height),0)
    draw = ImageDraw.Draw(target_mask_img)
    for item in contract.get("targets",[]):
        x0,y0,x1,y1=_pixel_rect(item["bbox"],width,height)
        draw.rectangle((x0,y0,x1-1,y1-1), fill=1)
    target_mask = np.asarray(target_mask_img,dtype=bool)
    outside = ~target_mask

    def metrics(mask: Any) -> dict[str, Any]:
        count = int(mask.sum())
        changed_count = int((changed & mask).sum())
        return {
            "pixels": count,
            "changed_pixels": changed_count,
            "changed_fraction": round(changed_count/count,7) if count else None,
            "mean_absolute_channel_change": round(float(delta[mask].mean()),3) if count else None,
        }

    targets = []
    for item in contract.get("targets",[]):
        mask = np.zeros((height,width),dtype=bool)
        x0,y0,x1,y1=_pixel_rect(item["bbox"],width,height)
        mask[y0:y1,x0:x1]=True
        targets.append({"id":item["id"],"bbox":item["bbox"],**metrics(mask)})

    protected = []
    fails = []
    for item in contract.get("protected",[]):
        mask = np.zeros((height,width),dtype=bool)
        x0,y0,x1,y1=_pixel_rect(item["bbox"],width,height)
        mask[y0:y1,x0:x1]=True
        result_metrics = metrics(mask)
        max_changed = item.get("max_changed_fraction",1.0)
        violates = (result_metrics["changed_fraction"] is None or
                    result_metrics["changed_fraction"] > max_changed)
        if violates and contract["mode"] == "enforce":
            fails.append(f"protected region '{item['id']}' exceeds {max_changed} changed fraction")
        protected.append({
            "id":item["id"], "bbox":item["bbox"],
            "max_changed_fraction":max_changed,
            **result_metrics,
        })

    outside_metrics = metrics(outside)
    max_outside = contract.get("max_outside_changed_fraction")
    if (contract["mode"]=="enforce" and max_outside is not None
        and (outside_metrics["changed_fraction"] is None or
             outside_metrics["changed_fraction"] > max_outside)):
        fails.append(f"outside editable regions changed more than {max_outside}")
    minimum = contract.get("min_target_changed_fraction")
    if contract["mode"]=="enforce" and minimum is not None:
        observed = metrics(target_mask)["changed_fraction"]
        if observed is None or observed < minimum:
            fails.append(f"target area changed less than required {minimum}")

    if diff_image is not None:
        diff_image = Path(diff_image)
        if diff_image.exists():
            raise ValidationError(f"refusing to overwrite existing diff image: {diff_image}")
        diff_image.parent.mkdir(parents=True,exist_ok=True)
        heatmap = Image.fromarray(
            np.uint8(np.minimum(np.max(delta,axis=2)*5, 255)),mode="L"
        )
        heatmap.save(diff_image)

    return {
        "schema_version":1,
        "status": ("FAIL" if fails else "PASS") if contract["mode"]=="enforce" else "INFO",
        "mode":contract["mode"],
        "reference_sha256":sha256_file(reference),
        "result_sha256":sha256_file(result),
        "contract_sha256":sha256_bytes(canonical_json_bytes(contract)),
        "pixel_threshold":contract["pixel_threshold"],
        "width":width, "height":height,
        "targets":targets, "protected":protected,
        "outside_targets":outside_metrics,
        "max_outside_changed_fraction":max_outside,
        "failures":fails,
    }


def verify_region_gate(contract: dict[str, Any], reference: Path, result: Path,
                       reported_status: str) -> dict[str, Any]:
    measured = compare_images(reference, result, contract)
    if contract["mode"] == "enforce":
        if measured["status"] == "NOT_VERIFIABLE":
            if reported_status != "NOT_VERIFIABLE":
                raise ValidationError("region QA was NOT_VERIFIABLE; cannot claim another status")
        elif measured["status"] == "FAIL" and reported_status != "FAIL":
            raise ValidationError("region QA measured FAIL; cannot report PASS")
        elif measured["status"] == "PASS" and reported_status not in {"PASS","FAIL"}:
            raise ValidationError("region QA passed; expected PASS or conservative FAIL")
    return measured


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edit",required=True,type=Path)
    parser.add_argument("--reference",required=True,type=Path)
    parser.add_argument("--result",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--diff-image",type=Path)
    args=parser.parse_args(argv)
    try:
        edit=load_document(args.edit).data
        contract=edit.get("region_contract")
        if not contract:
            raise ValidationError("edit request has no region_contract")
        report=compare_images(args.reference,args.result,contract,diff_image=args.diff_image)
        if args.output.exists():
            raise ValidationError(f"refusing to overwrite existing report: {args.output}")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf8") as fh:
            json.dump(report,fh,indent=2)
            fh.write("\n")
        print(json.dumps({"status":report["status"],"report":str(args.output),
                          "failures":report.get("failures",[])},ensure_ascii=False))
        return 0 if report["status"] in {"PASS","INFO"} else 1
    except (ValidationError,OSError,ValueError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
