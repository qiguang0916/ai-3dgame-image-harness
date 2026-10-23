#!/usr/bin/env python3
"""One entrypoint to the image-harness workflows; deterministic tools only."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

USAGE = """AI 3D Game Image Harness v0.14-dev (real native production + exact region QA)
Usage: ai-3dgame-image-harness <command> [options]

Commands:
  produce check|run|status  Check private references, then native ImageGen → QA → real audit
  autopilot run|status      Bounded native Codex subscription production loop
  batch validate|run|status|unity-stage  Audited commercial source / image batch
  batch-benchmark <options> Read-only native batch KPI, confidence intervals (JSON/Markdown)
  asset-spec inspect|scaffold|style-hash  Typed AssetSpec v2, draft starters and style SHA
  precision-compose <options>  SHA-bound strict ROI compositing, review required
  precision-report <options>   Quantitative raw/composited A/B evidence and seam heatmaps
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
  styles                    List curated, task-specific game art profiles
  reference-review <opts>   Issue SHA-bound Host visual inspection questions
  prompt-check <options>   Check authority/conflicts and real reference digests
  render-views --source ...  Render canonical GLB geometry references (Blender)
  canonical-qa --manifest ... Validate 4 source-bound views and visible silhouettes
  commercial-gate <opts>  Fail-closed Steam commercial asset evidence review
  unity-proof <opts>      Verify independent seven-category same-commit Unity release evidence
  player-capture <opts>    Capture actual Unity Player A/B inspection screenshots
  production-audit <opts>   Rehash real Host ImageGen receipts, QA and native source evidence
  version                  Print tool version

Autopilot delegates generation to native Codex built-in imagegen.
There is no automatic API fallback.
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"help", "-h", "--help"}:
        print(USAGE)
        return 0
    command, rest = args[0], args[1:]
    if command == 'produce':
        from simple_produce import main as produce
        return produce(rest)
    if command == 'autopilot':
        from production_autopilot import main as autopilot
        return autopilot(rest)
    if command == 'batch':
        from batch_production import main as batch
        return batch(rest)
    if command == 'batch-benchmark':
        from batch_benchmark import main as benchmark
        return benchmark(rest)
    if command == 'asset-spec':
        from asset_spec_v2 import main as asset_spec
        return asset_spec(rest)
    if command == 'precision-compose':
        from precision_composite import main as precision
        return precision(rest)
    if command == 'precision-report':
        from precision_quality import main as precision_quality
        return precision_quality(rest)
    if command == "version":
        print("ai-3dgame-image-harness 0.14.0-dev")
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
    if command in {"render-views", "canonical-qa"}:
        import argparse
        from commercial_art_gate import verify_canonical_views
        from pathlib import Path
        parser = argparse.ArgumentParser(prog=f"ai-3dgame-image-harness {command}")
        if command == "render-views":
            parser.add_argument("--source",required=True,type=Path)
            parser.add_argument("--output-dir",required=True,type=Path)
            parser.add_argument("--blender",type=Path)
        else:
            parser.add_argument("--manifest",required=True,type=Path)
        p = parser.parse_args(rest)
        if command == "render-views":
            import shutil
            import subprocess
            blender = p.blender or shutil.which("blender")
            if blender is None:
                fallback = Path("/Applications/Blender.app/Contents/MacOS/blender")
                blender = fallback if fallback.is_file() else None
            if blender is None:
                print("BLOCKED: Blender optional renderer is not installed",file=sys.stderr)
                return 2
            if p.output_dir.exists() and any(p.output_dir.iterdir()):
                print("BLOCKED: refusing to overwrite existing view evidence",file=sys.stderr)
                return 2
            commandline = [
                str(blender), "-b", "-t", "2", "--python",
                str(ROOT/"scripts"/"blender_canonical_views.py"),
                "--", "--source", str(p.source), "--out", str(p.output_dir),
            ]
            try:
                subprocess.run(commandline,check=True,timeout=120,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
                print(f"BLOCKED: canonical render failed: {exc}",file=sys.stderr)
                return 2
            manifest = p.output_dir/"manifest.json"
        else:
            manifest = p.manifest
        result = verify_canonical_views(manifest)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result["status"]=="PASS" else 2
    from validate_project import main as validate
    from next_action import main as next_action
    from execution_loop import main as loop
    from master_lifecycle import main as master
    from region_quality import main as region
    from asset_report import main as report
    from commercial_art_gate import main as commercial_gate
    from unity_release_bridge import main as unity_proof
    from unity_player_capture import main as player_capture
    from production_audit import main as production_audit
    from prompt_control import main as prompt_control
    actions={
        "styles": (prompt_control, ["styles", *rest]),
        "reference-review": (prompt_control, ["reference-review", *rest]),
        "prompt-check": (prompt_control, ["prompt-check", *rest]),
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
        "commercial-gate":(commercial_gate,rest),
        "unity-proof":(unity_proof,rest),
        "player-capture":(player_capture,rest),
        "production-audit":(production_audit,rest),
    }
    if command not in actions:
        print(f"Unsupported command: {command}\n\n{USAGE}",file=sys.stderr)
        return 2
    fn,params=actions[command]
    return fn(params)


if __name__=="__main__":
    raise SystemExit(main())
