"""Lightweight, optional game-art and visual-reference evidence contract."""
from __future__ import annotations
import re
from typing import Any
from validate_project import ValidationError


VALID_PURPOSES = {
    "hero_prop_reference", "concept_art", "background", "ui_art", "texture_reference",
    "sprite", "sprite_sheet", "marketing_art", "game_asset_reference",
}


def _words(items: Any, where: str) -> list[str]:
    if not isinstance(items,list) or any(not isinstance(x,str) or not x.strip() for x in items):
        raise ValidationError(f"{where}: expected a list of non-empty strings")
    return items


def validate_art_and_output(edit: dict[str, Any], where: str) -> None:
    art=edit.get("art_direction")
    if art is not None:
        if not isinstance(art,dict):
            raise ValidationError(f"{where}: art_direction must be a table")
        if art.get("purpose") not in VALID_PURPOSES:
            raise ValidationError(f"{where}: art_direction.purpose must be supported")
        for field in ("style_family","camera","lighting","game_scale_read"):
            if not isinstance(art.get(field),str) or not art[field].strip():
                raise ValidationError(f"{where}: art_direction.{field} must be nonempty")
        for field in ("palette","material_notes"):
            _words(art.get(field),f"{where}: art_direction.{field}")
        if not isinstance(art.get("must_match",False),bool):
            raise ValidationError(f"{where}: art_direction.must_match must be boolean")

    ref=edit.get("reference_evidence")
    if ref is not None:
        if not isinstance(ref,dict):
            raise ValidationError(f"{where}: reference_evidence must be a table")
        if not isinstance(ref.get("required"),bool):
            raise ValidationError(f"{where}: reference_evidence.required must be boolean")
        observations=ref.get("observations",[])
        if not isinstance(observations,list):
            raise ValidationError(f"{where}: reference_evidence.observations must be array")
        known_ids=set()
        for i,o in enumerate(observations):
            point=f"{where}: reference_evidence.observations[{i}]"
            if not isinstance(o,dict):
                raise ValidationError(f"{point}: expected table")
            ref_id=o.get("reference_id")
            if not isinstance(ref_id,str) or not ref_id.strip() or ref_id in known_ids:
                raise ValidationError(f"{point}: reference_id must be unique nonempty")
            known_ids.add(ref_id)
            _words(o.get("roles"),point+".roles")
            facts=_words(o.get("visible_facts"),point+".visible_facts")
            if not facts:
                raise ValidationError(f"{point}: requires actual visible_facts")
            _words(o.get("unknowns",[]),point+".unknowns")

    out=edit.get("output",{})
    if out:
        if not isinstance(out,dict):
            raise ValidationError(f"{where}: output must be a table")
        size=out.get("expected_size")
        if size is not None:
            if not isinstance(size,str) or not re.fullmatch(r"[1-9][0-9]{0,4}x[1-9][0-9]{0,4}",size):
                raise ValidationError(f"{where}: expected_size must be WxH in pixels")
            w,h=map(int,size.split("x"))
            if not (1<=w<=16384 and 1<=h<=16384):
                raise ValidationError(f"{where}: expected_size exceeds supported bounds")
        if "require_transparency" in out and not isinstance(out["require_transparency"],bool):
            raise ValidationError(f"{where}: require_transparency must be boolean")


def reference_visual_coverage(edit: dict[str, Any]) -> dict[str, Any]:
    ref=edit.get("reference_evidence",{})
    required=bool(ref.get("required",False))
    expected=list(edit.get("reference_sufficiency",{}).get("required_roles",[]))
    verified_roles: set[str] = set()
    for item in ref.get("observations",[]):
        if item.get("visible_facts"):
            verified_roles.update(item.get("roles",[]))
    missing=[r for r in expected if r not in verified_roles] if required else []
    return {
        "required":required,
        "verified_roles":sorted(verified_roles),
        "missing_roles":missing,
        "status":"insufficient" if missing else "sufficient" if required else "not_required",
        "note":"Host-declared visual observations, not automated proof of the image contents.",
    }
