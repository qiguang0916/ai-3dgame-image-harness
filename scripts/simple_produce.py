#!/usr/bin/env python3
"""Thin product entrypoint: existing native Codex autopilot + independent audit.

No new image model, prompting engine, state machine, repair policy, or QA.
An ACCEPTED state without a real native production-audit PASS is NOT delivery.
This is a technical image candidate, NOT human art/rights/Unity/Steam approval.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import execution_loop
from artifact_integrity import resolve_in_workspace
from native_codex_host import NativeCodexHost
from production_audit import audit_run
from production_autopilot import drive
from validate_project import ValidationError


def _in_workspace(root: Path, value: Path) -> Path:
    value = Path(value).expanduser()
    if not value.is_absolute():
        value = root / value
    return resolve_in_workspace(root, value)


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-3dgame-image-harness produce",
        description="One real native Codex image job. Automatic machine QA and independent audit; no commercial certification.",
    )
    actions = parser.add_subparsers(dest="action", required=True)
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
    status = actions.add_parser("status", help="Read-only latest state and re-audit accepted output")
    status.add_argument("--workspace-root", type=Path)
    status.add_argument("--run", type=Path)
    args = parser.parse_args(argv)

    try:
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
