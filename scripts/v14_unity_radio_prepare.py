#!/usr/bin/env python3
"""Stage a real production-audited RADIO into a FRESH isolated Unity 6 project.

This does not launch Unity, a Player, ImageGen, or the user's game project.
All staged code is public-source-safe; the private verified PNG stays local.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from artifact_integrity import resolve_in_workspace
from production_audit import audit_run
from validate_project import ValidationError
from v14_unity_radio_verify import EXPECTED_RADIO_SIZE, SHA_RE, sha256_file

UNITY_VERSION="6000.6.3f1"
PROJECT_PREFIX="image-harness-unity-v14-radio-"
SOURCE_PATH="Assets/PrivateRadio/RadioAccepted.png"
CODES=(
    "Assets/Editor/HarnessV14RadioEditor.cs",
    "Assets/Scripts/HarnessV14RadioRuntime.cs",
)


def prepare(repo:Path,project:Path,run_path:Path,expected_sha:str)->dict:
    repo=repo.resolve();project=project.expanduser().resolve()
    run_path=run_path.expanduser().resolve()
    if not SHA_RE.fullmatch(expected_sha):
        raise ValidationError("private source must be pinned to a lowercase 64-character SHA")
    if (not project.name.startswith(PROJECT_PREFIX) or
            not (project/"Assets").is_dir() or
            not (project/"ProjectSettings/ProjectVersion.txt").is_file() or
            UNITY_VERSION not in (project/"ProjectSettings/ProjectVersion.txt").read_text()):
        raise ValidationError("refuse project that is not a fresh named Unity 6 QA sandbox")
    # Strictly refuse to touch an existing project containing user/game assets.
    if any(item.name not in {".DS_Store"} for item in (project/"Assets").iterdir()):
        raise ValidationError("isolated Unity project Assets must be empty before staging")
    targets=[project/SOURCE_PATH,
             *(project/"Assets"/Path(path).relative_to("Assets") for path in CODES),
             project/"PrivateEvidence/SOURCE_PIN.json"]
    if any(x.exists() or x.is_symlink() for x in targets):
        raise ValidationError("refuse overwriting any pre-existing source, C# or receipt")
    for path in CODES:
        if not (repo/"unity/v14_isolated_radio"/path).is_file():
            raise ValidationError("versioned trusted Unity C# source is missing")
    run=json.loads(run_path.read_text(encoding="utf8"))
    if run.get("state")!="ACCEPTED" or not isinstance(run.get("current_receipt"),dict):
        raise ValidationError("source real model Run must be ACCEPTED")
    audit=audit_run(run_path)
    if audit.get("status")!="PASS" or audit.get("result_sha256")!=expected_sha:
        raise ValidationError("source real native production-audit is not PASS or SHA-bound")
    binding=run["current_receipt"]["result"]["path"]
    result=resolve_in_workspace(run["workspace_root"],binding)
    if not result.is_file() or sha256_file(result)!=expected_sha:
        raise ValidationError("private source is absent or modified")
    from PIL import Image
    with Image.open(result) as im:
        im.load()
        if im.format!="PNG" or im.size!=EXPECTED_RADIO_SIZE:
            raise ValidationError("RADIO PNG dimensions/format not Unity reference contract")
    for path in CODES:
        destination=project/path
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/"unity/v14_isolated_radio"/path,destination)
        if sha256_file(destination)!=sha256_file(repo/"unity/v14_isolated_radio"/path):
            raise ValidationError("copy of versioned Unity source changed bytes")
    imported=project/SOURCE_PATH
    imported.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(result,imported)
    if sha256_file(imported)!=expected_sha:
        raise ValidationError("copy of approved native final changed bytes")
    pinned={
        "source":"REAL_NATIVE_PRODUCTION_AUDITED_RADIO",
        "run_id":run["run_id"],
        "source_sha256":expected_sha,
        "unity_editor_version":UNITY_VERSION,
        "art_human_review":"NOT_RECEIVED",
        "rights":"NOT_VERIFIED",
        "steam_approved":False,
        "player_run_status":"NOT_TESTED",
        "project_scope":"Standalone image-textured quad for isolated Editor proof, not 3D gameplay",
    }
    destination=project/"PrivateEvidence/SOURCE_PIN.json"
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("x",encoding="utf8") as f:
        json.dump(pinned,f,indent=2,ensure_ascii=False)
        f.write("\n")
    return {"status":"READY_FOR_REAL_UNITY_EDITOR_IMPORT",
            "project":str(project),"staged_private_png_sha256":expected_sha,
            "staged_public_code":[{"path":path,
                "sha256":sha256_file(project/path)} for path in CODES],
            "player_executed":False,"human_art_approved":False,"steam_approved":False}


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    for param in ("project","run","expected-sha"):
        parser.add_argument("--"+param,required=True)
    args=parser.parse_args(argv)
    try:
        report=prepare(Path(__file__).resolve().parents[1],
                       Path(args.project),Path(args.run),args.expected_sha)
        print(json.dumps(report,ensure_ascii=False))
        return 0
    except (OSError,ValueError,TypeError,KeyError,ValidationError) as exc:
        print(json.dumps({"status":"BLOCKED_SOURCE_UNITY_STAGING",
                          "reason":type(exc).__name__,
                          "game_modified":False,"steam_approved":False}))
        return 2


if __name__=="__main__":
    raise SystemExit(main())

