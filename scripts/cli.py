#!/usr/bin/env python3
"""One entrypoint to the image-harness workflows; deterministic tools only."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

USAGE = """AI 3D Game Image Harness v0.6 (OpenAI host-native imagegen)
Usage: ai-3dgame-image-harness <command> [options]

Commands:
  doctor                    Check local deterministic QA dependencies
  validate [files...]      Validate TOML manifest/edit/QA contracts
  init <options>           Create an auditable run (execution_loop.py init)
  next <options>           Issue a Host Action Packet (next_action.py)
  generated <options>      Record host result + receipt (mark-generated)
  qa <options>             Apply receipt-bound visual QA (apply-qa)
  status <options>         Display run state
  block <options>          Persist BLOCKED with reason
  master <subcommand...>   candidate | finalize | register-first
  region-qa <options>      Measure bounded image-region preservation
  asset-report <options>   Check PNG dimensions and alpha against edit contract
  version                  Print tool version

This CLI does NOT generate images; use the official Codex/OpenAI built-in
$imagegen skill for generation and editing, with no automatic API fallback.
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"help", "-h", "--help"}:
        print(USAGE)
        return 0
    command, rest = args[0], args[1:]
    if command == "version":
        print("ai-3dgame-image-harness 0.6.0-dev")
        return 0
    if command == "doctor":
        modules={name: bool(importlib.util.find_spec(name)) for name in ("PIL", "numpy", "cv2", "skimage")}
        ready=modules["PIL"] and modules["numpy"]
        print(json.dumps({
            "tool": "ai-3dgame-image-harness", "status":"ready" if ready else "limited",
            "modules": modules,
            "real_host_imagegen": "NOT_VERIFIED (must be checked inside Codex host)",
            "notes":"Pillow+NumPy required for objective region/technical image QA; OpenCV optional.",
        }, indent=2))
        return 0 if ready else 2
    from validate_project import main as validate
    from next_action import main as next_action
    from execution_loop import main as loop
    from master_lifecycle import main as master
    from region_quality import main as region
    from asset_report import main as report
    actions={
        "validate":(validate,rest),
        "init":(loop,["init",*rest]),
        "next":(next_action,rest),
        "generated":(loop,["mark-generated",*rest]),
        "qa":(loop,["apply-qa",*rest]),
        "status":(loop,["status",*rest]),
        "block":(loop,["mark-blocked",*rest]),
        "master":(master,rest),
        "region-qa":(region,rest),
        "asset-report":(report,rest),
    }
    if command not in actions:
        print(f"Unsupported command: {command}\n\n{USAGE}",file=sys.stderr)
        return 2
    fn,params=actions[command]
    return fn(params)


if __name__=="__main__":
    raise SystemExit(main())
