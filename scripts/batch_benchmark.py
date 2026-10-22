#!/usr/bin/env python3
"""v0.13 deterministic native batch KPI report; NEVER runs ImageGen or approves art.

Only unique, SHA-bound, formally production-audited native results are eligible
for a real production sample. A batch journal's ACCEPTED string is insufficient.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Callable

from artifact_integrity import resolve_in_workspace
from batch_production import load_state, load_run, make_plan, verify_accepted_evidence
from production_audit import audit_run
from validate_project import ValidationError, load_document

PHASES = {
    "pilot": {"min_unique_audited": 12, "min_categories": 4, "first_pass": None, "final_pass": None},
    "candidate": {"min_unique_audited": 30, "min_categories": 5, "first_pass": .75, "final_pass": .90},
    "rc": {"min_unique_audited": 60, "min_categories": 6, "first_pass": .80, "final_pass": .95},
}
SAFE_REASON = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,79}\Z")


def wilson_interval(successes: int, total: int) -> list[float] | None:
    """Descriptive 95% binomial interval; never a population quality guarantee."""
    if total == 0:
        return None
    if successes < 0 or successes > total:
        raise ValidationError("invalid counted QA successes")
    z = 1.959963984540054
    fraction = successes / total
    denom = 1.0 + z*z/total
    mean = (fraction + z*z/(2*total))/denom
    radius = z * math.sqrt(fraction*(1-fraction)/total + z*z/(4*total*total))/denom
    return [round(max(0.,mean-radius),6),round(min(1.,mean+radius),6)]


def _category(root: Path, job: dict[str,Any]) -> str:
    """Derive the art category only from SHA-bound asset and edit documents."""
    asset = load_document(resolve_in_workspace(root,job["asset"])).data
    edit = load_document(resolve_in_workspace(root,job["edit"])).data
    typed = edit.get("asset_spec_v2")
    category = typed.get("category") if isinstance(typed,dict) else None
    category = category or asset.get("asset_type")
    return category[:80] if isinstance(category,str) and category.strip() else "UNCLASSIFIED"


def _reason(value: Any) -> str:
    return value if isinstance(value,str) and SAFE_REASON.fullmatch(value) else "unspecified_blocker"


def collect(plan: dict[str,Any], state: dict[str,Any], *,
            auditor: Callable[[Path],dict[str,Any]] = audit_run) -> dict[str,Any]:
    """No side effects: rehash every accepted run and re-audit native evidence."""
    root = Path(plan["workspace_root"]).resolve()
    if (state.get("plan") != plan or not isinstance(state.get("jobs"),list)
            or len(state["jobs"]) != len(plan["jobs"])):
        raise ValidationError("batch journal is not bound to original immutable plan")
    jobs=[]
    for spec, entry in zip(plan["jobs"],state["jobs"]):
        if not isinstance(entry,dict) or spec["id"] != entry.get("id"):
            raise ValidationError("batch job order or identity changed")
        run_path=resolve_in_workspace(root,spec["run"])
        evidence=run_path.with_name(run_path.name+".production")
        started=run_path.is_file() or evidence.is_dir()
        job={
            "id":spec["id"],"category":_category(root,spec),
            "journal_status":entry["status"],"started":started,
            "eligible_native":False,"first_pass_accepted":False,
            "audit_status":"NOT_RUN","reason":None,
        }
        if not started:
            job["reason"]="never_started" if entry["status"]=="PENDING" else "missing_run_or_native_host_evidence"
            jobs.append(job)
            continue
        if not run_path.is_file():
            job.update(audit_status="BLOCKED",reason="missing_run_state")
            jobs.append(job)
            continue
        try:
            run=load_run(run_path)
            if entry["status"]!="ACCEPTED" or run.get("state")!="ACCEPTED":
                blocker=run.get("blocker") or {}
                job.update(audit_status="BLOCKED",
                           reason=_reason(blocker.get("reason_code") or entry.get("reason") or "not_accepted"))
                jobs.append(job)
                continue
            if not verify_accepted_evidence(run,spec,root):
                job.update(audit_status="BLOCKED",reason="run_binding_or_accepted_bytes_invalid")
                jobs.append(job)
                continue
            native_report=auditor(run_path)
            if not isinstance(native_report,dict) or native_report.get("status")!="PASS":
                job.update(audit_status="BLOCKED",reason="production_audit_not_pass")
                jobs.append(job)
                continue
            receipt=run.get("current_receipt") or {}
            sha=receipt.get("result_sha256")
            run_id=run.get("run_id")
            if (not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha)
                    or not isinstance(run_id,str) or not run_id.strip()):
                job.update(audit_status="BLOCKED",reason="invalid_run_identity")
                jobs.append(job)
                continue
            job.update(
                audit_status="PASS",eligible_native=True,
                run_id=run_id,result_sha256=sha,
                source_contract_identity=spec["asset_sha256"]+":"+spec["edit_sha256"],
                first_pass_accepted=(run.get("iteration")==1 and
                    run.get("repair_passes")==0 and run.get("regeneration_passes")==0),
                repair_passes=run.get("repair_passes",0),
                regeneration_passes=run.get("regeneration_passes",0),
            )
        except (OSError,ValueError,TypeError,KeyError):
            job.update(audit_status="BLOCKED",reason="run_or_audit_not_verifiable")
        jobs.append(job)

    # Fail ALL duplicate samples closed, never use input order as a tiebreaker.
    eligible=[j for j in jobs if j["eligible_native"]]
    duplicate_fields={
        "result_sha256":("duplicate_native_result_sha",
                         "duplicate_result_sha_count"),
        "run_id":("duplicate_native_run_id","duplicate_run_id_count"),
        "source_contract_identity":("duplicate_source_asset_edit_contract",
                                     "duplicate_source_contract_count"),
    }
    result={"jobs":jobs}
    duplicates={}
    for field,(_,count_name) in duplicate_fields.items():
        counts=Counter(j.get(field) for j in eligible)
        repeated={value for value,n in counts.items() if n>1}
        duplicates[field]=repeated
        result[count_name]=len(repeated)
    for job in eligible:
        for field,(reason,_) in duplicate_fields.items():
            if job.get(field) in duplicates[field]:
                job.update(eligible_native=False,first_pass_accepted=False,
                           audit_status="BLOCKED",reason=reason)
                break
    return result


def build_report(plan:dict[str,Any],state:dict[str,Any],phase:str,
                 *,auditor:Callable[[Path],dict[str,Any]]=audit_run)->dict[str,Any]:
    if phase not in PHASES:
        raise ValidationError("unsupported v0.13 benchmark phase")
    evidence=collect(plan,state,auditor=auditor)
    jobs=evidence["jobs"]
    eligible=[j for j in jobs if j["eligible_native"]]
    started=[j for j in jobs if j["started"]]
    success=len(eligible)
    n=len(started)
    first=sum(1 for j in eligible if j["first_pass_accepted"])
    categories=sorted({j["category"] for j in eligible if j["category"]!="UNCLASSIFIED"})
    grouped={}
    for category in sorted({j["category"] for j in jobs}):
        subset=[j for j in jobs if j["category"]==category]
        grouped[category]={
            "planned":len(subset),
            "started":sum(bool(j["started"]) for j in subset),
            "audited_native_accepted":sum(bool(j["eligible_native"]) for j in subset),
            "first_pass_accepted":sum(bool(j["first_pass_accepted"]) for j in subset),
        }
    targets=PHASES[phase]
    first_rate=round(first/n,6) if n else None
    final_rate=round(success/n,6) if n else None
    size_ok=(success>=targets["min_unique_audited"] and
             len(categories)>=targets["min_categories"])
    rate_ok=bool(size_ok and
        (targets["first_pass"] is None or first_rate>=targets["first_pass"]) and
        (targets["final_pass"] is None or final_rate>=targets["final_pass"]))
    reasons=Counter(j["reason"] for j in jobs if j["reason"])
    return {
        "schema_version":1,"document_type":"native_batch_benchmark",
        "phase":phase,"batch_id":plan["batch_id"],
        "manifest_sha256":plan["manifest_sha256"],
        "status":("MEETS_OBSERVED_SAMPLE_COUNT_AND_RATES_ONLY" if rate_ok
                  else "INSUFFICIENT_VERIFIED_REAL_PRODUCTION"),
        "release_state":"BLOCKED_PENDING_ART_UNITY_RIGHTS_STEAM",
        "sample_requirement":targets,
        "planned_jobs":len(jobs),"started_jobs":n,
        "independent_audited_native_results":success,
        "unique_categories_with_native_audits":len(categories),
        "categories":categories,
        "first_pass_accepted":first,
        "first_pass_rate_observed":first_rate,"final_pass_rate_observed":final_rate,
        "first_pass_95pct_wilson":wilson_interval(first,n),
        "final_pass_95pct_wilson":wilson_interval(success,n),
        "per_category":grouped,
        "failure_reason_counts":dict(sorted(reasons.items())),
        "duplicate_native_result_sha_count":evidence["duplicate_result_sha_count"],
        "duplicate_native_run_id_count":evidence["duplicate_run_id_count"],
        "duplicate_source_asset_edit_contract_count":evidence["duplicate_source_contract_count"],
        "total_repair_passes_verified":sum(j.get("repair_passes",0) for j in eligible),
        "total_regeneration_passes_verified":sum(j.get("regeneration_passes",0) for j in eligible),
        "manual_intervention_rate":"NOT_VERIFIABLE_WITHOUT_HUMAN_DECISION_EVIDENCE",
        "critical_false_pass_calibration":"NOT_VERIFIED",
        "human_art_and_rights_review":"NOT_VERIFIED_BY_THIS_REPORT",
        "unity_player":"NOT_VERIFIED_BY_THIS_REPORT",
        "evidence_rule":"real production_audit PASS plus immutable receipt/current QA and unique source/result",
        "steam_approved":False,"commercial_release_certified":False,
        "imagegen_calls_triggered_by_report":0,
        "scope_note":"Pure read-only native Run report; synthetic stubs and direct sessions without formal production audit never qualify.",
        "jobs":jobs,
    }


def markdown(report:dict[str,Any])->str:
    required=report["sample_requirement"]
    out=[
        f"# {report['batch_id']} — v0.13 {report['phase']} sample benchmark",
        "",f"**Status:** {report['status']}",
        f"**Release:** {report['release_state']}","",
        "| Metric | Observed |","| --- | ---: |",
    ]
    metrics=[
        ("Planned jobs",report["planned_jobs"]),
        ("Started jobs (not necessarily native)",report["started_jobs"]),
        ("Independent audited native results",report["independent_audited_native_results"]),
        ("Native art types with evidence",report["unique_categories_with_native_audits"]),
        ("First-pass accepted",report["first_pass_accepted"]),
        ("First-pass observed fraction",report["first_pass_rate_observed"]),
        ("Final observed fraction",report["final_pass_rate_observed"]),
    ]
    out.extend(f"| {name} | {val if val is not None else 'N/A'} |" for name,val in metrics)
    out.extend(["",
        f"Requirements: {required['min_unique_audited']} independently audited outputs, {required['min_categories']} art categories.",
        "",
        "The report does not certify artistic quality, rights, Unity/Steam or future population quality.","",
        "| Category | Planned | Started | Audited Native | First Pass |",
        "| --- | ---: | ---: | ---: | ---: |"])
    for category,info in report["per_category"].items():
        clean=category.replace("|","/").replace("\n"," ")
        out.append(f"| {clean} | {info['planned']} | {info['started']} | "
                   f"{info['audited_native_accepted']} | {info['first_pass_accepted']} |")
    if report["failure_reason_counts"]:
        out.extend(["","## Failure reasons","","| Reason | Count |","| --- | ---: |"])
        out.extend(f"| {reason} | {count} |" for reason,count in report["failure_reason_counts"].items())
    return "\n".join(out)+"\n"


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root",required=True,type=Path)
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--state",required=True,type=Path)
    parser.add_argument("--phase",choices=sorted(PHASES),default="pilot")
    parser.add_argument("--format",choices=["json","markdown"],default="json")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    try:
        root=args.workspace_root.expanduser().resolve()
        manifest=resolve_in_workspace(root,args.manifest)
        state_path=resolve_in_workspace(root,args.state)
        plan=make_plan(manifest,root)
        state=load_state(state_path,plan)
        report=build_report(plan,state,args.phase)
        payload=(json.dumps(report,ensure_ascii=False,indent=2)+"\n"
                 if args.format=="json" else markdown(report))
        if args.output:
            destination=resolve_in_workspace(root,args.output)
            ext=".json" if args.format=="json" else ".md"
            if (destination.suffix.lower()!=ext or destination in (manifest,state_path)
                    or destination.is_symlink() or destination.exists()):
                raise ValidationError("output collides with source or other evidence")
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open("x",encoding="utf8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
        print(payload)
        return 0 if report["status"]=="MEETS_OBSERVED_SAMPLE_COUNT_AND_RATES_ONLY" else 2
    except (OSError,ValueError,KeyError,TypeError,ValidationError):
        print(json.dumps({"status":"BLOCKED","reason":"untrusted_batch_state_or_evidence",
                          "imagegen_calls_triggered":0}))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
