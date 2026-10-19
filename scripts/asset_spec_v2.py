#!/usr/bin/env python3
"""Optional v0.11 typed art intent and immutable inline Style Kit for Image Harness.

This module is deterministic. It makes no image model calls and does not certify
source rights, visual quality, a physical PBR material or Steam approval.
Existing version-one TOML documents remain the external wire schema.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from validate_project import ValidationError

CATEGORIES = {
    "concept_prop": "reference",
    "background": "ingame",
    "ui_icon": "ingame",
    "sprite": "ingame",
    "vfx_sheet": "ingame",
    "texture_candidate": "ingame",
    "steam_capsule": "marketing",
}
TRANSPARENT = {"ui_icon", "sprite", "vfx_sheet"}
TEXTURE_CHANNELS = {"basecolor", "normal", "roughness", "metallic", "mask"}
SPEC_FIELDS = {
    "contract_version", "category", "intended_use", "expected_size",
    "alpha_mode", "color_space", "quality_tier", "texture_channel",
    "required_roles", "authority", "style_kit",
}
KIT_FIELDS = {
    "id", "sha256", "palette", "lighting", "materials", "edge_language",
    "negative_constraints", "game_scale_read",
}
KIT_REQUIRED = KIT_FIELDS - {"sha256"}
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
SIZE = re.compile(r"([1-9][0-9]{0,4})x([1-9][0-9]{0,4})\Z")


def style_fingerprint(style: dict[str, Any]) -> str:
    """Canonical SHA256 of style properties excluding the declared SHA field."""
    contents = {k: v for k, v in style.items() if k != "sha256"}
    payload = json.dumps(contents, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf8")
    return hashlib.sha256(payload).hexdigest()


def _string(value: Any, where: str, max_chars: int = 240) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_chars:
        raise ValidationError(f"{where}: requires nonempty text <= {max_chars} chars")
    return value


def _list(value: Any, where: str, *, nonempty: bool = True) -> list[str]:
    if (not isinstance(value, list) or (nonempty and not value)
            or len(value) > 16 or any(not isinstance(x, str) for x in value)):
        raise ValidationError(f"{where}: requires a bounded list of strings")
    for item in value:
        _string(item, where)
    if len(value) != len(set(value)):
        raise ValidationError(f"{where}: repeated values are not allowed")
    return value


def validate_style_kit(kit: Any, where: str) -> None:
    if not isinstance(kit, dict):
        raise ValidationError(f"{where}: style_kit must be a table")
    if set(kit) != KIT_FIELDS:
        raise ValidationError(f"{where}: style_kit keys are missing or unsupported")
    if not ID.fullmatch(_string(kit.get("id"), f"{where}.id", 48)):
        raise ValidationError(f"{where}: invalid style kit ID")
    _list(kit.get("palette"), f"{where}.palette")
    if any(not HEX_COLOR.fullmatch(x) for x in kit["palette"]):
        raise ValidationError(f"{where}: palette requires six-digit hexadecimal colors")
    _list(kit.get("materials"), f"{where}.materials")
    _list(kit.get("negative_constraints"), f"{where}.negative_constraints")
    for key in ("lighting", "edge_language", "game_scale_read"):
        _string(kit.get(key), f"{where}.{key}")
    claimed = kit.get("sha256")
    if not isinstance(claimed, str) or not SHA.fullmatch(claimed):
        raise ValidationError(f"{where}: missing/invalid style kit SHA256")
    if claimed != style_fingerprint(kit):
        raise ValidationError(f"{where}: style kit SHA mismatch; explicit revision required")


def validate_schema(edit: dict[str, Any], where: str) -> None:
    spec = edit.get("asset_spec_v2")
    if spec is None:
        return
    if not isinstance(spec, dict) or set(spec) - SPEC_FIELDS:
        raise ValidationError(f"{where}: asset_spec_v2 must be a table with known fields")
    if type(spec.get("contract_version")) is not int or spec["contract_version"] != 2:
        raise ValidationError(f"{where}: asset_spec_v2.contract_version must be integer 2")
    category = spec.get("category")
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValidationError(f"{where}: unsupported asset_spec_v2 category")
    if spec.get("intended_use") != CATEGORIES[category]:
        raise ValidationError(f"{where}: category and intended_use conflict")
    raw = spec.get("expected_size")
    match = SIZE.fullmatch(raw) if isinstance(raw, str) else None
    if not match or not all(1 <= int(x) <= 16384 for x in match.groups()):
        raise ValidationError(f"{where}: expected_size must be bounded WxH pixels")
    alpha_mode = spec.get("alpha_mode")
    if not isinstance(alpha_mode, str) or alpha_mode not in {"required", "forbidden", "optional"}:
        raise ValidationError(f"{where}: unsupported alpha_mode")
    if (category in TRANSPARENT and alpha_mode != "required") or (
        category in {"background", "steam_capsule", "texture_candidate"}
        and alpha_mode != "forbidden"
    ):
        raise ValidationError(f"{where}: alpha_mode conflicts with category")
    colorspace = spec.get("color_space")
    if not isinstance(colorspace, str) or colorspace not in {"srgb", "linear"}:
        raise ValidationError(f"{where}: unsupported color_space")
    if not isinstance(spec.get("quality_tier"), str) or spec["quality_tier"] not in {"draft", "production_candidate"}:
        raise ValidationError(f"{where}: quality_tier cannot claim final release")
    if category == "texture_candidate":
        channel = spec.get("texture_channel")
        if not isinstance(channel, str) or channel not in TEXTURE_CHANNELS:
            raise ValidationError(f"{where}: texture_candidate requires texture_channel")
        expected = "srgb" if channel == "basecolor" else "linear"
        if colorspace != expected:
            raise ValidationError(f"{where}: texture_channel and color_space conflict")
    elif "texture_channel" in spec or colorspace != "srgb":
        raise ValidationError(f"{where}: non-texture image must be sRGB and not specify texture_channel")
    roles = _list(spec.get("required_roles"), f"{where}.required_roles", nonempty=False)
    if edit.get("operation") != "create" and not roles:
        raise ValidationError(f"{where}: v2 editing requires explicit reference roles")
    if edit.get("operation") == "create" and roles:
        raise ValidationError(f"{where}: v2 create must not assert preexisting reference authority")
    auth = spec.get("authority", {})
    if not isinstance(auth, dict):
        raise ValidationError(f"{where}: authority must be a table")
    for role, ref_id in auth.items():
        _string(role, f"{where}.authority.role")
        _string(ref_id, f"{where}.authority.{role}")
    if edit.get("operation") == "create" and auth:
        raise ValidationError(f"{where}: create cannot claim approved input reference")
    covered = set(edit.get("reference_sufficiency", {}).get("required_roles", []))
    if covered - set(roles):
        raise ValidationError(f"{where}: v2 required_roles must retain existing reference requirements")
    out = edit.get("output", {})
    if not isinstance(out, dict) or out.get("expected_size") != raw:
        raise ValidationError(f"{where}: output.expected_size must match v2 contract")
    if alpha_mode != "optional" and out.get("require_transparency") is not (alpha_mode == "required"):
        raise ValidationError(f"{where}: output.require_transparency conflicts with v2 alpha")
    if "style_kit" in spec:
        validate_style_kit(spec["style_kit"], f"{where}.asset_spec_v2.style_kit")
    if "style_kit" in spec and edit.get("prompt_intelligence", {}).get("style_profile", "none") != "none":
        raise ValidationError(f"{where}: v2 style kit and legacy style preset are ambiguous")


def authority_map(asset: dict[str, Any], edit: dict[str, Any]) -> dict[str, str]:
    spec = edit.get("asset_spec_v2")
    if not spec:
        return {}
    selected: dict[str, list[str]] = defaultdict(list)
    for binding in edit.get("reference_bindings", []):
        for role in binding["roles"]:
            selected[role].append(binding["reference_id"])
    explicit = spec.get("authority", {})
    declared = {r["id"]: r for r in asset.get("references", [])}
    for role, ref in explicit.items():
        if ref not in selected.get(role, []):
            raise ValidationError(f"v2 authority {role}: {ref} not selected for this role")
        if declared.get(ref, {}).get("state") != "approved":
            raise ValidationError(f"v2 authority {role}: reference is not approved")
    missing = set(spec["required_roles"]) - set(selected)
    if missing:
        raise ValidationError(f"v2 required roles not covered: {sorted(missing)}")
    result = {}
    for role in sorted(selected):
        options = selected[role]
        if len(options) > 1 and role not in explicit:
            raise ValidationError(f"ambiguous {role} role authority: explicitly choose an approved reference")
        result[role] = explicit.get(role, options[0])
    for role, ref in explicit.items():
        if role not in result:
            raise ValidationError(f"v2 authority {role} is not a reference role")
    return result


def validate_bindings(asset: dict[str, Any], edit: dict[str, Any], where: str) -> None:
    if not edit.get("asset_spec_v2"):
        return
    authority = authority_map(asset, edit)
    old = edit.get("prompt_intelligence", {}).get("role_authority", {})
    for role, ref in old.items():
        if authority.get(role) != ref:
            raise ValidationError(f"{where}: authority conflict between v2 and legacy prompt control")


def packet_contract(asset: dict[str, Any], edit: dict[str, Any]) -> dict[str, Any] | None:
    spec = edit.get("asset_spec_v2")
    if not spec:
        return None
    result = {k: spec[k] for k in (
        "contract_version", "category", "intended_use", "expected_size", "alpha_mode",
        "color_space", "quality_tier", "required_roles",
    )}
    if "texture_channel" in spec:
        result["texture_channel"] = spec["texture_channel"]
    result["role_authority"] = authority_map(asset, edit)
    kit = spec.get("style_kit")
    if kit:
        result["style_kit_id"] = kit["id"]
        result["style_kit_sha256"] = kit["sha256"]
        result["style_guidance"] = {
            k: kit[k] for k in ("palette", "lighting", "materials", "edge_language",
                                 "negative_constraints", "game_scale_read")
        }
    result["scope"] = "art-production candidate, not Unity/Steam approval"
    return result


def format_brief(asset: dict[str, Any], edit: dict[str, Any]) -> str:
    result = packet_contract(asset, edit)
    if not result:
        return ""
    lines = [
        "ASSET SPEC V2 (opt-in; binding art intent, never a new authoritative Master):",
        f"- category / intended use: {result['category']} / {result['intended_use']}",
        f"- output: {result['expected_size']}; alpha={result['alpha_mode']}; color={result['color_space']}",
        f"- quality_tier: {result['quality_tier']} (not Unity or Steam certification)",
        "REFERENCE ROLE AUTHORITY:",
    ]
    lines.extend(f"- {role}: {ref}" for role, ref in result["role_authority"].items())
    lines.append("No unseen geometry may be invented from a single view or style hint.")
    if result.get("texture_channel"):
        lines.extend([f"- texture data channel: {result['texture_channel']}",
                      "- This is a texture appearance candidate, not a verified PBR material."])
    if result.get("style_kit_sha256"):
        g = result["style_guidance"]
        lines.extend([
            f"FROZEN PROJECT STYLE KIT: {result['style_kit_id']} SHA256={result['style_kit_sha256']}",
            "- Palette: " + ", ".join(g["palette"]),
            "- Lighting: " + g["lighting"],
            "- Material language: " + ", ".join(g["materials"]),
            "- Edge language: " + g["edge_language"],
            "- Game-scale readability: " + g["game_scale_read"],
        ])
        lines.extend("- Avoid: " + x for x in g["negative_constraints"])
    lines.extend([
        "PRIORITY: approved Master/geometry/camera + hard preserve > requested delta > style kit.",
        "Style kit cannot authorize geometry changes or fill unknown reference evidence.",
    ])
    return "\n".join(lines)


def repair_guard(edit: dict[str, Any]) -> str:
    spec = edit.get("asset_spec_v2")
    if not spec:
        return ""
    kit = spec.get("style_kit")
    return "\n".join([
        "ASSET SPEC V2 REPAIR BOUNDARY:",
        f"- retain approved v2 style {kit['id']} SHA256={kit['sha256']}" if kit else
        "- retain all previously approved style and material decisions",
        f"- keep category={spec['category']} and target={spec['expected_size']} unchanged",
        "- repair only failed deltas; do not restyle or replace the approved Master.",
    ])


def scaffold(category: str, asset_id: str, output_dir: Path) -> dict[str, Any]:
    from asset_spec_scaffold import scaffold as create
    return create(category, asset_id, output_dir)


def readonly_style_hash(path: Path) -> dict[str, str]:
    from asset_spec_scaffold import readonly_style_hash as compute
    return compute(path)



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    inspect = actions.add_parser("inspect")
    inspect.add_argument("--asset", type=Path, required=True)
    inspect.add_argument("--edit", type=Path, required=True)
    create = actions.add_parser("scaffold")
    create.add_argument("--category", required=True)
    create.add_argument("--asset-id", required=True)
    create.add_argument("--out", type=Path, required=True)
    hashed = actions.add_parser("style-hash")
    hashed.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "scaffold":
            print(json.dumps(scaffold(args.category, args.asset_id, args.out)))
            return 0
        if args.action == "style-hash":
            print(json.dumps(readonly_style_hash(args.json)))
            return 0
        from validate_project import load_document, validate_document, cross_validate
        asset, edit = load_document(args.asset), load_document(args.edit)
        for item in (asset, edit):
            validate_document(item.data, item.path)
        cross_validate([asset, edit])
        contract = packet_contract(asset.data, edit.data)
        if contract is None:
            value = {"status": "LEGACY_V1", "commercial_release_certified": False}
        else:
            value = {"status": "V2_CONTRACT_VALIDATED", "asset_spec_v2": contract,
                     "commercial_release_certified": False,
                     "native_imagegen_invoked": False, "visual_qa": "NOT_TESTED"}
        print(json.dumps(value, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        print(json.dumps({"status": "BLOCKED", "message": "Invalid asset specification or evidence"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
