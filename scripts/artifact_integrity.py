#!/usr/bin/env python3
"""Deterministic path and digest helpers for auditable execution artifacts."""

from __future__ import annotations

import hashlib
import json
import struct
from copy import deepcopy
from pathlib import Path
from typing import Any

from validate_project import ValidationError


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_in_workspace(
    workspace_root: Path | str,
    raw_path: Path | str,
) -> Path:
    """Resolve a path without consulting cwd and reject workspace escapes."""
    root = Path(workspace_root).expanduser().resolve()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValidationError(
            f"path escapes workspace_root: {raw_path}"
        ) from exc
    return resolved


def workspace_relative(
    workspace_root: Path | str,
    path: Path | str,
) -> str:
    root = Path(workspace_root).expanduser().resolve()
    return str(resolve_in_workspace(root, path).relative_to(root))


def png_metadata(path: Path) -> dict[str, int | str]:
    with Path(path).open("rb") as handle:
        header = handle.read(33)
    if len(header) < 33 or not header.startswith(PNG_SIGNATURE):
        raise ValidationError(f"invalid PNG metadata: {path}")
    length = struct.unpack(">I", header[8:12])[0]
    if header[12:16] != b"IHDR" or length != 13:
        raise ValidationError(f"invalid PNG IHDR: {path}")
    width, height, bit_depth, color_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", header[16:29])
    )
    return {
        "format": "png",
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "compression_method": compression,
        "filter_method": filtering,
        "interlace_method": interlace,
        "byte_size": Path(path).stat().st_size,
    }


def file_binding(
    workspace_root: Path | str,
    path: Path | str,
    **fields: Any,
) -> dict[str, Any]:
    resolved = resolve_in_workspace(workspace_root, path)
    return {
        **fields,
        "path": workspace_relative(workspace_root, resolved),
        "sha256": sha256_file(resolved),
        "png": png_metadata(resolved),
    }


def packet_digest(packet: dict[str, Any]) -> str:
    payload = deepcopy(packet)
    payload.pop("packet_id", None)
    return sha256_bytes(canonical_json_bytes(payload))


def receipt_digest(receipt: dict[str, Any]) -> str:
    payload = deepcopy(receipt)
    payload.pop("receipt_id", None)
    return sha256_bytes(canonical_json_bytes(payload))
