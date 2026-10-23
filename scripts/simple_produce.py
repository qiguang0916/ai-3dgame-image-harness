#!/usr/bin/env python3
"""Thin product entrypoint: existing native Codex autopilot + independent audit.

No new image model, prompting engine, state machine, repair policy, or QA.
An ACCEPTED state without a real native production-audit PASS is NOT delivery.
This is a technical image candidate, NOT human art/rights/Unity/Steam approval.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import execution_loop
from artifact_integrity import png_metadata, resolve_in_workspace, sha256_file
from native_codex_host import NativeCodexHost
from production_audit import audit_run
from production_autopilot import drive
from runtime_preflight import run_preflight
from validate_project import ValidationError, load_document


def _in_workspace(root: Path, value: Path) -> Path:
    value = Path(value).expanduser()
    if not value.is_absolute():
        value = root / value
    return resolve_in_workspace(root, value)


def inspect_source_inputs(root: Path, asset_path: Path, edit_path: Path) -> dict[str, Any]:
    """Read-only inventory using the EXISTING runtime preflight. No Run or Host."""
    asset = load_document(asset_path).data
    edit = load_document(edit_path).data
    if asset.get("asset_id") != edit.get("asset_id"):
        raise ValidationError("asset and edit identity mismatch")
    refs = {ref["id"]: ref for ref in asset.get("references", [])}
    wanted: list[str] = []
    target = edit.get("execution", {}).get("edit_target_reference_id")
    if target:
        wanted.append(target)
    for binding in edit.get("reference_bindings", []):
        key = binding["reference_id"]
        if key not in wanted:
            wanted.append(key)
    inputs = []
    for ref_id in wanted:
        ref = refs.get(ref_id)
        if ref is None:
            inputs.append({"reference_id": ref_id, "status": "NOT_DECLARED"})
            continue
        relative = ref["path"]
        actual = _in_workspace(root, Path(relative))
        exists = actual.is_file() and not actual.is_symlink()
        inputs.append({
            "reference_id": ref_id,
            "declared_path": relative,
            "declared_state": ref.get("state"),
            "status": "SOURCE_PRESENT_NOT_AUTHORITY_VERIFIED" if exists else "MISSING_SOURCE",
        })
    preflight = run_preflight(asset, edit, root, dry_run=False)
    return {
        "asset_id": asset["asset_id"],
        "technical_preflight": preflight["status"],
        "reason_code": preflight.get("reason_code"),
        "selected_reference_count": len(inputs),
        "selected_references": inputs,
        "original_master_authority": "NOT_VERIFIED_BY_BYTES_ALONE",
        "codex_imagegen_calls": 0,
        "run_state_written": False,
        "release_ready": False,
        "steam_approved": False,
    }


def summary(run_path: Path) -> dict[str, Any]:
    """Report exactly what is independently proven, and never promote a Master."""
    run = execution_loop.load_run(Path(run_path))
    state = run.get("state")
    status = "IN_PROGRESS"
    failures: list[str] = []
    output = None
    digest = None
    evidence = None
    if state == "BLOCKED":
        status = "BLOCKED"
    elif state == "ERROR":
        status = "BLOCKED"
    elif state == "ACCEPTED":
        evidence = audit_run(Path(run_path))
        status = evidence.get("status", "BLOCKED")
        if status == "PASS":
            receipt = run.get("current_receipt") or {}
            image = receipt.get("result") or {}
            digest = receipt.get("result_sha256")
            output = str(resolve_in_workspace(Path(run["workspace_root"]), image["path"]))
        else:
            failures = list(evidence.get("failures", []))[:8]
    result = {
        "run_id": run.get("run_id"),
        "run_state": state,
        "technical_audit": status,
        "output_png": output,
        "output_sha256": digest,
        "machine_visual_qa": (run.get("last_qa") or {}).get("status"),
        "next_action": run.get("next_action"),
        "blocker": run.get("blocker"),
        "audit_failures": failures,
        "human_art_approval": "REQUIRED_NOT_VERIFIED",
        "source_rights": "NOT_VERIFIED",
        "unity_in_game": "NOT_VERIFIED",
        "steam_approved": False,
        "commercial_release": "BLOCKED",
        "scope": "technical image candidate only; immutable original/Mask and proof retained",
    }
    return result


EXPORT_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def export_technical_candidate(run_path: Path, export_name: str) -> dict[str, Any]:
    """Re-audit a real native Run before writing one immutable technical PNG export.

    Never copies a Master, mutates the Run, promotes a candidate, or reports
    human/rights/Steam approval. Exports only within the Run's own workspace.
    """
    if not isinstance(export_name, str) or not EXPORT_NAME_RE.fullmatch(export_name):
        raise ValidationError("export name must be a safe single path component")
    run_path = Path(run_path).expanduser().resolve()
    state = execution_loop.load_run(run_path)
    root = Path(state["workspace_root"]).expanduser().resolve()
    if resolve_in_workspace(root, run_path) != run_path:
        raise ValidationError("run is not inside its declared workspace")

    exports = resolve_in_workspace(root, "exports")
    destination = resolve_in_workspace(root, exports / export_name)
    if (destination.parent != exports or destination.exists()
            or destination.is_symlink() or destination == root):
        raise ValidationError("export path is not a new safe workspace folder")

    # Technical output only: no success or copy before actual independent audit.
    inspected = summary(run_path)
    if inspected["run_state"] != "ACCEPTED" or inspected["technical_audit"] != "PASS":
        raise ValidationError("not an independently accepted native image Run")

    source = resolve_in_workspace(root, inspected["output_png"])
    expected_sha = inspected["output_sha256"]
    if (not source.is_file() or not expected_sha or
            sha256_file(source) != expected_sha or source.suffix.lower() != ".png"):
        raise ValidationError("source PNG vanished or digest differs after audit")
    info = png_metadata(source)
    receipt = state["current_receipt"]
    if (not isinstance(receipt, dict) or receipt.get("result_sha256") != expected_sha
            or not isinstance(receipt.get("receipt_id"), str)):
        raise ValidationError("export receipt is not the independently audited output")

    # Exports are write-once and stay in the private Run workspace.
    exports.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.mkdir(mode=0o700, exist_ok=False)
    exported = destination / "candidate.png"
    with source.open("rb") as src, exported.open("xb") as target:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            target.write(block)
        target.flush()
        os.fsync(target.fileno())
    if sha256_file(exported) != expected_sha or sha256_file(source) != expected_sha:
        raise ValidationError("export source/output altered; partial export is not usable")

    meta = {
        "schema_version": 1,
        "status": "AUDITED_TECHNICAL_CANDIDATE_NOT_COMMERCIAL_APPROVAL",
        "run_id": inspected["run_id"],
        "run_json_relative": str(run_path.relative_to(root)),
        "run_json_sha256_at_export": sha256_file(run_path),
        "receipt_id": receipt["receipt_id"],
        "image": {
            "name": "candidate.png",
            "sha256": expected_sha,
            "width": info["width"],
            "height": info["height"],
            "bytes": info["byte_size"],
        },
        "independent_production_audit": "PASS",
        "machine_visual_qa": inspected["machine_visual_qa"],
        "source_rights": "NOT_VERIFIED",
        "human_art_approval": "REQUIRED_NOT_VERIFIED",
        "unity_in_game": "NOT_VERIFIED",
        "steam_approved": False,
        "commercial_release": "BLOCKED",
        "provenance_note": (
            "The private Run retains native ImageGen/Mask/Receipt/QA evidence; "
            "this export only copies the SHA-bound result and does not certify the art."
        ),
    }
    manifest = destination / "manifest.json"
    with manifest.open("x", encoding="utf8") as out:
        json.dump(meta, out, indent=2, ensure_ascii=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return {
        "status": "AUDITED_TECHNICAL_CANDIDATE_ONLY",
        "png": str(exported),
        "sha256": expected_sha,
        "manifest": str(manifest),
        "manifest_sha256": sha256_file(manifest),
        "technical_audit": "PASS",
        "commercial_release": "BLOCKED",
        "steam_approved": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-3dgame-image-harness produce",
        description="One real native Codex image job. Automatic machine QA and independent audit; no commercial certification.",
    )
    actions = parser.add_subparsers(dest="action", required=True)
    check = actions.add_parser("check", help="Read-only source preflight; no Run or Codex calls")
    check.add_argument("--workspace-root", type=Path, required=True)
    check.add_argument("--asset", type=Path, required=True)
    check.add_argument("--edit", type=Path, required=True)
    produce = actions.add_parser("run", help="Start or explicitly resume one technical image job")
    produce.add_argument("--workspace-root", type=Path, required=True)
    produce.add_argument("--asset", type=Path, required=True,
                         help="Existing immutable asset.toml inside workspace")
    produce.add_argument("--edit", type=Path, required=True,
                         help="Existing edit.toml inside workspace")
    produce.add_argument("--run", type=Path, help="Default: workspace-root/run.json")
    produce.add_argument("--resume", action="store_true")
    produce.add_argument("--max-actions", type=int, default=8)
    produce.add_argument("--codex", help="Existing authenticated Codex executable; no API fallback")
    export = actions.add_parser("export", help="Copy audited PNG and technical manifest; no Master promotion")
    export.add_argument("--run", required=True, type=Path)
    export.add_argument("--name", required=True, help="Private exports/<name>/, single safe path component")
    status = actions.add_parser("status", help="Read-only latest state and re-audit accepted output")
    status.add_argument("--workspace-root", type=Path)
    status.add_argument("--run", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.action == "check":
            root = args.workspace_root.expanduser().resolve()
            if not root.is_dir():
                raise ValidationError("workspace must already exist")
            asset = _in_workspace(root, args.asset)
            edit = _in_workspace(root, args.edit)
            if not asset.is_file() or not edit.is_file():
                raise ValidationError("asset/edit manifest absent")
            report = inspect_source_inputs(root, asset, edit)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["technical_preflight"] == "PASS" else 2
        if args.action == "export":
            exported = export_technical_candidate(args.run, args.name)
            print(json.dumps(exported, indent=2, ensure_ascii=False))
            return 0
        if args.action == "run":
            root = args.workspace_root.expanduser().resolve()
            if not root.is_dir():
                raise ValidationError("workspace must already exist")
            asset = _in_workspace(root, args.asset)
            edit = _in_workspace(root, args.edit)
            state_file = _in_workspace(root, args.run or Path("run.json"))
            if not asset.is_file() or not edit.is_file():
                raise ValidationError("asset/edit manifest absent")
            # Existing v0.13 engine handles run locking, SHA/Mask/Rcpt,
            # bounded repair, and fail-closed ambiguous Host actions.
            drive(asset, edit, root, state_file, resume=args.resume,
                  max_actions=args.max_actions, host=NativeCodexHost(args.codex))
        else:
            if args.run is None and args.workspace_root is None:
                raise ValidationError("status requires --run or --workspace-root")
            root = args.workspace_root.expanduser().resolve() if args.workspace_root else None
            state_file = (_in_workspace(root, args.run or Path("run.json"))
                          if root else args.run.expanduser().resolve())
            if state_file is None:
                raise ValidationError("run path missing")
        report = summary(state_file)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if report["technical_audit"] == "PASS":
            return 0
        return 2 if report["technical_audit"] == "BLOCKED" else 3
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        # Never print provider secrets, local absolute paths or host transcripts
        # from untrusted exception messages.
        print(json.dumps({
            "technical_audit": "BLOCKED",
            "commercial_release": "BLOCKED",
            "reason": "INVALID_INPUT_OR_UNAUDITABLE_RUN",
            "message": "Inspect the original Run safely; no automatic host retry.",
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
