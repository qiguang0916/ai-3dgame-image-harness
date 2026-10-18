#!/usr/bin/env python3
"""Deterministic game-image PNG format/size/transparency acceptance checks."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any

from artifact_integrity import sha256_file
from validate_project import ValidationError, load_document


def inspect_output(path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValidationError("Pillow required for technical image QA; cannot claim PASS") from exc
    path=Path(path)
    with Image.open(path) as image:
        image.load()
        fmt=image.format
        width,height=image.size
        rgba=image.convert("RGBA")
        alpha=rgba.getchannel("A").getextrema()
    failures=[]
    if fmt!="PNG":
        failures.append("Only PNG is guaranteed for production acceptance")
    if spec.get("expected_size"):
        expected=tuple(map(int,spec["expected_size"].split("x")))
        if (width,height)!=expected:
            failures.append(f"Expected {expected[0]}x{expected[1]} but observed {width}x{height}")
    if "require_transparency" in spec:
        has_transparency=alpha[0]<255
        if has_transparency != spec["require_transparency"]:
            failures.append("Alpha transparency is inconsistent with require_transparency")
    return {
        "schema_version":1,
        "status":"FAIL" if failures else "PASS",
        "path":str(path.resolve()),
        "sha256":sha256_file(path),
        "format":fmt,
        "width":width,
        "height":height,
        "has_transparency":alpha[0]<255,
        "failures":failures,
    }


def verify_output_gate(spec: dict[str,Any], image: Path,
                       reported_status: str) -> dict[str,Any]:
    measured=inspect_output(image,spec)
    if measured["status"]=="FAIL" and reported_status!="FAIL":
        raise ValidationError("technical output QA measured FAIL; cannot report PASS")
    if measured["status"]=="PASS" and reported_status not in {"PASS","FAIL"}:
        raise ValidationError("technical output gate must have a supported status")
    return measured


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image",type=Path,required=True)
    parser.add_argument("--edit",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        data=load_document(args.edit).data
        if not isinstance(data.get("output"),dict):
            raise ValidationError("edit request has no output technical contract")
        if args.out.exists():
            raise ValidationError("refusing to overwrite existing asset report")
        result=inspect_output(args.image,data["output"])
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open("x",encoding="utf8") as fh:
            json.dump(result,fh,indent=2)
            fh.write("\n")
        print(json.dumps({"status":result["status"],"report":str(args.out)}))
        return 0 if result["status"]=="PASS" else 1
    except (OSError,ValueError,ValidationError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
