#!/usr/bin/env python3
"""v0.7 opt-in prompt & reference authority control for host-native imagegen.

IMPORTANT: this module has no image-generation client and does not infer visual
facts from local pixels. Host vision observations must be supplied and digest
bound to approved real input files; a digest match does NOT prove the claim.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from validate_project import ValidationError

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "data" / "game-style-profiles.json"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
KNOWN_FIELDS = {
    "mode", "style_profile", "role_authority", "observations",
    "count_requests", "camera_change",
}
OBS_FIELDS = {
    "reference_id", "source_sha256", "inspected_pixels", "subject",
    "camera", "composition", "visible_features", "materials",
    "palette", "unknowns",
}
CAMERA_LOCK_TERMS = ("camera", "projection", "framing", "viewpoint", "view direction",
                     "相机", "视角", "镜头", "投影")
DEFAULT_STYLE = {
    "hero_prop_reference": "studio_hero_prop",
    "game_asset_reference": "studio_hero_prop",
    "background": "workshop_background",
    "ui_art": "game_ui_icon",
    "sprite": "game_sprite", "sprite_sheet": "game_sprite",
    "texture_reference": "pbr_texture_reference",
}


def style_profiles() -> dict[str, dict[str, Any]]:
    data = json.loads(PROFILES.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValidationError("invalid style-profile library version")
    profiles = data.get("profiles", [])
    ids = [p["id"] for p in profiles]
    if len(ids) != len(set(ids)):
        raise ValidationError("duplicate style-profile ids")
    return {p["id"]: p for p in profiles}


def resolve_style_profile(chosen: str, edit: dict[str, Any]) -> dict[str, Any] | None:
    profiles = style_profiles()
    if chosen == "none":
        return None
    if chosen == "auto":
        # An existing image Master, not a suggested preset, owns visual identity.
        if edit.get("operation") != "create":
            return None
        purpose = edit.get("art_direction", {}).get(
            "purpose", edit.get("output", {}).get("purpose")
        )
        chosen = DEFAULT_STYLE.get(purpose, "")
        if not chosen:
            return None
    if chosen not in profiles:
        raise ValidationError(f"unsupported game-art style profile '{chosen}'")
    return profiles[chosen]


def _text(value: Any, where: str, *, required: bool = True) -> None:
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > 500:
        raise ValidationError(f"{where}: expected short nonempty text (max 500 chars)")


def _strings(value: Any, where: str, *, allow_empty: bool = True) -> None:
    if not isinstance(value, list):
        raise ValidationError(f"{where}: expected array of strings")
    if not allow_empty and not value:
        raise ValidationError(f"{where}: must not be empty")
    if len(value) > 24:
        raise ValidationError(f"{where}: too many statements")
    for item in value:
        _text(item, where)


def reference_digest_for(path: Path) -> str:
    from artifact_integrity import sha256_file
    return sha256_file(Path(path))


def validate_prompt_control_schema(edit: dict[str, Any], where: str) -> None:
    control = edit.get("prompt_intelligence")
    if control is None:
        return
    if not isinstance(control, dict):
        raise ValidationError(f"{where}: prompt_intelligence must be TOML table")
    unknown = set(control) - KNOWN_FIELDS
    if unknown:
        raise ValidationError(f"{where}: unknown prompt_intelligence fields {sorted(unknown)}")
    if control.get("mode") != "guided":
        raise ValidationError(f"{where}: prompt_intelligence.mode must be guided")
    chosen = control.get("style_profile", "none")
    if not isinstance(chosen, str):
        raise ValidationError(f"{where}: style_profile must be a string")
    if chosen not in {"none", "auto", *style_profiles().keys()}:
        raise ValidationError(f"{where}: invalid style_profile '{chosen}'")
    authority = control.get("role_authority", {})
    if not isinstance(authority, dict):
        raise ValidationError(f"{where}: role_authority must be TOML table")
    for role, reference in authority.items():
        _text(role, f"{where}.role_authority.role")
        _text(reference, f"{where}.role_authority.{role}")

    observations = control.get("observations", [])
    if not isinstance(observations, list) or len(observations) > 12:
        raise ValidationError(f"{where}: observations must be an array (max 12)")
    seen: set[str] = set()
    for i, item in enumerate(observations):
        point = f"{where}: prompt_intelligence.observations[{i}]"
        if not isinstance(item, dict) or set(item) - OBS_FIELDS:
            raise ValidationError(f"{point}: unrecognized fields")
        rid = item.get("reference_id")
        _text(rid, f"{point}.reference_id")
        if rid in seen:
            raise ValidationError(f"{point}: duplicate inspected reference_id")
        seen.add(rid)
        digest = item.get("source_sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValidationError(f"{point}: source_sha256 must be lowercase 64-digit SHA256")
        if item.get("inspected_pixels") is not True:
            raise ValidationError(f"{point}: cannot use an observation without host pixel inspection")
        for field in ("subject", "camera", "composition"):
            _text(item.get(field), f"{point}.{field}")
        for field in ("visible_features", "materials", "palette", "unknowns"):
            _strings(item.get(field, []), f"{point}.{field}",
                     allow_empty=(field != "visible_features"))

    observation_text_total = sum(
        len(observation.get(field, ""))
        for observation in observations
        for field in ("subject", "camera", "composition")
    ) + sum(
        len(item)
        for observation in observations
        for field in ("visible_features", "materials", "palette", "unknowns")
        for item in observation.get(field, [])
    )
    if observation_text_total > 4000:
        raise ValidationError(f"{where}: visual observations exceed 4000 chars; select key facts")

    counts = control.get("count_requests", [])
    if not isinstance(counts, list) or len(counts) > 30:
        raise ValidationError(f"{where}: count_requests must be array (max 30)")
    seen_counts: set[str] = set()
    for i, entry in enumerate(counts):
        point = f"{where}: count_requests[{i}]"
        if not isinstance(entry, dict) or set(entry) != {"component_id", "count"}:
            raise ValidationError(f"{point}: requires only component_id and count")
        _text(entry["component_id"], f"{point}.component_id")
        if entry["component_id"] in seen_counts:
            raise ValidationError(f"{point}: repeated component count request")
        seen_counts.add(entry["component_id"])
        count = entry["count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValidationError(f"{point}: count must be nonnegative integer")
    if "camera_change" in control and not isinstance(control["camera_change"], bool):
        raise ValidationError(f"{where}: camera_change must be a boolean")


def resolve_role_authority(asset: dict[str, Any], edit: dict[str, Any]) -> dict[str, str]:
    control = edit.get("prompt_intelligence")
    if not control:
        return {}
    selected: dict[str, list[str]] = defaultdict(list)
    for bound in edit.get("reference_bindings", []):
        for role in bound.get("roles", []):
            selected[role].append(bound["reference_id"])
    explicit = control.get("role_authority", {})
    for role, ref_id in explicit.items():
        if role not in selected or ref_id not in selected[role]:
            raise ValidationError(f"role authority {role}: '{ref_id}' is not a selected reference for that role")
    result = {}
    for role in sorted(selected):
        options = selected[role]
        if len(options) > 1 and role not in explicit:
            raise ValidationError(
                f"ambiguous {role} reference authority ({', '.join(options)}); "
                "select one role_authority explicitly"
            )
        result[role] = explicit.get(role, options[0])
    for observation in control.get("observations", []):
        if observation["reference_id"] not in {b["reference_id"] for b in edit.get("reference_bindings", [])}:
            raise ValidationError(f"observed reference {observation['reference_id']} is not a selected input")
    return result


def validate_prompt_control_bindings(asset: dict[str, Any], edit: dict[str, Any],
                                      where: str) -> None:
    control = edit.get("prompt_intelligence")
    if not control:
        return
    resolve_role_authority(asset, edit)
    components = {
        comp["id"]: comp
        for comp in asset.get("topology", {}).get("components", [])
    }
    for change in control.get("count_requests", []):
        comp_id, count = change["component_id"], change["count"]
        component = components.get(comp_id)
        if component is None or component.get("count") is None:
            raise ValidationError(f"{where}: count request for unknown/unconstrained component '{comp_id}'")
        if component["count"] != count:
            raise ValidationError(
                f"{where}: count conflict for {comp_id}: approved topology "
                f"expects {component['count']}, request declares {count}; "
                "revise and approve topology contract before generating"
            )
    if control.get("camera_change"):
        locks = " ".join([
            *asset.get("locks", {}).get("hard", []),
            *edit.get("preserve", {}).get("hard", [])
        ]).lower()
        if any(term in locks for term in CAMERA_LOCK_TERMS):
            raise ValidationError(f"{where}: camera change conflicts with hard locked camera/view/framing")


def verify_observation_bindings(edit: dict[str, Any],
                                checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify observed image digests only, never claim semantic vision accuracy."""
    control = edit.get("prompt_intelligence", {})
    observations = control.get("observations", [])
    by_id = {c["reference_id"]: c for c in checks}
    failures = []
    for observation in observations:
        ref_id = observation["reference_id"]
        check = by_id.get(ref_id)
        if check is None or check["sha256"] != observation["source_sha256"]:
            failures.append(f"visual observation for {ref_id} does not match current input sha256")
    return {
        "status":"FAILED_DIGEST_BINDING" if failures else "VERIFIED_DIGEST_ONLY",
        "observations_checked":len(observations),
        "failures":failures,
        "note":"Input digest verified; host-declared visual facts are not independently certified.",
    }


def format_prompt_intelligence(asset: dict[str, Any], edit: dict[str, Any]) -> str:
    control = edit.get("prompt_intelligence")
    if not control:
        return ""
    authority = resolve_role_authority(asset, edit)
    lines = ["PROMPT INTELLIGENCE (host visual observations, digest-bound inputs):"]
    if authority:
        lines.append("ROLE AUTHORITY:")
        for role, ref_id in sorted(authority.items()):
            lines.append(f"- {role}: {ref_id}")
    for item in control.get("observations", []):
        lines.extend([
            f"INSPECTED REFERENCE: {item['reference_id']} (SHA256 {item['source_sha256'][:16]}...)",
            f"- visible subject: {item['subject']}",
            f"- observed camera: {item['camera']}",
            f"- observed composition: {item['composition']}",
        ])
        lines.extend(f"- visible feature: {x}" for x in item["visible_features"])
        lines.extend(f"- observed material: {x}" for x in item.get("materials", []))
        lines.extend(f"- observed palette: {x}" for x in item.get("palette", []))
        lines.extend(f"- UNKNOWN — do not invent: {x}" for x in item.get("unknowns", []))
    profile = resolve_style_profile(control.get("style_profile", "none"), edit)
    if profile:
        lines.extend(["STYLE GUIDANCE (subordinate, not a new design instruction):",
                      f"- profile: {profile['id']} — {profile['description']}"])
        lines.extend(f"- {x}" for x in profile["guidance"])
    lines.extend([
        "PRIORITY: Approved Master & HARD PRESERVE > requested delta > verified reference facts > soft art style.",
        "Do not override HARD PRESERVE, geometry, component counts, camera locks, or reference authority with style inspiration.",
        "Do not infer an unseen back view, interior, thickness, or mating surface from a single view.",
        "For a local edit, change only the declared target; avoid re-styling the entire object.",
    ])
    return "\n".join(lines)


def repair_authority_guidance(asset: dict[str, Any], edit: dict[str, Any]) -> str:
    if not edit.get("prompt_intelligence"):
        return ""
    roles = resolve_role_authority(asset, edit)
    return "\n".join([
        "REFERENCE AUTHORITY FOR REPAIR:",
        *(f"- {role}: {ref_id}" for role, ref_id in sorted(roles.items())),
        "Never apply a new style profile during a localized repair.",
        "Preserve all already-passed geometry, layout, crop, and material gates.",
    ])


def color_swatch_hints(path: Path, *, max_colors: int = 5) -> list[dict[str, Any]]:
    """Small deterministic image swatches, NOT inferred material identity."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValidationError("reference review requires Pillow for color hints") from exc
    with Image.open(path) as source:
        source.load()
        rgb = source.convert("RGB")
        rgb.thumbnail((96, 96))
        palette_image = rgb.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
        palette = palette_image.getpalette()
        counts = sorted(palette_image.getcolors() or [], reverse=True)
        total = sum(count for count, _ in counts)
        if not total or palette is None:
            return []
        return [
            {
                "hex": "#{:02x}{:02x}{:02x}".format(*palette[idx * 3 : idx * 3 + 3]),
                "fraction": round(count / total, 4),
            }
            for count, idx in counts[:max_colors]
        ]


def reference_review_packet(asset: dict[str, Any], edit: dict[str, Any],
                             workspace_root: Path) -> dict[str, Any]:
    """Issue real-input inspection questions for the host's vision, not local AI."""
    from runtime_preflight import run_preflight
    from artifact_integrity import workspace_relative
    check = run_preflight(asset, edit, workspace_root, dry_run=False)
    if check["status"] != "PASS":
        raise ValidationError("reference review blocked by real preflight: "
                              + str(check.get("reason_code")))
    roles = {b["reference_id"]: b["roles"] for b in edit.get("reference_bindings",[])}
    return {
        "schema_version":1, "action":"host_vision_reference_review",
        "execution":"no local model invoked",
        "asset_id":asset["asset_id"], "request_id":edit["request_id"],
        "workspace_root":str(Path(workspace_root).resolve()),
        "instruction":"Host must inspect actual pixels, fill only visible facts and mark hidden/unknowns. "
                      "Write prompt_intelligence observations back to edit TOML with the exact bound digest. "
                      "Do not infer hidden geometry or claim independent automated verification.",
        "references":[{
            "reference_id":c["reference_id"],
            "path":workspace_relative(workspace_root,c["path"]),
            "sha256":c["sha256"],
            "png":c["png"],
            "color_swatch_hints":color_swatch_hints(Path(c["path"])),
            "color_note":"Raw image swatches may include background/lighting; NOT authoritative material colors.",
            "roles":roles.get(c["reference_id"],[]),
            "inspection_fields":["subject","camera","composition","visible_features",
                                 "materials","palette","unknowns"],
        } for c in check["checks"] if c["reference_id"] in roles],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("styles")
    review = sub.add_parser("reference-review")
    review.add_argument("--asset",type=Path,required=True)
    review.add_argument("--edit",type=Path,required=True)
    review.add_argument("--workspace-root",type=Path,required=True)
    check = sub.add_parser("prompt-check")
    check.add_argument("--asset",type=Path,required=True)
    check.add_argument("--edit",type=Path,required=True)
    check.add_argument("--workspace-root",type=Path,required=True)
    check.add_argument("--dry-run",action="store_true")
    args = parser.parse_args(argv)
    if args.command == "styles":
        print(json.dumps(style_profiles(),ensure_ascii=False,indent=2))
        return 0
    try:
        from validate_project import load_document, validate_document, cross_validate
        asset=load_document(args.asset)
        edit=load_document(args.edit)
        for doc in (asset, edit):
            validate_document(doc.data,doc.path)
        cross_validate([asset,edit])
        if args.command=="reference-review":
            output=reference_review_packet(asset.data,edit.data,args.workspace_root)
        else:
            from runtime_preflight import run_preflight
            preflight=run_preflight(asset.data,edit.data,args.workspace_root,dry_run=args.dry_run)
            profile=resolve_style_profile(
                edit.data.get("prompt_intelligence",{}).get("style_profile","none"),
                edit.data
            )
            output={
                "status":preflight["status"],
                "reason_code":preflight.get("reason_code"),
                "style_profile":profile["id"] if profile else None,
                "role_authority":resolve_role_authority(asset.data,edit.data),
                "observation_digest":preflight.get("prompt_intelligence"),
                "host_imagegen":"not called",
            }
        print(json.dumps(output,ensure_ascii=False,indent=2))
        return 0 if output.get("status","PASS")=="PASS" or args.command=="reference-review" else 2
    except (ValidationError,OSError,ValueError) as exc:
        print(f"BLOCKED: {exc}",file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
