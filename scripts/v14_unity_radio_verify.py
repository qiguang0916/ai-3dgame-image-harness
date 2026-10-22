#!/usr/bin/env python3
"""Fail-closed offline verification of a real, isolated Unity RADIO Editor import.

The only PASS asserted here is a SHA-verified Editor textured-image render.
A built .app is NOT a launched/captured Player or Unity-in-game 3D acceptance.
Human art, rights and Steam review are out of scope and always BLOCKED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import plistlib
import re
import sys
from pathlib import Path
from typing import Any

from artifact_integrity import resolve_in_workspace
from production_audit import audit_run
from validate_project import ValidationError

SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
EXPECTED_RADIO_SIZE = (1536, 1024)
MIN_EDITOR_SHOT = (640, 360)


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def json_object(path: Path) -> dict[str,Any]:
    if not path.is_file() or path.is_symlink() or not 0<path.stat().st_size<=2_000_000:
        raise ValidationError("missing, symlinked or oversized Unity evidence JSON")
    try:
        value=json.loads(path.read_text(encoding="utf8"))
    except (ValueError,UnicodeError,OSError) as exc:
        raise ValidationError("malformed Unity evidence JSON") from exc
    if not isinstance(value,dict):
        raise ValidationError("Unity evidence JSON must be an object")
    return value


def compare_rendered_pixels(source:Path, screenshot:Path,
                            *,threshold:int=36,max_mae:float=13.0)->dict[str,Any]:
    """Compare actual Editor render to source orientation and image content.

    This is pixel concordance only, NOT cryptographic proof of renderer origin.
    An actual Unity Editor log/compiled C# and isolated project are checked
    separately. A flat/black/mirrored/random image cannot obtain this PASS.
    """
    import numpy as np
    from PIL import Image
    with Image.open(source) as im:
        im.load()
        if im.format!="PNG":
            raise ValidationError("original technical production image is not PNG")
        original_size=im.size
        original=im.convert("RGB")
    with Image.open(screenshot) as im:
        im.load()
        if im.format!="PNG" or im.width<MIN_EDITOR_SHOT[0] or im.height<MIN_EDITOR_SHOT[1]:
            raise ValidationError("Editor capture PNG missing or dimensions invalid")
        shot=np.asarray(im.convert("RGB"),dtype=np.uint8)
    rows,cols=shot.shape[:2]
    reference=shot[0,0,:].astype(np.int16)
    displacement=np.max(np.abs(shot.astype(np.int16)-reference),axis=2)
    foreground=displacement>threshold
    ys=np.where(foreground.any(axis=1))[0]
    xs=np.where(foreground.any(axis=0))[0]
    if len(xs)==0 or len(ys)==0:
        raise ValidationError("Editor capture has no meaningful asset pixels")
    bbox=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
    bw,bh=bbox[2]-bbox[0],bbox[3]-bbox[1]
    if (bw<300 or bh<240 or bw>=cols or bh>=rows
            or abs((bw/bh)-(original_size[0]/original_size[1]))>0.09):
        raise ValidationError("Editor rendered asset coverage/shape is inconsistent")
    cropped=shot[bbox[1]:bbox[3],bbox[0]:bbox[2],:]
    expected=np.asarray(original.resize((bw,bh),Image.Resampling.BILINEAR),dtype=np.float32)
    captured=cropped.astype(np.float32)
    maez={
        "original":float(np.mean(np.abs(captured-expected))),
        "horizontal_flip":float(np.mean(np.abs(captured-expected[:,::-1,:]))),
        "vertical_flip":float(np.mean(np.abs(captured-expected[::-1,:,:]))),
        "rotated_180":float(np.mean(np.abs(captured-expected[::-1,::-1,:])))
    }
    if not math.isfinite(maez["original"]) or maez["original"]>max_mae:
        raise ValidationError("Editor frame does not faithfully show source pixels")
    if any(maez["original"]>=maez[key]-3 for key in
           ("horizontal_flip","vertical_flip","rotated_180")):
        raise ValidationError("Editor frame orientation is flipped or inconclusive")
    if float(np.std(captured))<18 or float(foreground.mean())<0.2:
        raise ValidationError("Editor image color diversity/coverage too low")
    return {
        "status":"EDITOR_RENDER_SOURCE_ORIENTATION_AND_PIXELS_MATCH",
        "screenshot_dimensions":[cols,rows],
        "source_dimensions":list(original_size),
        "rendered_bbox_xyxy":bbox,
        "asset_area_fraction":round(float(bw*bh/(cols*rows)),6),
        "nonbackground_fraction":round(float(foreground.mean()),6),
        "rgb_mean_absolute_error_original":round(maez["original"],5),
        "rgb_mean_absolute_error_mirror":round(maez["horizontal_flip"],5),
        "rgb_mean_absolute_error_vertical":round(maez["vertical_flip"],5),
        "raw_screenshot_sha256":sha256_file(screenshot),
        "limitations":"Pure observed Editor rendering/pixel comparison. Cannot prove actual standalone Player, 3D object behavior or legal rights."
    }


def verify_editor_pilot(repo:Path,project:Path,evidence:Path,
                        private_run:Path,expected_sha:str,editor_log:Path)->dict[str,Any]:
    if not isinstance(expected_sha,str) or not SHA_RE.fullmatch(expected_sha):
        raise ValidationError("must supply exactly one lowercase 64-digit technical source SHA")
    repo=repo.resolve();project=project.resolve();evidence=evidence.resolve()
    if not project.is_dir() or not evidence.is_dir() or not editor_log.is_file():
        raise ValidationError("isolated Unity project/evidence/log missing")
    pinned=json_object(project/"PrivateEvidence/SOURCE_PIN.json")
    if (pinned.get("source_sha256")!=expected_sha
            or pinned.get("steam_approved") is not False
            or pinned.get("art_human_review")!="NOT_RECEIVED"
            or pinned.get("unity_editor_version")!="6000.6.3f1"):
        raise ValidationError("Unity isolated source receipt or scope was changed")
    source=project/"Assets/PrivateRadio/RadioAccepted.png"
    if not source.is_file() or source.is_symlink() or sha256_file(source)!=expected_sha:
        raise ValidationError("imported Unity source PNG SHA mismatch")
    full=private_run.expanduser().resolve()
    run=json_object(full)
    if run.get("state")!="ACCEPTED":
        raise ValidationError("source production Run has not reached ACCEPTED")
    audit=audit_run(full)
    if audit.get("status")!="PASS" or audit.get("result_sha256")!=expected_sha:
        raise ValidationError("real native source production audit fails on fresh verification")
    source_in_original=resolve_in_workspace(run["workspace_root"],run["current_receipt"]["result"]["path"])
    if sha256_file(source_in_original)!=expected_sha:
        raise ValidationError("original native technical delivery was replaced")
    source_code_sha={}
    for path in ("Assets/Editor/HarnessV14RadioEditor.cs",
                 "Assets/Scripts/HarnessV14RadioRuntime.cs"):
        file=project/path
        published=repo/"unity/v14_isolated_radio"/path
        if not file.is_file() or not published.is_file() or file.is_symlink():
            raise ValidationError("Unity source C# missing from isolated project")
        if sha256_file(file)!=sha256_file(published):
            raise ValidationError("isolated Unity C# differs from reviewed version")
        source_code_sha[path]=sha256_file(file)
    actual=json_object(evidence/"editor-report.json")
    if any((
        actual.get("status")!="UNITY_EDITOR_IMPORTED_PLAYER_BUILT_NOT_ART_APPROVED",
        actual.get("unityVersion")!="6000.6.3f1",
        actual.get("imageSourceSha256")!=expected_sha,
        actual.get("imageImportedSha256")!=expected_sha,
        actual.get("assetPath")!="Assets/PrivateRadio/RadioAccepted.png",
        actual.get("importedImageMatchesSourceBytes") is not True,
        actual.get("editorCaptureIsRealUnityRender") is not True,
        actual.get("editorRenderedStatus")!="UNITY_EDITOR_RENDER_CONTENT_OBSERVED_NOT_ART_APPROVED",
        actual.get("buildResult")!="Succeeded",
        actual.get("developmentBuild") is not False,
        actual.get("importedWidth")!=EXPECTED_RADIO_SIZE[0],
        actual.get("importedHeight")!=EXPECTED_RADIO_SIZE[1],
        not isinstance(actual.get("assetGuid"),str) or len(actual["assetGuid"])!=32,
        not isinstance(actual.get("quadFacingCameraDot"),(int,float)) or
            actual.get("quadFacingCameraDot",0)<0.95,
        not isinstance(actual.get("editorNonbackgroundSamples"),int) or
            actual.get("editorNonbackgroundSamples",0)<1500,
    )):
        raise ValidationError("actual Unity Editor import/build/report fields do not pass scoped requirements")
    shot=evidence/"editor-scene.png"
    if not shot.is_file() or shot.is_symlink() or sha256_file(shot)!=actual.get("editorRenderedSha256"):
        raise ValidationError("Unity Editor RenderTexture screenshot does not match saved editor report")
    pixels=compare_rendered_pixels(source,shot)
    log=editor_log.read_text(errors="replace")
    markers=[
        "HARNESS_V14_EDITOR_SCENE_CAPTURE "+str(shot)+" "+sha256_file(shot),
        "HARNESS_V14_EDITOR_IMPORT_DONE "+expected_sha+" Succeeded",
        "Exiting batchmode successfully now!"
    ]
    if not all(marker in log for marker in markers):
        raise ValidationError("Unity Editor genuine render/build log markers missing")
    app=evidence/"RadioImageAcceptance.app"
    if app.resolve()!=Path(actual.get("buildPlayerPath","")).resolve():
        raise ValidationError("Unity Editor recorded a different build location")
    plist=app/"Contents/Info.plist"
    if not plist.is_file() or plist.is_symlink():
        raise ValidationError("macOS Player bundle Info.plist missing")
    try:
        info=plistlib.loads(plist.read_bytes())
        binary=app/"Contents/MacOS"/info["CFBundleExecutable"]
    except (ValueError,KeyError,TypeError) as exc:
        raise ValidationError("invalid macOS Player bundle manifest") from exc
    if not binary.is_file() or binary.is_symlink() or binary.stat().st_size<10_000:
        raise ValidationError("macOS Player executable missing or implausible")
    return {
        "schema_version":1,
        "status":"EDITOR_IMPORT_RENDER_AND_PLAYER_BUILD_VERIFIED_ONLY",
        "source_production_audit":"PASS",
        "source_native_run_id":run["run_id"],
        "source_native_production_sha256":expected_sha,
        "unity_version":actual["unityVersion"],
        "editor_graphics_device":actual.get("graphicsDevice"),
        "project":str(project),"isolated_scene":"Assets/Scenes/V14RadioTextureAcceptance.unity",
        "source_code_sha256":source_code_sha,
        "editor_report_sha256":sha256_file(evidence/"editor-report.json"),
        "editor_log_sha256":sha256_file(editor_log),
        "actual_editor_pixel_evidence":pixels,
        "player_bundle_built":True,
        "player_build_reported_non_development":True,
        "player_bundle_executable_sha256":sha256_file(binary),
        "player_bundle_executable_bytes":binary.stat().st_size,
        "player_bundle_reported_bytes":actual["buildSizeBytes"],
        "player_launch_captured":False,
        "player_framerate_verified":False,
        "unity_editor_technical_scope_pass":True,
        "unity_player_status":"BLOCKED_EXTERNAL_LAUNCH_NOT_PERMITTED",
        "unity_3d_asset_verified":False,
        "human_art_approval":"NOT_RECEIVED",
        "source_commercial_rights":"NOT_VERIFIED",
        "steam_approved":False,
        "commercial_release_certified":False,
        "v14_full_release_gate":"BLOCKED_PENDING_PLAYER_AND_GAME_ASSET_AND_ART_RIGHTS",
        "official_commercial_batch_samples_added":0,
        "safety_note":"A textured-quad Unity Editor import and a built standalone .app are not a player screenshot, commercial right, 3D mesh or actual game integration."
    }


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("project","evidence","run","expected-sha","editor-log","output"):
        parser.add_argument("--"+name,required=True)
    args=parser.parse_args(argv)
    output=Path(args.output).expanduser().resolve()
    if output.exists() or output.is_symlink():
        print("BLOCKED: output already exists; refusing to rewrite technical evidence",file=sys.stderr)
        return 2
    try:
        result=verify_editor_pilot(
            Path(__file__).resolve().parents[1],Path(args.project),Path(args.evidence),
            Path(args.run),args.expected_sha,Path(args.editor_log))
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open("x",encoding="utf-8") as f:
            json.dump(result,f,ensure_ascii=False,indent=2)
            f.write("\n")
        print(json.dumps({"status":result["status"],
                          "editor_render_mae":result["actual_editor_pixel_evidence"]["rgb_mean_absolute_error_original"],
                          "player_launched":result["player_launch_captured"],
                          "commercial_release_certified":False,
                          "report_sha256":sha256_file(output)},ensure_ascii=False))
        return 0
    except (OSError,ValueError,KeyError,TypeError,ValidationError) as exc:
        print(json.dumps({"status":"BLOCKED_EDITOR_TECHNICAL_VERIFICATION",
                          "reason":type(exc).__name__,
                          "player_verified":False,"commercial_release_certified":False}))
        return 2


if __name__=="__main__":
    raise SystemExit(main())

