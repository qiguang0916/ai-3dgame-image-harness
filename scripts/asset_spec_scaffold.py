"""Offline-only v0.11 template generator: no model, permission or Master approval."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from asset_spec_v2 import CATEGORIES, ID, TRANSPARENT, style_fingerprint, validate_style_kit
from validate_project import ValidationError, cross_validate, load_document, validate_document


CATEGORY_SIZE = {
    "concept_prop": "1536x1024", "background": "1920x1080",
    "ui_icon": "512x512", "sprite": "512x512",
    "vfx_sheet": "2048x2048", "texture_candidate": "1024x1024",
    "steam_capsule": "920x430",
}
CATEGORY_PURPOSE = {
    "concept_prop": "concept_art", "background": "background",
    "ui_icon": "ui_art", "sprite": "sprite",
    "vfx_sheet": "sprite_sheet", "texture_candidate": "texture_reference",
    "steam_capsule": "marketing_art",
}


def _toml(value: Any) -> str:
    """Encode the small, strictly typed values used by this scaffold."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return "[" + ", ".join(_toml(x) for x in value) + "]"
    raise ValidationError("unsupported scaffold TOML field")


def starter_kit() -> dict[str, Any]:
    kit = {
        "id": "game_art_original_v1",
        "palette": ["#B8AAA0", "#46545E", "#FAFAF7"],
        "lighting": "Softbox lighting, low distraction, game-scale readable shapes",
        "materials": ["believable restrained surfaces", "clear material boundaries"],
        "edge_language": "No halos or unrelated outlines around the subject",
        "negative_constraints": [
            "no irrelevant props or invented hidden geometry",
            "no fake UI or unintended text overlays",
        ],
        "game_scale_read": "Readable at the final in-game display size",
    }
    kit["sha256"] = style_fingerprint(kit)
    return kit


def scaffold(category: str, asset_id: str, output_dir: Path) -> dict[str, Any]:
    """Create draft asset/edit TOML files without overwriting a previous folder."""
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValidationError("unsupported scaffold category")
    if not isinstance(asset_id, str) or not ID.fullmatch(asset_id):
        raise ValidationError("invalid scaffold asset ID")
    dest = Path(output_dir).expanduser().absolute()
    if dest.exists() or dest.is_symlink():
        raise ValidationError("scaffold destination must not exist")
    size = CATEGORY_SIZE[category]
    alpha = category in TRANSPARENT
    kit = starter_kit()
    asset_lines = [
        'document_type = "asset_manifest"', 'schema_version = 1',
        f'asset_id = {_toml(asset_id)}',
        f'asset_type = {_toml(category)}',
        'status = "bootstrap"',
        '', '[locks]', 'hard = ["declared visible object identity"]',
        'soft = ["lighting softness"]',
        '', '[qa]', 'max_repair_passes = 2', 'max_regeneration_passes = 1',
    ]
    edit_lines = [
        'document_type = "edit_request"', 'schema_version = 1',
        f'request_id = {_toml(asset_id + "_CREATE")}',
        f'asset_id = {_toml(asset_id)}', 'operation = "create"',
        f'target = {_toml("New original " + category + " game image candidate")}',
        f'change = {_toml("Create only the declared original " + category + " image; no unrelated elements.")}',
        '', '[preserve]', 'hard = []', 'soft = []',
        '', '[output]', f'purpose = {_toml(CATEGORY_PURPOSE[category])}',
        f'expected_size = {_toml(size)}',
        f'require_transparency = {_toml(alpha)}',
        '', '[asset_spec_v2]', 'contract_version = 2',
        f'category = {_toml(category)}',
        f'intended_use = {_toml(CATEGORIES[category])}',
        f'expected_size = {_toml(size)}',
        f'alpha_mode = {_toml("required" if alpha else "forbidden")}',
        'color_space = "srgb"', 'quality_tier = "draft"',
        'required_roles = []',
    ]
    if category == "texture_candidate":
        edit_lines.append('texture_channel = "basecolor"')
    edit_lines.extend(['', '[asset_spec_v2.style_kit]'])
    edit_lines.extend(f'{key} = {_toml(value)}' for key, value in kit.items())
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{dest.name}.v11-", dir=dest.parent))
    try:
        (temp / "asset.toml").write_text("\n".join(asset_lines) + "\n", encoding="utf-8")
        (temp / "create.toml").write_text("\n".join(edit_lines) + "\n", encoding="utf-8")
        documents = [load_document(temp / name) for name in ("asset.toml", "create.toml")]
        for doc in documents:
            validate_document(doc.data, doc.path)
        cross_validate(documents)
        if dest.exists() or dest.is_symlink():
            raise ValidationError("concurrent scaffold destination appeared")
        temp.rename(dest)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return {
        "status": "SCAFFOLDED_NOT_APPROVED", "category": category,
        "asset_id": asset_id, "output": str(dest),
        "style_kit_sha256": kit["sha256"], "commercial_release_certified": False,
        "rights_review": "REQUIRED_BEFORE_BATCH_PRODUCTION",
        "real_imagegen": "NOT_INVOKED",
    }


def readonly_style_hash(source: Path) -> dict[str, str]:
    """Compute a validated digest from a JSON style kit without modifying it."""
    source = Path(source)
    if not source.is_file() or source.stat().st_size > 16000:
        raise ValidationError("style JSON missing or too large")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "sha256" in data:
        raise ValidationError("style JSON must be unsigned style fields only")
    digest = style_fingerprint(data)
    validate_style_kit({**data, "sha256": digest}, str(source))
    return {"style_id": data["id"], "sha256": digest}
