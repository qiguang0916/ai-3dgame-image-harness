#!/usr/bin/env python3
"""Read-only bridge for the independent ai-3dgame-test-harness release gate.

Checks all seven same-commit evidence classes and actual artifact SHA-256
before producing a Unity Player proof summary. Does not build Unity, simulate
input, or claim that a screenshot is visually genuine on its own.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote

from validate_project import ValidationError

REQUIRED_CATEGORIES = (
    "unity-editor", "game-physics", "player-visual", "os-input",
    "paper-cut", "performance", "nondev-build",
)
SOURCE_FOR_CATEGORY = {
    "unity-editor": {"live-unity-mcp"},
    "player-visual": {"real-macos-unity-player"},
    "os-input": {"native-macos-input"},
    "game-physics": {"real-macos-unity-player", "live-unity-mcp"},
}
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


def _artifact(uri: object) -> Path:
    if not isinstance(uri, str):
        raise ValidationError("release artifact is missing local file URI")
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        raise ValidationError("release evidence must reference a local file:// artifact")
    path = Path(unquote(parsed.path)).resolve()
    if not path.is_file():
        raise ValidationError("release evidence artifact is missing")
    if not 0 < path.stat().st_size <= 256 * 1024 * 1024:
        raise ValidationError("release evidence artifact has invalid size")
    return path


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_valid_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def verify_test_harness_release(manifest: dict, *, expected_commit: str) -> dict:
    problems = []
    statuses = []
    candidate_capture = None

    if not isinstance(expected_commit, str) or not COMMIT.fullmatch(expected_commit):
        raise ValidationError("expected game commit must be a full lowercase 40-character SHA")
    if not isinstance(manifest, dict):
        raise ValidationError("release manifest must be a JSON object")
    if manifest.get("expectedCommit") != expected_commit:
        problems.append("release manifest expectedCommit mismatches actual game commit")
    evidence = manifest.get("evidence")
    if not isinstance(evidence, list):
        raise ValidationError("release manifest requires evidence array")

    for category in REQUIRED_CATEGORIES:
        entries = [x for x in evidence if isinstance(x, dict) and x.get("category") == category]
        if not entries:
            problems.append(f"{category}: no evidence")
            continue
        valid = []
        for item in entries:
            failures = []
            if item.get("commitSha") != expected_commit:
                failures.append("wrong game commit")
            if item.get("passed") is not True or item.get("verified") is not True:
                failures.append("not passing verified evidence")
            if not _is_valid_timestamp(item.get("capturedAt")):
                failures.append("invalid capture timestamp")
            if category in SOURCE_FOR_CATEGORY and item.get("source") not in SOURCE_FOR_CATEGORY[category]:
                failures.append("untrusted source classification")
            if category == "nondev-build" and item.get("developmentBuild") is not False:
                failures.append("non-development build not proven")
            declared = item.get("sha256")
            if not isinstance(declared, str) or not SHA.fullmatch(declared):
                failures.append("invalid digest")
            artifact = None
            try:
                artifact = _artifact(item.get("artifactUri"))
                if isinstance(declared, str) and _digest(artifact) != declared:
                    failures.append("artifact SHA-256 mismatch")
            except (OSError, ValidationError) as exc:
                failures.append(type(exc).__name__ + ": invalid/unreadable evidence artifact")
            if failures:
                problems.append(f"{category}: " + "; ".join(failures))
                continue
            valid.append((item, artifact))
        if not valid:
            problems.append(f"{category}: no verified passing artifact for this commit")
        else:
            statuses.append(category)
        # The image harness requires the player-visual proof to point directly
        # to a real PNG/JPEG file, not just a JSON manifest claiming screenshot.
        if category == "player-visual" and valid:
            for item, artifact in valid:
                if artifact.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                    continue
                try:
                    from PIL import Image
                    with Image.open(artifact) as im:
                        im.load()
                        if im.width < 640 or im.height < 360:
                            continue
                    candidate_capture = {
                        "path": str(artifact), "sha256": item["sha256"],
                        "commitSha": expected_commit,
                    }
                    break
                except (OSError, ValueError):
                    continue
            if candidate_capture is None:
                problems.append("player-visual: verified Unity Player PNG/JPEG screenshot file missing")

    seen = [x.get("category") for x in evidence if isinstance(x, dict)]
    unknown = sorted({x for x in seen if x not in REQUIRED_CATEGORIES})
    if unknown:
        problems.append("unrecognized evidence categories: " + ", ".join(str(x) for x in unknown))
    status = "PASS" if not problems and len(statuses) == len(REQUIRED_CATEGORIES) else "BLOCKED"
    return {
        "schema_version": 1, "status": status,
        "expected_commit": expected_commit,
        "verified_categories": statuses, "required_categories": list(REQUIRED_CATEGORIES),
        "player_capture": candidate_capture,
        "failures": problems,
        "steam_approved": False,
        "scope": "Artifact hashes/source labels validated; independent player authenticity, image aesthetics and legal rights require review",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--commit", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        if args.output.exists():
            raise ValidationError("refusing to overwrite existing Unity proof report")
        source = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = verify_test_harness_release(source, expected_commit=args.commit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(json.dumps({"status": result["status"], "failures": result["failures"]}, ensure_ascii=False))
        return 0 if result["status"] == "PASS" else 2
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
