#!/usr/bin/env python3
"""Read-only production receipt audit for actual Codex Host ImageGen runs.

Reports code/artifact integrity, not independent art quality or legal approval.
The official host transcript and a matching saved generated_images PNG are
required; synthetic stub-host outputs must fail this audit.
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from artifact_integrity import packet_digest, receipt_digest, png_metadata, resolve_in_workspace, sha256_file, sha256_bytes
from native_codex_host import native_generated_source
from runtime_preflight import validate_image_file
from validate_project import ValidationError


def _json(path:Path) -> dict[str,Any]:
    if not path.is_file() or path.stat().st_size>3_000_000:
        raise ValidationError(f"missing/oversized audit JSON: {path.name}")
    data=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(data,dict):
        raise ValidationError("invalid audit JSON root")
    return data


def audit_run(run_path:Path, *, codex_home:Path|None=None) -> dict[str,Any]:
    source=Path(run_path).expanduser().resolve()
    problems=[]
    summary={
        "schema_version":1,"run_path":str(source),"status":"BLOCKED",
        "release_status":"NOT_CERTIFIED","steam_approved":False,
        "imagegen_attestation": "unverified_native_event_origin",
        "generation_steps":[],
        "qa_steps":[],
        "failures":problems,
        "scope":"Image/receipt/host-transcript integrity only, not independent artistic correctness, IP rights, Unity/Steam release",
    }
    try:
        run=_json(source)
        if run.get("state")!="ACCEPTED":
            problems.append("run is not ACCEPTED")
        if run.get("auditable") is not True:
            problems.append("run is not a real auditable execution")
        root=Path(run["workspace_root"]).resolve()
        if not source.is_relative_to(root):
            raise ValidationError("run path escapes its declared workspace")
        if not run.get("current_receipt") or receipt_digest(run["current_receipt"])!=run["current_receipt"]["receipt_id"]:
            problems.append("current receipt missing or digest mismatch")
        receipt=run.get("current_receipt") or {}
        if not isinstance(receipt,dict):
            raise ValidationError("malformed current receipt")
        if receipt.get("result"):
            target=resolve_in_workspace(root,receipt["result"]["path"])
            if not target.is_file() or sha256_file(target)!=receipt.get("result_sha256"):
                problems.append("final result is missing or SHA changed")
            elif not validate_image_file(target)[0]:
                problems.append("final generated PNG is corrupt")
        else:
            problems.append("no final result binding")
        qa=run.get("last_qa") or {}
        if not isinstance(qa,dict):
            raise ValidationError("malformed final QA")
        hard=set(run.get("required_hard_gates",[]))
        present={g.get("name") for g in qa.get("gates",[]) if isinstance(g,dict)}
        if qa.get("status") not in {"PASS","PASS_WITH_NOTES"} or not hard or not hard.issubset(present):
            problems.append("final hard-gate QA absent/incomplete")
        if any(g.get("status")!="PASS" for g in qa.get("gates",[]) if g.get("name") in hard):
            problems.append("final QA contains non-PASS hard gate")
        if qa.get("receipt_id")!=receipt.get("receipt_id") or qa.get("result_sha256")!=receipt.get("result_sha256"):
            problems.append("QA not bound to final receipt/result")
        evidence_dir=source.with_name(source.name+".production")
        generation_dirs=sorted(x for x in evidence_dir.glob("*-imagegen_*") if x.is_dir())
        if len(generation_dirs)!=run.get("iteration"):
            problems.append("generation iteration count does not match recorded image steps")
        home=Path(codex_home or Path.home()/".codex").expanduser().resolve()
        receipt_ids=[]
        for step in generation_dirs:
            info={"name":step.name,"status":"BLOCKED"}
            summary["generation_steps"].append(info)
            try:
                packet=_json(step/"packet.json")
                step_receipt=_json(step/"receipt.json")
                attestation=_json(step/"attestation.json")
                events=(step/"events.jsonl").read_bytes()
                image=step/"generated.png"
                if packet.get("packet_id")!=packet_digest(packet):
                    raise ValidationError("packet digest mismatch")
                if step_receipt.get("receipt_id")!=receipt_digest(step_receipt):
                    raise ValidationError("receipt digest mismatch")
                if step_receipt["packet_id"]!=packet["packet_id"]:
                    raise ValidationError("receipt references wrong packet")
                if step_receipt.get("result_sha256")!=sha256_file(image):
                    raise ValidationError("result PNG does not match execution receipt")
                if not validate_image_file(image)[0]:
                    raise ValidationError("invalid generated PNG")
                if not isinstance(attestation,dict) or attestation.get("backend")!="native_codex_chatgpt":
                    raise ValidationError("not an authenticated native Codex host attestation")
                if attestation.get("event_transcript_sha256")!=sha256_bytes(events):
                    raise ValidationError("Codex event transcript SHA mismatch")
                native=native_generated_source(events,image,home)
                if sha256_file(native)!=sha256_file(image):
                    raise ValidationError("native Codex generated source SHA mismatch")
                for binding in step_receipt.get("input_bindings",[]):
                    p=resolve_in_workspace(root,binding["path"])
                    if not p.is_file() or sha256_file(p)!=binding["sha256"]:
                        raise ValidationError("receipt input image absent or tampered")
                    if png_metadata(p)!=binding["png"]:
                        raise ValidationError("receipt input PNG metadata mismatch")
                info.update({
                    "status":"PASS",
                    "receipt_id":step_receipt["receipt_id"],
                    "output_sha256":sha256_file(image),
                    "native_source_sha256":sha256_file(native),
                    "transcript_sha256":sha256_bytes(events),
                })
                receipt_ids.append(step_receipt["receipt_id"])
            except (OSError,ValueError,KeyError,TypeError,ValidationError,json.JSONDecodeError) as e:
                problems.append(step.name+": "+str(e))
        if receipt_ids and receipt.get("receipt_id")!=receipt_ids[-1]:
            problems.append("terminal receipt does not match last generation")
        critic_dirs=sorted(x for x in evidence_dir.glob("*-visual_qa") if x.is_dir())
        if len(critic_dirs)!=run.get("iteration"):
            problems.append("every generation must have a persisted visual QA step")
        for step in critic_dirs:
            info={"name":step.name,"status":"BLOCKED"}
            summary["qa_steps"].append(info)
            try:
                qt=tomllib.loads((step/"qa.toml").read_text(encoding="utf8"))
                packet=_json(step/"packet.json")
                attestation=_json(step/"attestation.json")
                events=(step/"events.jsonl").read_bytes()
                if qt.get("receipt_id") not in receipt_ids:
                    raise ValidationError("critic QA receipt not a verified native generation")
                if qt.get("result_sha256") is None or qt.get("asset_id")!=run.get("asset_id"):
                    raise ValidationError("critic QA binding invalid")
                if attestation.get("event_transcript_sha256")!=sha256_bytes(events):
                    raise ValidationError("critic event transcript hash mismatch")
                if packet.get("packet_id")!=packet_digest(packet):
                    raise ValidationError("critic request packet was altered")
                info.update({"status":"PASS","report_id":qt.get("report_id"),
                             "status_verdict":qt.get("status")})
            except (OSError,ValueError,KeyError,ValidationError,json.JSONDecodeError) as e:
                problems.append(step.name+": "+str(e))
        if run.get("state")=="ACCEPTED" and not problems:
            summary["status"]="PASS"
            summary["imagegen_attestation"]="native_saved_png_plus_SHA_and_completed_copy_event"
        summary["run_id"]=run.get("run_id")
        summary["result_sha256"]=receipt.get("result_sha256")
    except (OSError,ValueError,KeyError,TypeError,ValidationError,json.JSONDecodeError) as e:
        problems.append("audit setup failed: "+str(e))
    return summary


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists():
        print("BLOCKED: refusing to overwrite existing production audit",file=sys.stderr)
        return 2
    report=audit_run(args.run)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf8") as f:
        json.dump(report,f,indent=2,ensure_ascii=False)
        f.write("\n")
    print(json.dumps({"status":report["status"],"steps":len(report["generation_steps"]),
                      "qa":len(report["qa_steps"]), "problems":report["failures"],
                      "steam_approved":False},ensure_ascii=False))
    return 0 if report["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
