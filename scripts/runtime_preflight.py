#!/usr/bin/env python3
"""Runtime validation for real image inputs used by ai-3dgame-image-harness."""

from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path
from typing import Any

from artifact_integrity import (
    png_metadata,
    resolve_in_workspace,
    sha256_file,
)
from validate_project import ValidationError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _validate_png(path: Path) -> tuple[bool, str]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return False, f"unreadable: {exc.__class__.__name__}"

    if not data.startswith(PNG_SIGNATURE):
        return False, "invalid PNG signature"

    pos = len(PNG_SIGNATURE)
    seen_ihdr = False
    seen_iend = False
    idat = bytearray()

    try:
        while pos < len(data):
            if pos + 12 > len(data):
                return False, "truncated PNG chunk"
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            kind = data[pos + 4:pos + 8]
            start = pos + 8
            end = start + length
            crc_end = end + 4
            if crc_end > len(data):
                return False, "truncated PNG payload"
            payload = data[start:end]
            expected_crc = struct.unpack(">I", data[end:crc_end])[0]
            actual_crc = zlib.crc32(kind)
            actual_crc = zlib.crc32(payload, actual_crc) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                return False, "PNG CRC mismatch"

            if kind == b"IHDR":
                if seen_ihdr or length != 13:
                    return False, "invalid PNG IHDR"
                width, height = struct.unpack(">II", payload[:8])
                if width <= 0 or height <= 0:
                    return False, "invalid PNG dimensions"
                seen_ihdr = True
            elif kind == b"IDAT":
                idat.extend(payload)
            elif kind == b"IEND":
                seen_iend = True
                break

            pos = crc_end

        if not seen_ihdr or not seen_iend or not idat:
            return False, "missing required PNG chunks"
        zlib.decompress(bytes(idat))
    except (struct.error, zlib.error):
        return False, "PNG decode failed"

    return True, "png"


def validate_image_file(path: Path) -> tuple[bool, str]:
    if path.suffix.lower() != ".png":
        return False, "unsupported image format; guaranteed runtime support is PNG"
    return _validate_png(path)


def _resolve(base_dir: Path, raw_path: str) -> Path:
    return resolve_in_workspace(base_dir, raw_path)


def _selected_reference_ids(edit: dict[str, Any]) -> list[str]:
    return [
        binding["reference_id"]
        for binding in edit.get("reference_bindings", [])
    ]


def evaluate_reference_sufficiency(
    edit: dict[str, Any],
) -> dict[str, Any]:
    contract = edit.get("reference_sufficiency", {})
    required_roles = list(contract.get("required_roles", []))
    covered_roles: list[str] = []
    seen: set[str] = set()
    for binding in edit.get("reference_bindings", []):
        for role in binding.get("roles", []):
            if role not in seen:
                seen.add(role)
                covered_roles.append(role)

    missing_roles = [
        role for role in required_roles if role not in seen
    ]
    allow_provisional = bool(contract.get("allow_provisional", False))
    provisional_fields = list(contract.get("provisional_fields", []))
    prohibited_assumptions = list(
        contract.get("prohibited_assumptions", [])
    )
    from game_art_contract import reference_visual_coverage
    visual = reference_visual_coverage(edit)
    status = (
        "insufficient" if visual["status"] == "insufficient"
        else "sufficient" if not missing_roles
        else ("provisional" if allow_provisional else "insufficient")
    )
    return {
        "visual_review": visual,
        "status": status,
        "required_roles": required_roles,
        "covered_roles": [
            role for role in required_roles if role in seen
        ],
        "missing_roles": missing_roles,
        "provisional_fields": provisional_fields,
        "prohibited_assumptions": prohibited_assumptions,
    }


def run_preflight(
    asset: dict[str, Any],
    edit: dict[str, Any],
    base_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Check real inputs before allowing a host image action."""
    base_dir = Path(base_dir).expanduser().resolve()
    sufficiency = evaluate_reference_sufficiency(edit)

    if sufficiency["status"] == "insufficient":
        return {
            "status": "BLOCKED",
            "dry_run": dry_run,
            "reason_code": "reference_sufficiency_failed",
            "checks": [],
            "reference_sufficiency": sufficiency,
            "workspace_root": str(base_dir),
        }

    refs = {ref["id"]: ref for ref in asset.get("references", [])}
    selected_ids = _selected_reference_ids(edit)
    target_id = edit.get("execution", {}).get("edit_target_reference_id")

    ordered_ids: list[str] = []
    if target_id:
        ordered_ids.append(target_id)
    for ref_id in selected_ids:
        if ref_id not in ordered_ids:
            ordered_ids.append(ref_id)

    for ref_id in ordered_ids:
        ref = refs.get(ref_id)
        if ref is not None:
            try:
                _resolve(base_dir, ref["path"])
            except ValidationError as exc:
                return {
                    "status": "BLOCKED",
                    "dry_run": dry_run,
                    "reason_code": "path_outside_workspace",
                    "checks": [],
                    "reference_sufficiency": sufficiency,
                    "workspace_root": str(base_dir),
                    "detail": str(exc),
                }

    if dry_run:
        # A dry run may compile prompts, but does not inspect or hash actual
        # reference pixels. Never present host observations as real verification.
        result = {
            "status": "PASS",
            "dry_run": True,
            "reason_code": None,
            "checks": [],
            "reference_sufficiency": sufficiency,
            "workspace_root": str(base_dir),
        }
        if edit.get("prompt_intelligence"):
            result["prompt_intelligence"] = {
                "status": "NOT_VERIFIED_DRY_RUN",
                "observations_checked": 0,
            }
        return result

    checks: list[dict[str, Any]] = []

    for ref_id in ordered_ids:
        ref = refs.get(ref_id)
        if ref is None or ref.get("state") != "approved":
            return {
                "status": "BLOCKED",
                "dry_run": False,
                "reason_code": (
                    "edit_target_missing"
                    if ref_id == target_id
                    else "required_reference_missing"
                ),
                "checks": checks,
                "reference_sufficiency": sufficiency,
                "workspace_root": str(base_dir),
            }

        resolved = _resolve(base_dir, ref["path"])
        is_target = ref_id == target_id

        if not resolved.exists():
            return {
                "status": "BLOCKED",
                "dry_run": False,
                "reason_code": (
                    "edit_target_missing"
                    if is_target
                    else "required_reference_missing"
                ),
                "checks": checks,
                "reference_sufficiency": sufficiency,
                "workspace_root": str(base_dir),
                "path": str(resolved),
            }
        if not resolved.is_file() or not os.access(resolved, os.R_OK):
            return {
                "status": "BLOCKED",
                "dry_run": False,
                "reason_code": "reference_unreadable",
                "checks": checks,
                "reference_sufficiency": sufficiency,
                "workspace_root": str(base_dir),
                "path": str(resolved),
            }

        valid, detail = validate_image_file(resolved)
        if not valid:
            return {
                "status": "BLOCKED",
                "dry_run": False,
                "reason_code": "reference_image_invalid",
                "checks": checks,
                "reference_sufficiency": sufficiency,
                "workspace_root": str(base_dir),
                "path": str(resolved),
                "detail": detail,
            }

        actual_sha256 = sha256_file(resolved)
        declared_sha256 = ref.get("content_sha256")
        if declared_sha256 is not None and declared_sha256 != actual_sha256:
            return {
                "status": "BLOCKED",
                "dry_run": False,
                "reason_code": "reference_digest_mismatch",
                "checks": checks,
                "reference_sufficiency": sufficiency,
                "workspace_root": str(base_dir),
                "path": str(resolved),
                "expected_sha256": declared_sha256,
                "actual_sha256": actual_sha256,
            }

        checks.append(
            {
                "reference_id": ref_id,
                "path": str(resolved),
                "kind": "edit_target" if is_target else "support_reference",
                "status": "PASS",
                "format": detail,
                "sha256": actual_sha256,
                "png": png_metadata(resolved),
            }
        )

    prompt_state = None
    if edit.get("prompt_intelligence"):
        from prompt_control import verify_observation_bindings
        prompt_state = verify_observation_bindings(edit, checks)
        if prompt_state["status"] != "VERIFIED_DIGEST_ONLY":
            return {
                "status": "BLOCKED",
                "dry_run": False,
                "reason_code": "reference_digest_mismatch",
                "checks": checks,
                "reference_sufficiency": sufficiency,
                "workspace_root": str(base_dir),
                "prompt_intelligence": prompt_state,
                "detail": "; ".join(prompt_state["failures"]),
            }

    result = {
        "status": "PASS",
        "dry_run": False,
        "reason_code": None,
        "checks": checks,
        "reference_sufficiency": sufficiency,
        "workspace_root": str(base_dir),
    }
    if prompt_state is not None:
        result["prompt_intelligence"] = prompt_state
    return result
