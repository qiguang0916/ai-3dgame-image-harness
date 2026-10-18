#!/usr/bin/env python3
"""Create and finalize auditable ai-3dgame-image-harness Master candidates."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
import shutil
import struct
import sys
import uuid
import zlib
from pathlib import Path
from typing import Any

from artifact_integrity import receipt_digest
from execution_loop import _validate_auditable_qa
from topology_contract import validate_qa_completeness
from validate_project import ValidationError, load_document, validate_document


PASSING_QA_STATUSES = {"PASS", "PASS_WITH_NOTES"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: cannot read JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: JSON root must be an object")
    return value


def _write_json_new(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise ValidationError(f"refusing to overwrite existing file: {path}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_dimensions(path: Path) -> tuple[str, int, int]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"cannot read candidate image {path}: {exc}") from exc

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        image_format, width, height = _png_dimensions(path, data)
    elif data[:6] in {b"GIF87a", b"GIF89a"}:
        if len(data) < 14 or data[-1:] != b";" or b"," not in data[13:]:
            raise ValidationError(f"{path}: malformed GIF header")
        width, height = struct.unpack("<HH", data[6:10])
        image_format = "gif"
    elif data.startswith(b"\xff\xd8"):
        image_format, width, height = _jpeg_dimensions(path, data)
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        image_format, width, height = _webp_dimensions(path, data)
    else:
        raise ValidationError(
            f"{path}: candidate must be a recognized PNG, JPEG, GIF, or WebP image"
        )

    if width < 1 or height < 1:
        raise ValidationError(f"{path}: image dimensions must be positive")
    return image_format, width, height


def _png_dimensions(path: Path, data: bytes) -> tuple[str, int, int]:
    offset = 8
    width = height = 0
    idat = bytearray()
    seen_ihdr = False
    seen_iend = False
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(data):
            raise ValidationError(f"{path}: truncated PNG chunk")
        chunk_data = data[data_start:data_end]
        expected_crc = int.from_bytes(data[data_end:crc_end], "big")
        actual_crc = binascii.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise ValidationError(f"{path}: invalid PNG chunk checksum")
        if chunk_type == b"IHDR":
            if seen_ihdr or length != 13 or offset != 8:
                raise ValidationError(f"{path}: malformed PNG IHDR")
            width, height = struct.unpack(">II", chunk_data[:8])
            seen_ihdr = True
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            if length != 0:
                raise ValidationError(f"{path}: malformed PNG IEND")
            seen_iend = True
            offset = crc_end
            break
        offset = crc_end
    if not seen_ihdr or not idat or not seen_iend or offset != len(data):
        raise ValidationError(f"{path}: incomplete PNG image data")
    try:
        pixels = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise ValidationError(f"{path}: invalid PNG pixel data") from exc
    if not pixels:
        raise ValidationError(f"{path}: PNG contains no pixel rows")
    return "png", width, height


def _jpeg_dimensions(path: Path, data: bytes) -> tuple[str, int, int]:
    if not data.endswith(b"\xff\xd9"):
        raise ValidationError(f"{path}: incomplete JPEG image data")
    offset = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:
            break
        if offset + 2 > len(data):
            break
        segment_length = int.from_bytes(data[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(data):
            break
        if marker in sof_markers and segment_length >= 7:
            height = int.from_bytes(data[offset + 3 : offset + 5], "big")
            width = int.from_bytes(data[offset + 5 : offset + 7], "big")
            return "jpeg", width, height
        offset += segment_length
    raise ValidationError(f"{path}: JPEG has no readable dimensions")


def _webp_dimensions(path: Path, data: bytes) -> tuple[str, int, int]:
    if len(data) < 30:
        raise ValidationError(f"{path}: malformed WebP header")
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise ValidationError(f"{path}: incomplete WebP image data")
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return "webp", width, height
    if chunk == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return "webp", width, height
    if chunk == b"VP8L" and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return "webp", width, height
    raise ValidationError(f"{path}: WebP has no readable dimensions")


def create_candidate(
    *,
    image_path: Path,
    source_run_path: Path,
    reference_id: str,
    revision: int,
    supersedes: str | None,
    output_path: Path,
) -> dict[str, Any]:
    if not reference_id.strip():
        raise ValidationError("reference_id must be non-empty")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValidationError("revision must be a positive integer")
    if revision == 1:
        if supersedes is not None:
            raise ValidationError("first Master cannot supersede another")
    elif not isinstance(supersedes, str) or not supersedes.strip():
        raise ValidationError("successor Master requires supersedes")
    if reference_id == supersedes:
        raise ValidationError("a Master revision cannot supersede itself")

    image_path = image_path.resolve()
    image_format, width, height = _image_dimensions(image_path)
    if image_format != "png":
        raise ValidationError("Master candidates must be PNG images")
    run = _read_json(source_run_path)
    for key in ("run_id", "asset_id", "request_id", "current_result_path"):
        if not isinstance(run.get(key), str) or not run[key].strip():
            raise ValidationError(f"{source_run_path}: missing run field '{key}'")
    run_result = Path(run["current_result_path"])
    if not run_result.is_absolute():
        if run.get("auditable") and run.get("workspace_root"):
            run_result = Path(run["workspace_root"]) / run_result
        else:
            run_result = source_run_path.parent / run_result
    if run_result.resolve() != image_path:
        raise ValidationError("candidate image does not match source run result path")
    if run.get("auditable") is not True:
        raise ValidationError("Master candidate source run must be auditable")
    if revision == 1 and not (run.get("bootstrap_asset") is True and run.get("execution_mode") == "generate"):
        raise ValidationError("first Master must come from an auditable bootstrap create run")
    receipt = run.get("current_receipt")
    if not isinstance(receipt, dict):
        raise ValidationError("auditable candidate source run has no receipt")
    if receipt_digest(receipt) != receipt.get("receipt_id"):
        raise ValidationError("candidate source receipt integrity check failed")
    result_binding = receipt.get("result", {})
    if result_binding.get("sha256") != _sha256(image_path):
        raise ValidationError(
            "candidate image does not match source execution receipt"
        )
    if run.get("state") not in {"QA_PENDING", "ACCEPTED"}:
        raise ValidationError(
            "candidate source run must be ready for QA or already accepted"
        )

    record = {
        "document_type": "master_candidate",
        "schema_version": 1,
        "state": "candidate",
        "asset_id": run["asset_id"],
        "request_id": run["request_id"],
        "reference_id": reference_id,
        "candidate_path": str(image_path),
        "content_sha256": _sha256(image_path),
        "image": {"format": image_format, "width": width, "height": height},
        "lineage": {
            "revision": revision,
            "supersedes": supersedes,
            "source_run_id": run["run_id"],
            "source_run_path": str(source_run_path.resolve()),
        },
    }
    _write_json_new(output_path, record)
    return record


def _validate_candidate_record(record: dict[str, Any], path: Path) -> None:
    if record.get("document_type") != "master_candidate":
        raise ValidationError(f"{path}: expected master_candidate record")
    if record.get("schema_version") != 1 or record.get("state") != "candidate":
        raise ValidationError(f"{path}: only a schema v1 candidate can be finalized")
    for key in (
        "asset_id",
        "request_id",
        "reference_id",
        "candidate_path",
        "content_sha256",
    ):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValidationError(f"{path}: missing candidate field '{key}'")
    lineage = record.get("lineage")
    if not isinstance(lineage, dict):
        raise ValidationError(f"{path}: missing candidate lineage")
    for key in ("revision", "supersedes", "source_run_id", "source_run_path"):
        if key not in lineage:
            raise ValidationError(f"{path}: missing lineage field '{key}'")
    if lineage["revision"] == 1 and lineage["supersedes"] is not None:
        raise ValidationError(f"{path}: first Master has invalid predecessor")
    if lineage["revision"] > 1 and not lineage["supersedes"]:
        raise ValidationError(f"{path}: subsequent Master requires predecessor")


def finalize_candidate(
    *,
    candidate_record_path: Path,
    qa_path: Path,
    output_path: Path,
    approved_image_path: Path | None = None,
) -> dict[str, Any]:
    record = _read_json(candidate_record_path)
    _validate_candidate_record(record, candidate_record_path)
    image_path = Path(record["candidate_path"]).resolve()
    image_format, _, _ = _image_dimensions(image_path)
    if image_format != "png" or record.get("image", {}).get("format") != "png":
        raise ValidationError("Master candidates must remain PNG images")
    actual_digest = _sha256(image_path)
    if actual_digest != record["content_sha256"]:
        raise ValidationError("candidate image changed after candidate registration")

    qa_doc = load_document(qa_path)
    validate_document(qa_doc.data, qa_doc.path)
    qa = qa_doc.data
    source_run_path = Path(record["lineage"]["source_run_path"]).resolve()
    source_run = _read_json(source_run_path)
    if source_run.get("auditable") is not True:
        raise ValidationError("Master candidate source run must be auditable")
    if source_run.get("run_id") != record["lineage"]["source_run_id"]:
        raise ValidationError("candidate lineage run_id does not match source run")
    if source_run.get("asset_id") != record["asset_id"]:
        raise ValidationError("candidate asset_id does not match source run")
    if source_run.get("request_id") != record["request_id"]:
        raise ValidationError("candidate request_id does not match source run")
    receipt = source_run.get("current_receipt")
    if not isinstance(receipt, dict):
        raise ValidationError("candidate source run has no current receipt")
    if receipt.get("result_sha256") != actual_digest:
        raise ValidationError(
            "candidate image does not match source run current receipt result"
        )
    current_result = Path(str(source_run.get("current_result_path", "")))
    if not current_result.is_absolute():
        current_result = Path(source_run["workspace_root"]) / current_result
    if current_result.resolve() != image_path:
        raise ValidationError(
            "candidate image does not match source run current result path"
        )
    required_gates = source_run.get("required_hard_gates")
    if not isinstance(required_gates, list) or not required_gates:
        raise ValidationError("source run has no required hard-gate contract")
    validate_qa_completeness(required_gates, qa)
    _validate_auditable_qa(source_run, qa)
    binding = qa.get("master_candidate")
    if not isinstance(binding, dict):
        raise ValidationError("Master QA must contain a master_candidate binding")
    expected_bindings = {
        "reference_id": record["reference_id"],
        "content_sha256": record["content_sha256"],
        "source_run_id": record["lineage"]["source_run_id"],
    }
    for key, expected in expected_bindings.items():
        if binding.get(key) != expected:
            raise ValidationError(f"Master QA {key} does not match candidate")
    if qa["asset_id"] != record["asset_id"]:
        raise ValidationError("Master QA asset_id does not match candidate")
    if qa["request_id"] != record["request_id"]:
        raise ValidationError("Master QA request_id does not match candidate source run")

    if output_path.exists():
        raise ValidationError(f"refusing to overwrite existing file: {output_path}")

    if qa["status"] in PASSING_QA_STATUSES:
        if source_run.get("state") != "ACCEPTED":
            raise ValidationError(
                "Master promotion requires an ACCEPTED source run"
            )
        last_qa = source_run.get("last_qa")
        if (
            not isinstance(last_qa, dict)
            or last_qa.get("status") not in PASSING_QA_STATUSES
        ):
            raise ValidationError("source run has no accepted QA verdict")
        for key in ("receipt_id", "result_sha256"):
            if last_qa.get(key) != receipt.get(key):
                raise ValidationError(
                    "source run accepted QA does not match current receipt"
                )
        state = "approved"
        if binding.get("actual_pixels_inspected") is not True:
            raise ValidationError(
                "approved Master QA must confirm actual pixel inspection"
            )
        if approved_image_path is None:
            raise ValidationError("approved QA requires --approved-image")
        approved_image_path = approved_image_path.resolve()
        if approved_image_path == output_path.resolve():
            raise ValidationError(
                "approved image path must differ from the decision record path"
            )
        if approved_image_path == image_path:
            raise ValidationError("promotion requires a new approved image path")
        if approved_image_path.exists():
            raise ValidationError(
                f"refusing to overwrite existing file: {approved_image_path}"
            )
        approved_image_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = approved_image_path.with_name(
            f".{approved_image_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with temporary_path.open("xb") as destination:
                with image_path.open("rb") as source:
                    shutil.copyfileobj(source, destination)
            if _sha256(image_path) != actual_digest:
                raise ValidationError("candidate image changed during promotion")
            if _sha256(temporary_path) != actual_digest:
                raise ValidationError("approved image copy failed digest verification")
            try:
                os.link(temporary_path, approved_image_path)
            except FileExistsError as exc:
                raise ValidationError(
                    f"refusing to overwrite existing file: {approved_image_path}"
                ) from exc
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    else:
        if approved_image_path is not None:
            raise ValidationError("non-passing QA cannot create an approved image")
        state = "blocked" if qa["status"] == "BLOCKED" else "rejected"

    decision = {
        "document_type": "master_lifecycle_decision",
        "schema_version": 1,
        "state": state,
        "asset_id": record["asset_id"],
        "request_id": record["request_id"],
        "reference_id": record["reference_id"],
        "candidate_path": str(image_path),
        "qa_status": qa["status"],
        "lineage": {
            "revision": record["lineage"]["revision"],
            "supersedes": record["lineage"]["supersedes"],
            "content_sha256": actual_digest,
            "source_run_id": record["lineage"]["source_run_id"],
            "source_run_path": record["lineage"]["source_run_path"],
            "source_qa_report_id": qa["report_id"],
            "source_qa_path": str(qa_path.resolve()),
        },
    }
    if state == "approved":
        decision["approved_path"] = str(approved_image_path)
    _write_json_new(output_path, decision)
    return decision


def register_first_master(
    *,
    bootstrap_asset_path: Path,
    decision_path: Path,
    output_path: Path,
    roles: list[str],
) -> dict[str, Any]:
    """Create a new active TOML manifest after first-Master QA; never mutate input."""
    import re
    from validate_project import validate_asset_manifest
    if not roles or any(not isinstance(x, str) or not x.strip() for x in roles) or len(set(roles)) != len(roles):
        raise ValidationError("first Master registration requires unique reference roles")
    asset_doc = load_document(bootstrap_asset_path)
    validate_document(asset_doc.data, asset_doc.path)
    if asset_doc.data.get("status") != "bootstrap":
        raise ValidationError("only a bootstrap manifest may register the first Master")
    decision = _read_json(decision_path)
    if decision.get("state") != "approved" or decision.get("asset_id") != asset_doc.data["asset_id"]:
        raise ValidationError("approved decision asset_id does not match bootstrap manifest")
    if decision.get("lineage", {}).get("revision") != 1 or decision.get("lineage", {}).get("supersedes") is not None:
        raise ValidationError("first Master decision must be revision 1 without predecessor")
    metadata = decision.get("lineage", {})
    source_run_path = Path(str(metadata.get("source_run_path", "")))
    qa_path = Path(str(metadata.get("source_qa_path", "")))
    if not source_run_path.is_file() or not qa_path.is_file():
        raise ValidationError("first Master decision has no verifiable source run / QA files")
    source_run = _read_json(source_run_path)
    if not (
        source_run.get("auditable") is True
        and source_run.get("bootstrap_asset") is True
        and source_run.get("execution_mode") == "generate"
        and source_run.get("state") == "ACCEPTED"
        and source_run.get("asset_id") == asset_doc.data["asset_id"]
        and source_run.get("run_id") == metadata.get("source_run_id")
    ):
        raise ValidationError("first Master decision source run is not an accepted bootstrap creation")
    qa_doc = load_document(qa_path)
    validate_document(qa_doc.data, qa_doc.path)
    qa = qa_doc.data
    from validate_project import SHA256_PATTERN
    expected_qa = source_run.get("last_qa")
    if (
        not isinstance(expected_qa, dict)
        or qa.get("report_id") != metadata.get("source_qa_report_id")
        or expected_qa.get("report_id") != qa.get("report_id")
        or qa.get("status") not in PASSING_QA_STATUSES
        or expected_qa.get("status") not in PASSING_QA_STATUSES
    ):
        raise ValidationError("first Master was not approved by the persisted source QA")
    validate_qa_completeness(source_run.get("required_hard_gates", []), qa)
    _validate_auditable_qa(source_run, qa)
    master_binding = qa.get("master_candidate")
    if not isinstance(master_binding, dict) or not (
        master_binding.get("reference_id") == decision.get("reference_id")
        and master_binding.get("content_sha256") == metadata.get("content_sha256")
        and master_binding.get("source_run_id") == source_run.get("run_id")
        and master_binding.get("actual_pixels_inspected") is True
    ):
        raise ValidationError("first Master candidate pixel QA attestation is missing or does not match")
    candidate = Path(str(decision.get("candidate_path", ""))).resolve()
    receipt = source_run.get("current_receipt",{})
    current_result = Path(source_run.get("current_result_path", ""))
    if not current_result.is_absolute():
        current_result = Path(source_run["workspace_root"]) / current_result
    if (
        candidate != current_result.resolve()
        or not candidate.is_file()
        or _sha256(candidate) != metadata.get("content_sha256")
        or receipt.get("result_sha256") != metadata.get("content_sha256")
    ):
        raise ValidationError("candidate/source-run/receipt bytes do not match first Master decision")

    image = Path(decision["approved_path"]).resolve()
    if not image.is_file() or _sha256(image) != metadata["content_sha256"]:
        raise ValidationError("approved first Master digest mismatch or missing file")
    if output_path.resolve() == bootstrap_asset_path.resolve() or output_path.exists():
        raise ValidationError("registration must create a new manifest path")
    if output_path.parent.resolve() != bootstrap_asset_path.parent.resolve():
        raise ValidationError("new manifest must share bootstrap manifest directory for portable paths")
    text = bootstrap_asset_path.read_text(encoding="utf8")
    if not re.search(r'(?m)^status\s*=\s*"bootstrap"\s*$', text):
        raise ValidationError("bootstrap manifest must declare status in root header")
    text = re.sub(r'(?m)^status\s*=\s*"bootstrap"\s*$', 'status = "active"', text, count=1)
    text = re.sub(r'(?m)^references\s*=\s*\[\s*\]\s*$', '', text, count=1)
    header, sep, tail = text.partition("\n[")
    if not sep:
        raise ValidationError("bootstrap manifest must contain locks table")
    if "primary_master" in header:
        raise ValidationError("bootstrap cannot contain primary_master")
    new_text = header.rstrip() + "\nprimary_master = " + json.dumps(decision["reference_id"]) + "\n" + sep + tail
    relpath = os.path.relpath(image, output_path.parent.resolve())
    if relpath.startswith("../"):
        raise ValidationError("approved Master must stay inside the asset workspace")
    metadata = decision["lineage"]
    new_text += ("\n[[references]]\n"
                 "id = " + json.dumps(decision["reference_id"]) + "\n"
                 "path = " + json.dumps(relpath) + "\n"
                 'state = "approved"\n'
                 "roles = " + json.dumps(roles) + "\n"
                 "revision = 1\n"
                 "content_sha256 = " + json.dumps(metadata["content_sha256"]) + "\n"
                 "source_run_id = " + json.dumps(metadata["source_run_id"]) + "\n"
                 "source_qa_report_id = " + json.dumps(metadata["source_qa_report_id"]) + "\n")
    import tomllib
    parsed = tomllib.loads(new_text)
    validate_asset_manifest(parsed, output_path)
    try:
        with output_path.open("x", encoding="utf8") as handle:
            handle.write(new_text)
    except FileExistsError as exc:
        raise ValidationError("refusing to overwrite existing active manifest") from exc
    return {"status": "active", "manifest_path": str(output_path),
            "primary_master": decision["reference_id"], "approved_image": str(image)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    candidate = subparsers.add_parser("candidate")
    candidate.add_argument("--image", required=True, type=Path)
    candidate.add_argument("--source-run", required=True, type=Path)
    candidate.add_argument("--reference-id", required=True)
    candidate.add_argument("--revision", required=True, type=int)
    candidate.add_argument("--supersedes", help="Required for revision > 1; omit for first Master")
    candidate.add_argument("--out", required=True, type=Path)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--candidate", required=True, type=Path)
    finalize.add_argument("--qa", required=True, type=Path)
    finalize.add_argument("--out", required=True, type=Path)
    finalize.add_argument("--approved-image", type=Path)

    register = subparsers.add_parser("register-first")
    register.add_argument("--bootstrap-asset", type=Path, required=True)
    register.add_argument("--decision", type=Path, required=True)
    register.add_argument("--out", type=Path, required=True)
    register.add_argument("--roles", nargs="+", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "candidate":
            result = create_candidate(
                image_path=args.image,
                source_run_path=args.source_run,
                reference_id=args.reference_id,
                revision=args.revision,
                supersedes=args.supersedes,
                output_path=args.out,
            )
        elif args.command == "register-first":
            result = register_first_master(
                bootstrap_asset_path=args.bootstrap_asset,
                decision_path=args.decision,
                output_path=args.out,
                roles=args.roles,
            )
        else:
            result = finalize_candidate(
                candidate_record_path=args.candidate,
                qa_path=args.qa,
                output_path=args.out,
                approved_image_path=args.approved_image,
            )
    except (OSError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
