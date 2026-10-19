#!/usr/bin/env python3
"""v0.10 fail-closed batch driver for the existing native Codex ImageGen autopilot."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from artifact_integrity import resolve_in_workspace, sha256_file, receipt_digest
from execution_loop import _exclusive_run_lock, init_from_paths, load_run
from production_autopilot import drive
from production_audit import audit_run
from validate_project import ValidationError

ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMERCIAL_LICENSES = {
    "CC0-1.0", "CC-BY-4.0", "MIT", "Apache-2.0",
    "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD",
}

def read_json(path):
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValidationError("missing or oversized JSON")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError("JSON root must be an object")
    return value

def bound_file(root, value, suffix=None):
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise ValidationError("manifest inputs must be workspace-relative files")
    p = resolve_in_workspace(root, value)
    if not p.is_file() or (suffix and p.suffix.lower() != suffix):
        raise ValidationError("missing or wrong-type workspace input")
    return p

def reviewed_rights(root, value):
    if not isinstance(value, dict):
        raise ValidationError("missing source-rights review")
    basis, license_id = value.get("basis"), value.get("license_id")
    permitted = (
        (basis == "user_owned" and license_id == "USER_OWNED") or
        (basis == "openai_generated_reference" and license_id == "OPENAI_OUTPUT_TERMS_REVIEWED") or
        (basis == "commercial_licensed" and license_id in COMMERCIAL_LICENSES)
    )
    if not permitted:
        raise ValidationError("unknown/noncommercial source license BLOCKED")
    if basis == "commercial_licensed" and license_id == "CC-BY-4.0":
        attribution = value.get("attribution")
        if not isinstance(attribution, str) or len(attribution.strip()) < 8:
            raise ValidationError("CC-BY licensed input requires recorded attribution")
    reviewer = value.get("reviewer")
    if (value.get("review_status") != "REVIEWED_FOR_COMMERCIAL_USE"
            or value.get("commercial_use_reviewed") is not True
            or not isinstance(reviewer, str) or len(reviewer.strip()) < 3):
        raise ValidationError("explicit responsible human rights review required")
    evidence = value.get("evidence")
    if not isinstance(evidence, dict):
        raise ValidationError("missing review evidence SHA")
    file = bound_file(root, evidence.get("path"))
    digest = evidence.get("sha256")
    if not isinstance(digest, str) or not SHA.fullmatch(digest) or sha256_file(file) != digest:
        raise ValidationError("rights evidence SHA mismatch")
    return {
        "basis": basis, "license_id": license_id, "reviewer": reviewer.strip(),
        "attribution": value.get("attribution", ""),
        "evidence": {"path": str(file.relative_to(root)), "sha256": digest},
        "status": "RECORD_CHECKED_NOT_LEGAL_CERTIFICATION",
    }

def make_plan(manifest_path, root):
    root = Path(root).expanduser().resolve()
    source = resolve_in_workspace(root, manifest_path)
    manifest = read_json(source)
    batch_id = manifest.get("batch_id")
    jobs = manifest.get("jobs")
    if (manifest.get("schema_version") != 1 or not isinstance(batch_id, str)
            or not ID.fullmatch(batch_id) or not isinstance(jobs, list)
            or not 1 <= len(jobs) <= 128):
        raise ValidationError("invalid batch contract")
    seen, prepared = set(), []
    for job in jobs:
        if not isinstance(job, dict):
            raise ValidationError("invalid job")
        ident = job.get("id")
        if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in seen:
            raise ValidationError("unsafe/duplicate job id")
        seen.add(ident)
        asset = bound_file(root, job.get("asset"), ".toml")
        edit = bound_file(root, job.get("edit"), ".toml")
        rights = reviewed_rights(root, job.get("rights"))
        preflight = init_from_paths(asset, edit, workspace_root=root)
        prepared.append({
            "id": ident, "asset": str(asset.relative_to(root)),
            "edit": str(edit.relative_to(root)), "asset_sha256": sha256_file(asset),
            "edit_sha256": sha256_file(edit), "rights": rights,
            "preflight": preflight["state"],
            "preflight_reason": (preflight.get("blocker") or {}).get("reason_code"),
            "input_spec_sha256": preflight.get("input_spec_sha256"),
            "run": f".ai-3dgame-image-harness/batches/{batch_id}/jobs/{ident}.json",
        })
    return {
        "schema_version": 1, "batch_id": batch_id, "workspace_root": str(root),
        "manifest": str(source.relative_to(root)), "manifest_sha256": sha256_file(source),
        "jobs": prepared,
    }

def verify_run_binding(run, spec, root):
    """Reject stale or swapped Run state before reusing/staging it."""
    return (
        run.get("auditable") is True and
        run.get("workspace_root") == str(root) and
        run.get("asset_document_path") == spec["asset"] and
        run.get("edit_document_path") == spec["edit"] and
        run.get("input_spec_sha256") == spec["input_spec_sha256"]
    )

def verify_accepted_evidence(run, spec, root):
    """Recheck accepted receipt, pixels and QA before reporting a green job.

    This is a *local integrity* check, not proof of native model origin or
    commercial QA. Production staging still requires production_audit.
    """
    if not verify_run_binding(run, spec, root) or run.get("state") != "ACCEPTED":
        return False
    receipt, qa = run.get("current_receipt"), run.get("last_qa")
    if not isinstance(receipt, dict) or not isinstance(qa, dict):
        return False
    if receipt.get("receipt_id") != receipt_digest(receipt):
        return False
    target = receipt.get("result")
    if not isinstance(target, dict) or not isinstance(target.get("path"), str):
        return False
    image = resolve_in_workspace(root, target["path"])
    if not image.is_file() or sha256_file(image) != receipt.get("result_sha256"):
        return False
    if (qa.get("status") not in {"PASS", "PASS_WITH_NOTES"}
            or qa.get("receipt_id") != receipt["receipt_id"]
            or qa.get("result_sha256") != receipt["result_sha256"]):
        return False
    required = run.get("required_hard_gates")
    if not isinstance(required, list) or not required:
        return False
    gates = {g.get("name"): g.get("status") for g in qa.get("gates", []) if isinstance(g, dict)}
    return all(gates.get(name) == "PASS" for name in required)


def save_state(path, value, new=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    if new:
        with path.open("x", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    else:
        fd, temp = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

def load_state(path, plan):
    value = read_json(path)
    jobs = value.get("jobs")
    if (value.get("schema_version") != 1 or value.get("plan") != plan
            or not isinstance(jobs, list) or len(jobs) != len(plan["jobs"])):
        raise ValidationError("resume plan, review SHA or batch state changed")
    for state_job, planned in zip(jobs, plan["jobs"]):
        if (not isinstance(state_job, dict) or state_job.get("id") != planned["id"]
                or state_job.get("status") not in {"PENDING", "PAUSED", "ACCEPTED", "BLOCKED", "ERROR"}):
            raise ValidationError("malformed job state")
    return value

def summarize(value):
    counts = Counter(j["status"] for j in value["jobs"])
    status = ("BLOCKED" if counts["BLOCKED"] or counts["ERROR"] else
              "ASSETS_ACCEPTED_NOT_STEAM_CERTIFIED" if counts["ACCEPTED"] == len(value["jobs"])
              else "IN_PROGRESS")
    return {
        "batch_id": value["plan"]["batch_id"], "state": status,
        "counts": {k: counts[k] for k in ("PENDING", "PAUSED", "ACCEPTED", "BLOCKED", "ERROR")},
        "steam_approved": False, "commercial_release_certified": False,
    }

def checked_status(state_path):
    """Report status only after revalidating original plan and accepted bytes.

    This path is intentionally read-only: it may refuse a stale success but
    never modifies a journal or invokes an image model.
    """
    source = Path(state_path).expanduser().resolve()
    snapshot = read_json(source)
    stored = snapshot.get("plan")
    if not isinstance(stored, dict) or not isinstance(snapshot.get("jobs"), list):
        raise ValidationError("invalid batch status file")
    root = Path(stored["workspace_root"]).expanduser().resolve()
    resolve_in_workspace(root, source)
    plan = make_plan(stored["manifest"], root)
    state = load_state(source, plan)
    for spec, job in zip(plan["jobs"], state["jobs"]):
        if job["status"] == "ACCEPTED":
            accepted = load_run(resolve_in_workspace(root, spec["run"]))
            if not verify_accepted_evidence(accepted, spec, root):
                raise ValidationError("accepted batch integrity changed")
    return summarize(state)


def run_batch(manifest, workspace_root, state_path, *, resume=False, max_jobs=8, max_actions=8, host=None):
    root = Path(workspace_root).expanduser().resolve()
    state_path = resolve_in_workspace(root, state_path)
    if not 1 <= max_jobs <= 128 or not 1 <= max_actions <= 100:
        raise ValidationError("invalid bounded action budget")
    with _exclusive_run_lock(state_path):
        plan = make_plan(manifest, root)
        if resume:
            state = load_state(state_path, plan)
        else:
            if state_path.exists() or state_path.is_symlink():
                raise ValidationError("existing batch requires --resume")
            # A missing batch pointer is NOT evidence that earlier model calls
            # never ran. Never recreate it over orphan runs or host events.
            for spec in plan["jobs"]:
                orphan = resolve_in_workspace(root, spec["run"])
                evidence = orphan.with_name(orphan.name + ".production")
                if orphan.exists() or orphan.is_symlink() or evidence.exists() or evidence.is_symlink():
                    raise ValidationError("orphan batch Run/Host evidence requires manual reconciliation")
            state = {"schema_version": 1, "plan": plan,
                     "jobs": [{"id": j["id"], "status": "PENDING"} for j in plan["jobs"]]}
            save_state(state_path, state, new=True)
        invoked = 0
        for spec, job in zip(plan["jobs"], state["jobs"]):
            if job["status"] == "ACCEPTED":
                # A stale ACCEPTED row is only a journal pointer, not proof.
                # In particular, missing/swapped runs must never remain green.
                try:
                    accepted = load_run(resolve_in_workspace(root, spec["run"]))
                    if not verify_accepted_evidence(accepted, spec, root):
                        raise ValidationError("accepted Run or output evidence changed")
                except (OSError, ValueError, KeyError, TypeError):
                    job.update(status="ERROR", reason="accepted_run_missing_or_changed")
                    save_state(state_path, state)
                continue
            if invoked >= max_jobs or job["status"] in {"BLOCKED", "ERROR"}:
                continue
            if spec["preflight"] == "BLOCKED":
                job.update(status="BLOCKED", reason=spec["preflight_reason"])
                save_state(state_path, state)
                continue
            run = resolve_in_workspace(root, spec["run"])
            if run.exists():
                try:
                    previous = load_run(run)
                    if not verify_run_binding(previous, spec, root):
                        raise ValidationError("existing Run does not match immutable task")
                    if previous["state"] in {"ACCEPTED", "BLOCKED"}:
                        if previous["state"] == "ACCEPTED" and not verify_accepted_evidence(previous, spec, root):
                            raise ValidationError("prior accepted output evidence changed")
                        job["status"] = previous["state"]
                        save_state(state_path, state)
                        continue
                except (OSError, ValueError, KeyError, TypeError):
                    job.update(status="ERROR", reason="invalid_existing_run")
                    save_state(state_path, state)
                    continue
            job["status"] = "PAUSED"
            save_state(state_path, state)
            try:
                result = drive(resolve_in_workspace(root, spec["asset"]),
                               resolve_in_workspace(root, spec["edit"]), root, run,
                               resume=run.exists(), max_actions=max_actions, host=host)
                status = result["state"]
                job["status"] = status if status in {"BLOCKED", "ACCEPTED"} else (
                    "ERROR" if status == "ERROR" else "PAUSED")
                job["run_state"] = status
            except (OSError, ValueError, KeyError, TypeError):
                # Do not persist host diagnostics/secrets or automatically retry.
                job.update(status="ERROR", reason="partial_evidence_reconciliation_required")
            save_state(state_path, state)
            invoked += 1
        return summarize(state)

def stage_unity(manifest, workspace_root, state_path, output_dir, codex_home=None):
    root = Path(workspace_root).expanduser().resolve()
    state_path = resolve_in_workspace(root, state_path)
    dest = resolve_in_workspace(root, output_dir)
    with _exclusive_run_lock(state_path):
        plan = make_plan(manifest, root)
        state = load_state(state_path, plan)
        if dest.exists() or any(j["status"] != "ACCEPTED" for j in state["jobs"]):
            raise ValidationError("output already exists or assets not all ACCEPTED")
        ready = []
        for job in plan["jobs"]:
            run_path = resolve_in_workspace(root, job["run"])
            run = load_run(run_path)
            if not verify_accepted_evidence(run, job, root):
                raise ValidationError("staging Run, receipt or PNG evidence invalid")
            audit = audit_run(run_path, codex_home=codex_home)
            if run["state"] != "ACCEPTED" or audit["status"] != "PASS":
                raise ValidationError("no independent native ImageGen audit PASS")
            receipt = run["current_receipt"]
            image = resolve_in_workspace(root, receipt["result"]["path"])
            if sha256_file(image) != receipt["result_sha256"]:
                raise ValidationError("image differs from recorded native receipt")
            ready.append((job, receipt, image))
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix="." + dest.name + ".", dir=dest.parent))
        try:
            entries = []
            for job, receipt, image in ready:
                target = temp / (job["id"] + ".png")
                shutil.copyfile(image, target)
                if sha256_file(target) != receipt["result_sha256"]:
                    raise ValidationError("PNG stage copy SHA mismatch")
                entries.append({
                    "job_id": job["id"], "asset_kind": "ingame_2d_asset",
                    "image": target.name, "sha256": sha256_file(target),
                    "native_receipt_id": receipt["receipt_id"], "source_run": job["run"],
                    "rights_review": job["rights"], "production_audit": "PASS",
                })
            metadata = {
                "schema_version": 1, "batch_id": plan["batch_id"], "assets": entries,
                "unity_import": "NOT_TESTED", "unity_seven_category_qa": "REQUIRED",
                "human_visual_review": "REQUIRED", "steam_ai_disclosure": "REQUIRED_WHERE_APPLICABLE",
                "steam_approved": False, "commercial_release_certified": False,
            }
            (temp / "unity-staging-manifest.json").write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            if dest.exists():
                raise ValidationError("concurrent Unity output appeared")
            temp.rename(dest)
            return {"state": "STAGED_NOT_UNITY_VERIFIED", "output": str(dest),
                    "assets": len(entries), "commercial_release_certified": False}
        finally:
            if temp.exists():
                shutil.rmtree(temp)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for mode in ("validate", "run", "status", "unity-stage"):
        cmd = commands.add_parser(mode)
        if mode == "status":
            cmd.add_argument("--state", type=Path, required=True)
        else:
            cmd.add_argument("--manifest", type=Path, required=True)
            cmd.add_argument("--workspace-root", type=Path, required=True)
            if mode != "validate":
                cmd.add_argument("--state", type=Path, required=True)
        if mode == "run":
            cmd.add_argument("--resume", action="store_true")
            cmd.add_argument("--max-jobs", type=int, default=8)
            cmd.add_argument("--max-actions", type=int, default=8)
            cmd.add_argument("--codex")
        if mode == "unity-stage":
            cmd.add_argument("--output-dir", type=Path, required=True)
            cmd.add_argument("--codex-home", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "validate":
            plan = make_plan(args.manifest, args.workspace_root)
            blocked = [j["id"] for j in plan["jobs"] if j["preflight"] == "BLOCKED"]
            result = {"state": "BLOCKED" if blocked else "VALID", "preflight_blocked": blocked,
                      "imagegen_invoked": False, "commercial_release_certified": False}
            rc = 2 if blocked else 0
        elif args.action == "run":
            from native_codex_host import NativeCodexHost
            result = run_batch(args.manifest, args.workspace_root, args.state,
                               resume=args.resume, max_jobs=args.max_jobs,
                               max_actions=args.max_actions, host=NativeCodexHost(args.codex))
            rc = 0 if result["state"] == "ASSETS_ACCEPTED_NOT_STEAM_CERTIFIED" else (
                2 if result["state"] == "BLOCKED" else 3)
        elif args.action == "status":
            result, rc = checked_status(args.state), 0
        else:
            result = stage_unity(args.manifest, args.workspace_root, args.state,
                                 args.output_dir, codex_home=args.codex_home)
            rc = 0
        print(json.dumps(result, ensure_ascii=False))
        return rc
    except (OSError, ValueError, TypeError, KeyError, ValidationError):
        print(json.dumps({"state": "ERROR", "message": "Invalid source rights, plan, evidence or state; no retry."}))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
