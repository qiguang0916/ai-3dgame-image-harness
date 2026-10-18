#!/usr/bin/env python3
"""Fail-closed Steam art packaging gate; NOT a Steam approval or image model.

Distinguishes deterministic proof (hashes, dimensions, GLB named components,
view-image validity) from host- or human-reviewed evidence for actual game
visuals, legal rights and Unity integration. Never fabricates an approval.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

from artifact_integrity import sha256_file
from validate_project import ValidationError

REQUIRED_VIEW_NAMES = {"BROAD_A", "BROAD_B", "SPINE", "QUARTER"}
CAPSULE_DIMENSIONS = {
    "header": (920, 430),
    "small": (462, 174),
    "main": (1232, 706),
    "vertical": (748, 896),
    "library_capsule": (600, 900),
    "library_hero": (3840, 1240),
    "library_header": (920, 430),
}
KINDS = {
    "concept_reference", "ingame_3d_model", "ingame_2d_asset",
    "steam_store_capsule", "steam_gameplay_screenshot",
}


def _path(root: Path, raw: Any) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("missing relative evidence path")
    base = root.resolve()
    p = (base / raw).resolve()
    if not p.is_relative_to(base):
        raise ValueError(f"evidence path escapes package root: {raw}")
    return p


def _file(root: Path, evidence: Any, label: str, problems: list[str]) -> Path | None:
    if not isinstance(evidence, dict):
        problems.append(f"{label}: missing file/digest binding")
        return None
    try:
        p = _path(root, evidence.get("path"))
        declared = evidence.get("sha256")
        if not p.is_file():
            raise ValueError("file is missing")
        if not isinstance(declared, str) or sha256_file(p) != declared:
            raise ValueError("digest mismatch")
        return p
    except (OSError, ValueError) as exc:
        problems.append(f"{label}: {exc}")
        return None


def _review(root: Path, data: Any, name: str, blockers: list[str]) -> None:
    if not isinstance(data, dict) or data.get("status") != "PASS":
        blockers.append(f"{name}: PASS evidence missing")
        return
    if not isinstance(data.get("reviewer"), str) or not data["reviewer"].strip():
        blockers.append(f"{name}: reviewer identifier missing")
    _file(root, data, name, blockers)


def _unity_evidence(root: Path, data: Any, blockers: list[str],
                    *, screenshot_artifact: Path | None = None) -> None:
    _review(root, data, "unity_integration", blockers)
    if not isinstance(data, dict):
        return
    if data.get("engine") != "Unity" or data.get("capture_origin") != "unity_player":
        blockers.append("unity_integration requires actual Unity Player screenshot provenance")
    build_id = data.get("build_id")
    if not isinstance(build_id, str) or not build_id.strip():
        blockers.append("unity_integration build_id missing")
    # For in-game assets, rely on the independent ai-3dgame-test-harness
    # seven-category same-commit release gate, not a self-written Unity PASS.
    # Proof remains read-only and all referenced evidence bytes are rehashed.
    release_path = _file(
        root, data.get("test_harness_release"), "ai-3dgame-test-harness release manifest",
        blockers,
    )
    release_player_sha = None
    if release_path is not None and isinstance(build_id, str):
        try:
            from unity_release_bridge import verify_test_harness_release
            release_manifest = json.loads(release_path.read_text(encoding="utf-8"))
            verdict = verify_test_harness_release(release_manifest, expected_commit=build_id)
            if verdict["status"] != "PASS":
                blockers.append("independent seven-category Unity release gate BLOCKED: " +
                                "; ".join(verdict["failures"]))
            else:
                release_player_sha = verdict["player_capture"]["sha256"]
        except (OSError, ValueError, KeyError) as exc:
            blockers.append("independent Unity release manifest invalid or unreadable")

    screenshot = _file(root, data.get("player_capture"), "unity player screenshot", blockers)
    if screenshot is not None and release_player_sha is not None:
        if sha256_file(screenshot) != release_player_sha:
            blockers.append("Unity Player screenshot is not the seven-category test-harness capture")
    if screenshot is not None:
        try:
            from PIL import Image
            with Image.open(screenshot) as source:
                source.load()
                if source.width < 640 or source.height < 360:
                    blockers.append("unity player screenshot is too small for visual QA")
        except (OSError,ValueError) as exc:
            blockers.append(f"unity player screenshot invalid: {exc}")
        if screenshot_artifact is not None and sha256_file(screenshot)!=sha256_file(screenshot_artifact):
            blockers.append("Steam screenshot differs from bound Unity Player capture")


def inspect_glb(path: Path, expected_components: dict[str, int]) -> dict[str, Any]:
    """Verify actual GLB container/node declarations, NOT geometry correctness."""
    failures: list[str] = []
    result: dict[str, Any] = {
        "status": "FAIL", "path": str(path), "failures": failures,
        "mesh_names": [],
    }
    try:
        with Path(path).open("rb") as handle:
            header = handle.read(20)
            if len(header) != 20:
                raise ValueError("GLB truncated header")
            magic, version, total, json_len, json_type = struct.unpack("<4sII I4s", header)
            if magic != b"glTF" or version != 2 or json_type != b"JSON":
                raise ValueError("invalid glTF 2.0 binary header")
            size = Path(path).stat().st_size
            if total != size or json_len > size - 20 or json_len > 16_000_000:
                raise ValueError("GLB length or JSON chunk invalid")
            nodes = json.loads(handle.read(json_len))
        named = [
            item.get("name", "")
            for item in nodes.get("nodes", [])
            if isinstance(item, dict) and isinstance(item.get("mesh"), int)
        ]
        result["mesh_names"] = named
        result["sha256"] = sha256_file(path)
        result["mesh_count"] = len(named)
        for substring, count in expected_components.items():
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                failures.append(f"invalid expected count for {substring}")
                continue
            found = sum(substring in name for name in named)
            if found != count:
                failures.append(f"{substring}: required {count} named mesh objects, observed {found}")
        if not named:
            failures.append("no named mesh nodes")
    except (OSError, ValueError, json.JSONDecodeError, struct.error) as exc:
        failures.append(f"GLB integrity invalid: {exc}")
    result["status"] = "PASS" if not failures else "FAIL"
    result["scope"] = "GLB container and declared named mesh nodes only; visual geometry not proven"
    return result


def _visual_coverage(image: Path) -> dict[str, Any]:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise ValidationError("canonical view detection requires Pillow and NumPy") from exc
    with Image.open(image) as src:
        src.load()
        a = np.asarray(src.convert("RGB"), dtype=np.int16)
    height, width = a.shape[:2]
    border = np.concatenate([
        a[:max(2, height//30), :].reshape(-1, 3),
        a[-max(2, height//30):, :].reshape(-1, 3),
        a[:, :max(2, width//30)].reshape(-1, 3),
        a[:, -max(2, width//30):].reshape(-1, 3),
    ], axis=0)
    bgcolor = np.median(border, axis=0)
    mask = (np.max(np.abs(a - bgcolor), axis=2) > 28)
    foreground = float(mask.mean())
    pts = np.argwhere(mask)
    bbox = [int(pts[:, 1].min()),int(pts[:, 0].min()),
            int(pts[:, 1].max()),int(pts[:, 0].max())] if len(pts) else None
    coverage = (float((bbox[2] - bbox[0] + 1) / width)
                if bbox else 0.0)
    return {
        "width": width, "height": height,
        "foreground_fraction": round(foreground, 6),
        "horizontal_coverage": round(coverage, 4),
        "bbox": bbox,
    }


def verify_canonical_views(manifest_path: Path) -> dict[str, Any]:
    failures: list[str] = []
    output: dict[str, Any] = {
        "status": "FAIL",
        "manifest": str(manifest_path),
        "failures": failures,
        "view_reports": [],
    }
    try:
        with Path(manifest_path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        root = Path(manifest_path).resolve().parent
        source = Path(data["source_glb"]).resolve()
        if not source.is_file() or sha256_file(source) != data.get("source_sha256"):
            failures.append("source GLB digest mismatch or missing")
        views = data.get("views", [])
        if not isinstance(views, list) or {r.get("name") for r in views} != REQUIRED_VIEW_NAMES:
            failures.append("missing/duplicate canonical view names")
        digests = []
        for item in views:
            name = str(item.get("name"))
            try:
                img = _path(root, item["image"])
                if not img.is_file():
                    raise ValueError("view file missing")
                actual_sha = sha256_file(img)
                if item["sha256"] != actual_sha:
                    failures.append(f"{name}: image digest mismatch")
                digests.append(actual_sha)
                metrics = _visual_coverage(img)
                output["view_reports"].append({"name": name, **metrics})
                if metrics["width"] != item.get("width") or metrics["height"] != item.get("height"):
                    failures.append(f"{name}: dimension mismatch")
                if metrics["foreground_fraction"] < .001 or metrics["horizontal_coverage"] < .10:
                    failures.append(f"{name}: empty/insufficient foreground or bad camera framing")
                if metrics["foreground_fraction"] > .70:
                    failures.append(f"{name}: implausibly large foreground coverage")
            except (ValueError, OSError, KeyError) as exc:
                failures.append(f"{name}: {exc}")
        if len(digests) != len(set(digests)):
            failures.append("duplicate image digests across canonical views")
        output["source_glb_sha256"] = data.get("source_sha256")
    except (OSError,ValueError,KeyError,json.JSONDecodeError,ValidationError) as exc:
        failures.append(f"view manifest invalid: {exc}")
    output["status"] = "PASS" if not failures else "FAIL"
    output["scope"] = "Canonical renders came from same source GLB; does NOT prove imagegen editing/Unity/artist approval"
    return output


def evaluate_package(package: dict[str, Any], root: Path) -> dict[str, Any]:
    root=Path(root).resolve()
    blockers: list[str] = []
    kind = package.get("asset_kind")
    result = {
        "schema_version": 1,
        "asset_id": package.get("asset_id"),
        "asset_kind": kind,
        "status": "BLOCKED",
        "ready_for_release": False,
        "steam_approved": False,
        "blockers": blockers,
        "checks": {},
        "limitations": [
            "PASS is a submission-review checklist, not Valve approval or a legal guarantee.",
            "Reviewer attestations must be grounded in authentic source/evidence; hashes cannot prove the visual or legal truth.",
            "Real in-engine/Host QA remains mandatory for shipping assets.",
        ],
    }
    if kind not in KINDS:
        blockers.append("invalid asset_kind")
        return result
    artifact = _file(root, package.get("artifact"), "artifact", blockers)
    if kind == "concept_reference":
        result["status"] = "REFERENCE_ONLY"
        blockers.append("concept images are references, not a Steam shipping/gameplay screenshot certificate")
        return result
    source=package.get("source",{})
    if not isinstance(source,dict) or source.get("origin") not in {"user_owned", "licensed_third_party", "openai_imagegen"}:
        blockers.append("source.origin is missing or unsupported")
        source={}
    if not isinstance(source.get("rights_basis"),str) or not source.get("rights_basis","").strip():
        blockers.append("source.rights_basis is missing")
    _review(root,source.get("rights_review"),"rights_review",blockers)
    _review(root,package.get("visual_qa"),"visual_qa",blockers)

    if kind in {"ingame_3d_model", "ingame_2d_asset"}:
        _unity_evidence(root,package.get("unity_integration"),blockers)
        if kind=="ingame_3d_model":
            if artifact is not None and artifact.suffix.lower()!=".glb":
                blockers.append("ingame_3d_model artifact must be .glb")
            component_expectations=package.get("expected_components")
            if not isinstance(component_expectations,dict) or not component_expectations:
                blockers.append("expected_components must enumerate verifiable named GLB parts")
            elif artifact is not None:
                check=inspect_glb(artifact, component_expectations)
                result["checks"]["geometry_names"]=check
                if check["status"]!="PASS":
                    blockers.extend(check["failures"])
            raw=package.get("canonical_views_manifest")
            if not raw:
                blockers.append("canonical_views_manifest missing")
            else:
                try:
                    check=verify_canonical_views(_path(root,raw))
                    result["checks"]["canonical_views"]=check
                    if check["status"]!="PASS":
                        blockers.extend(check["failures"])
                    elif artifact is not None and check["source_glb_sha256"]!=sha256_file(artifact):
                        blockers.append("canonical views do not match shipping GLB")
                except (ValueError,OSError) as exc:
                    blockers.append(f"canonical view manifest invalid: {exc}")
        elif artifact is not None and artifact.suffix.lower() not in {".png",".webp"}:
            blockers.append("ingame_2d_asset must be image format PNG/WebP")

    if kind in {"steam_store_capsule","steam_gameplay_screenshot"}:
        if artifact is not None:
            try:
                from PIL import Image
                with Image.open(artifact) as img:
                    width,height=img.size
                    fmt=img.format
                if kind=="steam_store_capsule":
                    slot=package.get("store_slot")
                    expected=CAPSULE_DIMENSIONS.get(slot)
                    if not expected:
                        blockers.append("unknown store_slot")
                    elif (width,height)!=expected:
                        blockers.append(f"Steam {slot} capsule requires {expected[0]}x{expected[1]} px, got {width}x{height}")
                    if package.get("store_text_policy") != "game_title_or_logo_only":
                        blockers.append("capsule copy restrictions are not attested: title/logo only")
                else:
                    if width<1920 or height<1080 or width*9!=height*16:
                        blockers.append("Steam screenshot must be >=1920x1080 and 16:9")
                    if package.get("capture_origin")!="unity_player" or source.get("origin")=="openai_imagegen":
                        blockers.append("Steam screenshot must be a real Unity Player gameplay capture, not generated concept art")
                if fmt not in {"PNG","JPEG"}:
                    blockers.append("Steam store art requires an approved PNG/JPEG raster format")
            except (OSError,ValueError) as exc:
                blockers.append(f"store raster image corrupt: {exc}")
        _review(root,package.get("store_content_review"),"store_content_review",blockers)
        if kind=="steam_gameplay_screenshot":
            _unity_evidence(root,package.get("unity_integration"),blockers,
                            screenshot_artifact=artifact)

    if not blockers:
        result["status"]="READY_FOR_STEAM_SUBMISSION_REVIEW"
        result["ready_for_release"]=True
    return result


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        with args.manifest.open("r",encoding="utf8") as f:
            package=json.load(f)
        report=evaluate_package(package,args.manifest.parent)
        if args.output.exists():
            raise ValidationError("refusing to overwrite existing release QA report")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
        print(json.dumps({"status":report["status"],"blockers":report["blockers"]},ensure_ascii=False))
        return 0 if report["ready_for_release"] else 2
    except (OSError,ValueError,ValidationError,json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
