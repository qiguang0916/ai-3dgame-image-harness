#!/usr/bin/env python3
"""Capture genuine Unity Player UI via an opt-in *in-engine* QA screenshot flag.

No macOS Screen Recording/Accessibility permission, GUI scripting, local AI,
or game-project mutation is required. This is *only* a Player visual capture;
it cannot certify independent physics, OS input, performance, rights or Steam
acceptance. Outputs are deliberately local, write-once and SHA-bound.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_project import ValidationError

EXPECTED = ("sharpening-hud.png", "inspection-html-A-2880x1800.png",
            "inspection-html-B-2880x1800.png")
LOG_MARKERS = ("INSPECT_HTML_QA_CAPTURE_A", "INSPECT_HTML_QA_CAPTURE_B")


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024),b""):
            h.update(chunk)
    return h.hexdigest()


def app_binary(bundle: Path) -> Path:
    bundle=Path(bundle).resolve()
    if bundle.suffix != ".app" or not bundle.is_dir():
        raise ValidationError("expected an existing macOS Unity .app bundle")
    with (bundle/"Contents"/"Info.plist").open("rb") as f:
        data=plistlib.load(f)
    exe=bundle/"Contents"/"MacOS"/data["CFBundleExecutable"]
    if not exe.is_file():
        raise ValidationError("Unity Player executable is missing")
    return exe


def inspect_capture(bundle: Path, evidence_dir: Path) -> dict[str,Any]:
    """Read only immutable screenshot/Player-log evidence, no OS screen capture."""
    root=Path(evidence_dir).resolve()
    if not root.is_dir():
        raise ValidationError("evidence directory does not exist")
    executable=app_binary(bundle)
    log=root/"player.log"
    failures=[]
    lines=[]
    if not log.is_file():
        failures.append("actual Unity Player log missing")
    else:
        lines=log.read_text(errors="replace").splitlines()
    screen_dir=root/"captured"
    screenshots=[]
    for name in EXPECTED:
        path=screen_dir/name
        if not path.is_file() or path.is_symlink():
            failures.append(f"Unity Player screenshot missing or symlink: {name}")
            continue
        try:
            from PIL import Image
            with Image.open(path) as im:
                im.load()
                w,h=im.size
                if im.format!="PNG" or w<640 or h<360:
                    raise ValidationError("PNG dimensions/format invalid")
            screenshots.append({"name":name,"path":str(path),"sha256":sha(path),
                                "width":w,"height":h,"byte_size":path.stat().st_size})
        except (OSError,ValueError,ValidationError) as exc:
            failures.append(f"invalid Unity screenshot {name}: {exc}")
    # Key proof: these were emitted by the actual executable's in-engine
    # screenshot coroutine, not externally composited images.
    for marker in LOG_MARKERS:
        expected_name = (
            "inspection-html-A-2880x1800.png" if marker.endswith("_A")
            else "inspection-html-B-2880x1800.png"
        )
        expected_path = (screen_dir / expected_name).resolve()
        matched = False
        for line in lines:
            if marker not in line:
                continue
            match = re.search(re.escape(marker) + r"\s+(.+?\.png)(?=\s|$)", line)
            if match and Path(match.group(1)).expanduser().resolve() == expected_path:
                matched = True
                break
        if not matched:
            failures.append(f"Unity screenshot trace missing: {marker}")
    if not any("MINIMUM_LOOP_READY" in line for line in lines):
        failures.append("Unity gameplay loop did not report ready")
    if any("INSPECT_HTML_QA_LOOP_MISSING" in line or
           "NullReferenceException" in line for line in lines):
        failures.append("Unity screenshot harness reported a runtime exception")
    return {
        "schema_version":1,
        "evidence_kind":"unity_player_self_capture",
        "capture_status":"PASS" if not failures else "BLOCKED",
        "seven_category_release_status":"BLOCKED",
        "steam_approved":False,
        "executable":str(executable),
        "executable_sha256":sha(executable),
        "log_sha256":sha(log) if log.is_file() else None,
        "screenshots":screenshots,
        "expected_screenshots":list(EXPECTED),
        "failures":failures,
        "provenance_note":(
            "Unity Player's built-in ScreenCapture coroutine emitted A/B evidence. "
            "Logs and file hashes establish a local chain, not cryptographic game build "
            "identity, physics performance, source rights or Steam approval."
        ),
    }


def verify_existing_report(bundle: Path, evidence_dir: Path) -> dict[str, Any]:
    """Rehash all files against write-once original report; do not bless edits."""
    root=Path(evidence_dir).resolve()
    report=root/"report.json"
    if not report.is_file() or report.stat().st_size>2_000_000:
        raise ValidationError("original local capture report is missing/oversized")
    try:
        stored=json.loads(report.read_text(encoding="utf8"))
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        raise ValidationError("original capture report cannot be parsed") from exc
    actual=inspect_capture(bundle,root)
    blockers=[]
    if stored.get("capture_status")!="PASS":
        blockers.append("original capture was not passing")
    if stored.get("executable_sha256")!=actual.get("executable_sha256"):
        blockers.append("original player executable digest mismatch")
    if stored.get("log_sha256")!=actual.get("log_sha256"):
        blockers.append("original Unity log digest mismatch")
    original_shas={x.get("name"):x.get("sha256") for x in stored.get("screenshots",[]) if isinstance(x,dict)}
    current_shas={x.get("name"):x.get("sha256") for x in actual.get("screenshots",[]) if isinstance(x,dict)}
    if original_shas!=current_shas or len(original_shas)!=len(EXPECTED):
        blockers.append("original Unity screenshot digest mismatch")
    if blockers:
        actual["capture_status"]="BLOCKED"
        actual["failures"].extend(blockers)
    actual["verification_mode"]="rehash_original_write_once_report"
    return actual


def run_capture(bundle:Path, destination:Path, *, duration:int=45,
                width:int=1440,height:int=900) -> dict[str,Any]:
    if not 18 <= duration <= 180:
        raise ValidationError("capture duration must be between 18 and 180 seconds")
    if width<640 or height<360:
        raise ValidationError("capture window must be at least 640x360")
    dest=Path(destination).expanduser().resolve()
    if dest.exists():
        raise ValidationError("write-once capture destination already exists")
    executable=app_binary(bundle)
    dest.mkdir(parents=True)
    captures=dest/"captured"
    log=dest/"player.log"
    args=[str(executable),"-screen-fullscreen","0",
          "-screen-width",str(width),"-screen-height",str(height),
          "-inspectHtmlQaCapture","-minimumEvidenceDir",str(captures),
          "-logFile",str(log)]
    started=datetime.now(timezone.utc).isoformat()
    deadline=time.monotonic()+duration
    process=None
    reason="TIME_LIMIT"
    try:
        with (dest/"launcher.log").open("xb") as fh:
            process=subprocess.Popen(args,stdout=fh,stderr=subprocess.STDOUT)
            while time.monotonic()<deadline:
                if all((captures/n).is_file() for n in EXPECTED):
                    # Final async ScreenCapture writes must fully flush to disk.
                    time.sleep(1)
                    reason="EXPECTED_ENGINE_CAPTURES"
                    break
                if process.poll() is not None:
                    reason="PLAYER_EXITED"
                    break
                time.sleep(0.5)
    except (OSError,ValueError):
        reason="PLAYER_LAUNCH_FAILED"
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    check=inspect_capture(bundle,dest)
    check.update({
        "started_at":started,"finished_at":datetime.now(timezone.utc).isoformat(),
        "reason":reason,
        "player_exit_code":process.returncode if process else None,
        "source_bundle":str(bundle),
    })
    with (dest/"report.json").open("x",encoding="utf8") as f:
        json.dump(check,f,ensure_ascii=False,indent=2)
        f.write("\n")
    return check


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app",required=True,type=Path)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--verify-existing",action="store_true")
    parser.add_argument("--duration",type=int,default=45)
    parser.add_argument("--width",type=int,default=1440)
    parser.add_argument("--height",type=int,default=900)
    args=parser.parse_args(argv)
    try:
        if args.verify_existing:
            result=verify_existing_report(args.app,args.output_dir)
        else:
            result=run_capture(args.app,args.output_dir,duration=args.duration,
                               width=args.width,height=args.height)
        print(json.dumps({
            "capture_status":result["capture_status"],
            "release_status":result["seven_category_release_status"],
            "shots":len(result["screenshots"]),
            "failures":result["failures"],
            "report":str(args.output_dir/"report.json"),
        },ensure_ascii=False))
        return 0 if result["capture_status"]=="PASS" else 2
    except (OSError,ValidationError,ValueError) as e:
        print(json.dumps({"capture_status":"BLOCKED","reason":str(e)},ensure_ascii=False))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
