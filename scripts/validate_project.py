#!/usr/bin/env python3
"""Validate game-image TOML manifests with Python standard library only."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ALLOWED_DOCUMENT_TYPES = {"asset_manifest", "edit_request", "qa_report"}
ALLOWED_REFERENCE_STATES = {
    "approved",
    "candidate",
    "draft",
    "rejected",
    "superseded",
}
ALLOWED_OPERATIONS = {
    "create",
    "local_edit",
    "structural_edit",
    "variant",
    "repair",
    "regenerate",
}
OPERATIONS_REQUIRING_BASE_EDIT_TARGET = {
    "local_edit",
    "structural_edit",
    "variant",
    "regenerate",
}
ALLOWED_QA_STATUSES = {
    "PASS",
    "PASS_WITH_NOTES",
    "REPAIR_MINOR",
    "REGENERATE_MAJOR",
    "BLOCKED",
}
ALLOWED_GATE_SEVERITIES = {"hard", "soft"}
ALLOWED_GATE_STATUSES = {
    "PASS",
    "FAIL",
    "NOTE",
    "NOT_CHECKED",
    "NOT_VERIFIABLE",
}
MASTER_LINEAGE_FIELDS = {
    "revision",
    "supersedes",
    "content_sha256",
    "source_run_id",
    "source_qa_report_id",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class LoadedDocument:
    path: Path
    data: dict[str, Any]


class ValidationError(ValueError):
    pass


def require(data: dict[str, Any], key: str, where: str) -> Any:
    value = data.get(key)
    if value is None or value == "" or value == []:
        raise ValidationError(f"{where}: missing required field '{key}'")
    return value


def ensure_string_list(value: Any, where: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValidationError(f"{where}: expected a list of non-empty strings")
    if not allow_empty and not value:
        raise ValidationError(f"{where}: list must not be empty")
    return value


def validate_asset_manifest(data: dict[str, Any], path: Path) -> None:
    where = str(path)
    require(data, "asset_id", where)
    primary_master = require(data, "primary_master", where)

    locks = require(data, "locks", where)
    if not isinstance(locks, dict):
        raise ValidationError(f"{where}: locks must be a table")
    ensure_string_list(locks.get("hard"), f"{where}: locks.hard")
    ensure_string_list(
        locks.get("soft", []),
        f"{where}: locks.soft",
        allow_empty=True,
    )

    references = require(data, "references", where)
    if not isinstance(references, list):
        raise ValidationError(f"{where}: references must be an array of tables")

    ids: set[str] = set()
    reference_by_id: dict[str, dict[str, Any]] = {}
    approved = 0
    for index, ref in enumerate(references):
        rwhere = f"{where}: references[{index}]"
        if not isinstance(ref, dict):
            raise ValidationError(f"{rwhere}: expected table")
        ref_id = require(ref, "id", rwhere)
        if ref_id in ids:
            raise ValidationError(f"{rwhere}: duplicate reference id '{ref_id}'")
        ids.add(ref_id)
        reference_by_id[ref_id] = ref
        require(ref, "path", rwhere)
        state = require(ref, "state", rwhere)
        if state not in ALLOWED_REFERENCE_STATES:
            raise ValidationError(f"{rwhere}: invalid state '{state}'")
        if state == "approved":
            approved += 1
        roles = ensure_string_list(ref.get("roles"), f"{rwhere}: roles")
        if len(set(roles)) != len(roles):
            raise ValidationError(f"{rwhere}: duplicate reference roles")

        lineage_fields = MASTER_LINEAGE_FIELDS.intersection(ref)
        if lineage_fields and lineage_fields != MASTER_LINEAGE_FIELDS:
            missing = ", ".join(sorted(MASTER_LINEAGE_FIELDS - lineage_fields))
            raise ValidationError(
                f"{rwhere}: enhanced master lineage is missing: {missing}"
            )
        if lineage_fields:
            revision = ref["revision"]
            if (
                isinstance(revision, bool)
                or not isinstance(revision, int)
                or revision < 1
            ):
                raise ValidationError(
                    f"{rwhere}: revision must be a positive integer"
                )
            for key in ("supersedes", "source_run_id", "source_qa_report_id"):
                require(ref, key, rwhere)
            if ref["supersedes"] == ref_id:
                raise ValidationError(f"{rwhere}: supersedes cannot reference itself")
            if not isinstance(ref["content_sha256"], str) or not SHA256_PATTERN.fullmatch(
                ref["content_sha256"]
            ):
                raise ValidationError(
                    f"{rwhere}: content_sha256 must be 64 lowercase hex characters"
                )

    if approved == 0:
        raise ValidationError(f"{where}: at least one approved reference is required")
    if primary_master not in ids:
        raise ValidationError(
            f"{where}: primary_master '{primary_master}' does not match a reference id"
        )
    if reference_by_id[primary_master].get("state") != "approved":
        raise ValidationError(f"{where}: primary_master must be approved")

    successor_by_predecessor: dict[str, str] = {}
    lineage_edges: dict[str, str] = {}
    for ref_id, ref in reference_by_id.items():
        if not MASTER_LINEAGE_FIELDS.intersection(ref):
            continue
        supersedes = ref["supersedes"]
        if supersedes in successor_by_predecessor:
            raise ValidationError(
                f"{where}: reference '{supersedes}' has multiple successors: "
                f"'{successor_by_predecessor[supersedes]}' and '{ref_id}'"
            )
        successor_by_predecessor[supersedes] = ref_id
        lineage_edges[ref_id] = supersedes
        predecessor = reference_by_id.get(supersedes)
        if predecessor is None:
            raise ValidationError(
                f"{where}: reference '{ref_id}' supersedes unknown reference "
                f"'{supersedes}'"
            )
        if ref["state"] == "approved" and predecessor["state"] != "superseded":
            raise ValidationError(
                f"{where}: approved reference '{ref_id}' requires its predecessor "
                f"'{supersedes}' to be superseded"
            )
        predecessor_revision = predecessor.get("revision")
        if (
            isinstance(predecessor_revision, int)
            and not isinstance(predecessor_revision, bool)
            and predecessor_revision >= ref["revision"]
        ):
            raise ValidationError(
                f"{where}: reference '{ref_id}' revision must be newer than "
                f"'{supersedes}'"
            )

    for start in lineage_edges:
        seen: set[str] = set()
        current = start
        while current in lineage_edges:
            if current in seen:
                raise ValidationError(
                    f"{where}: reference lineage contains a cycle at '{current}'"
                )
            seen.add(current)
            current = lineage_edges[current]

    qa = data.get("qa", {})
    if qa:
        if not isinstance(qa, dict):
            raise ValidationError(f"{where}: qa must be a table")

        repair_passes = qa.get("max_repair_passes", 2)
        if not isinstance(repair_passes, int) or not 0 <= repair_passes <= 5:
            raise ValidationError(
                f"{where}: qa.max_repair_passes must be an integer 0..5"
            )

        regeneration_passes = qa.get("max_regeneration_passes", 1)
        if (
            not isinstance(regeneration_passes, int)
            or not 0 <= regeneration_passes <= 3
        ):
            raise ValidationError(
                f"{where}: qa.max_regeneration_passes must be an integer 0..3"
            )

    from topology_contract import validate_topology_schema

    try:
        validate_topology_schema(data, where)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def validate_edit_request(data: dict[str, Any], path: Path) -> None:
    where = str(path)
    require(data, "request_id", where)
    require(data, "asset_id", where)
    operation = require(data, "operation", where)
    if operation not in ALLOWED_OPERATIONS:
        raise ValidationError(f"{where}: invalid operation '{operation}'")
    require(data, "target", where)
    require(data, "change", where)

    execution = data.get("execution", {})
    if execution and not isinstance(execution, dict):
        raise ValidationError(f"{where}: execution must be a table")
    if operation in OPERATIONS_REQUIRING_BASE_EDIT_TARGET:
        require(
            execution,
            "edit_target_reference_id",
            f"{where}: execution",
        )

    preserve = require(data, "preserve", where)
    if not isinstance(preserve, dict):
        raise ValidationError(f"{where}: preserve must be a table")
    hard = ensure_string_list(
        preserve.get("hard", []),
        f"{where}: preserve.hard",
        allow_empty=operation in {"create", "regenerate"},
    )
    ensure_string_list(
        preserve.get("soft", []),
        f"{where}: preserve.soft",
        allow_empty=True,
    )
    if operation == "local_edit" and not hard:
        raise ValidationError(
            f"{where}: local_edit requires at least one hard preserve rule"
        )

    sufficiency = data.get("reference_sufficiency", {})
    if sufficiency:
        if not isinstance(sufficiency, dict):
            raise ValidationError(
                f"{where}: reference_sufficiency must be a table"
            )
        ensure_string_list(
            sufficiency.get("required_roles", []),
            f"{where}: reference_sufficiency.required_roles",
            allow_empty=True,
        )
        provisional_fields = ensure_string_list(
            sufficiency.get("provisional_fields", []),
            f"{where}: reference_sufficiency.provisional_fields",
            allow_empty=True,
        )
        ensure_string_list(
            sufficiency.get("prohibited_assumptions", []),
            f"{where}: reference_sufficiency.prohibited_assumptions",
            allow_empty=True,
        )
        allow_provisional = sufficiency.get("allow_provisional", False)
        if not isinstance(allow_provisional, bool):
            raise ValidationError(
                f"{where}: reference_sufficiency.allow_provisional must be boolean"
            )
        if allow_provisional and not provisional_fields:
            raise ValidationError(
                f"{where}: provisional mode requires provisional_fields"
            )

    qa_contract = data.get("qa_contract", {})
    if qa_contract:
        if not isinstance(qa_contract, dict):
            raise ValidationError(f"{where}: qa_contract must be a table")
        required_gates = ensure_string_list(
            qa_contract.get("required_hard_gates", []),
            f"{where}: qa_contract.required_hard_gates",
            allow_empty=True,
        )
        if len(set(required_gates)) != len(required_gates):
            raise ValidationError(
                f"{where}: qa_contract.required_hard_gates contains duplicates"
            )

    bindings = data.get("reference_bindings", [])
    if operation != "create" and not bindings:
        raise ValidationError(
            f"{where}: non-create operations require reference_bindings"
        )
    if not isinstance(bindings, list):
        raise ValidationError(
            f"{where}: reference_bindings must be an array of tables"
        )

    seen: set[str] = set()
    for index, binding in enumerate(bindings):
        bwhere = f"{where}: reference_bindings[{index}]"
        if not isinstance(binding, dict):
            raise ValidationError(f"{bwhere}: expected table")
        ref_id = require(binding, "reference_id", bwhere)
        if ref_id in seen:
            raise ValidationError(
                f"{bwhere}: duplicate reference binding '{ref_id}'"
            )
        seen.add(ref_id)
        roles = ensure_string_list(binding.get("roles"), f"{bwhere}: roles")
        if len(set(roles)) != len(roles):
            raise ValidationError(f"{bwhere}: duplicate binding roles")


def validate_qa_report(data: dict[str, Any], path: Path) -> None:
    where = str(path)
    require(data, "report_id", where)
    require(data, "asset_id", where)
    require(data, "request_id", where)
    status = require(data, "status", where)
    if status not in ALLOWED_QA_STATUSES:
        raise ValidationError(f"{where}: invalid QA status '{status}'")

    gates = require(data, "gates", where)
    if not isinstance(gates, list):
        raise ValidationError(f"{where}: gates must be an array of tables")

    hard_gate_count = 0
    failed_hard = False
    non_pass_gate_count = 0
    seen_names: set[str] = set()

    for index, gate in enumerate(gates):
        gwhere = f"{where}: gates[{index}]"
        if not isinstance(gate, dict):
            raise ValidationError(f"{gwhere}: expected table")
        name = require(gate, "name", gwhere)
        if name in seen_names:
            raise ValidationError(f"{gwhere}: duplicate gate name '{name}'")
        seen_names.add(name)

        severity = require(gate, "severity", gwhere)
        gate_status = require(gate, "status", gwhere)
        if severity not in ALLOWED_GATE_SEVERITIES:
            raise ValidationError(f"{gwhere}: invalid severity '{severity}'")
        if gate_status not in ALLOWED_GATE_STATUSES:
            raise ValidationError(f"{gwhere}: invalid status '{gate_status}'")

        if gate_status not in {"PASS", "NOTE"}:
            non_pass_gate_count += 1

        if severity == "hard":
            hard_gate_count += 1
            if gate_status != "PASS":
                failed_hard = True

    if hard_gate_count == 0:
        raise ValidationError(f"{where}: at least one hard gate is required")

    if status in {"PASS", "PASS_WITH_NOTES"} and failed_hard:
        raise ValidationError(
            f"{where}: PASS/PASS_WITH_NOTES cannot contain a non-PASS hard gate"
        )

    if status in {"REPAIR_MINOR", "REGENERATE_MAJOR"} and non_pass_gate_count == 0:
        raise ValidationError(
            f"{where}: {status} requires at least one failed/unverifiable gate"
        )

    directives = ensure_string_list(
        data.get("repair_directives", []),
        f"{where}: repair_directives",
        allow_empty=True,
    )
    if status == "REPAIR_MINOR" and not directives:
        raise ValidationError(
            f"{where}: REPAIR_MINOR requires at least one repair directive"
        )

    master_candidate = data.get("master_candidate")
    if master_candidate is not None:
        mwhere = f"{where}: master_candidate"
        if not isinstance(master_candidate, dict):
            raise ValidationError(f"{mwhere}: must be a table")
        for key in ("reference_id", "content_sha256", "source_run_id"):
            require(master_candidate, key, mwhere)
        digest = master_candidate["content_sha256"]
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ValidationError(
                f"{mwhere}: content_sha256 must be 64 lowercase hex characters"
            )
        inspected = master_candidate.get("actual_pixels_inspected")
        if not isinstance(inspected, bool):
            raise ValidationError(
                f"{mwhere}: actual_pixels_inspected must be boolean"
            )


def validate_document(data: dict[str, Any], path: Path) -> None:
    where = str(path)
    document_type = require(data, "document_type", where)
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValidationError(
            f"{where}: unknown document_type '{document_type}'"
        )
    if data.get("schema_version") != 1:
        raise ValidationError(f"{where}: schema_version must be 1")

    if document_type == "asset_manifest":
        validate_asset_manifest(data, path)
    elif document_type == "edit_request":
        validate_edit_request(data, path)
    elif document_type == "qa_report":
        validate_qa_report(data, path)


def load_document(path: Path) -> LoadedDocument:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: TOML root must be a table")
    return LoadedDocument(path=path, data=data)


def cross_validate(documents: list[LoadedDocument]) -> None:
    assets: dict[str, dict[str, Any]] = {}
    edits: dict[str, dict[str, Any]] = {}
    qa_reports: list[LoadedDocument] = []

    for doc in documents:
        dtype = doc.data["document_type"]
        if dtype == "asset_manifest":
            asset_id = doc.data["asset_id"]
            if asset_id in assets:
                raise ValidationError(
                    f"duplicate asset manifest for '{asset_id}'"
                )
            assets[asset_id] = doc.data
        elif dtype == "edit_request":
            request_id = doc.data["request_id"]
            if request_id in edits:
                raise ValidationError(
                    f"duplicate edit request '{request_id}'"
                )
            edits[request_id] = doc.data
        elif dtype == "qa_report":
            qa_reports.append(doc)

    for doc in documents:
        data = doc.data
        if data["document_type"] != "edit_request":
            continue

        asset = assets.get(data["asset_id"])
        if asset is None:
            continue

        reference_by_id = {
            ref["id"]: ref for ref in asset["references"]
        }
        bound_ids: set[str] = set()

        for binding in data.get("reference_bindings", []):
            ref_id = binding["reference_id"]
            bound_ids.add(ref_id)
            ref = reference_by_id.get(ref_id)
            if ref is None:
                raise ValidationError(
                    f"{doc.path}: reference_binding '{ref_id}' is not in asset "
                    f"'{data['asset_id']}'"
                )
            if ref.get("state") != "approved":
                raise ValidationError(
                    f"{doc.path}: reference_binding '{ref_id}' is not approved"
                )

            declared_roles = set(ref.get("roles", []))
            requested_roles = set(binding.get("roles", []))
            undeclared = requested_roles - declared_roles
            if undeclared:
                joined = ", ".join(sorted(undeclared))
                raise ValidationError(
                    f"{doc.path}: reference_binding '{ref_id}' requests "
                    f"undeclared role(s): {joined}"
                )

        operation = data["operation"]
        if operation in OPERATIONS_REQUIRING_BASE_EDIT_TARGET:
            target_id = data["execution"]["edit_target_reference_id"]
            target_ref = reference_by_id.get(target_id)
            if target_ref is None:
                raise ValidationError(
                    f"{doc.path}: edit target '{target_id}' is not in asset "
                    f"'{data['asset_id']}'"
                )
            if target_ref.get("state") != "approved":
                raise ValidationError(
                    f"{doc.path}: edit target '{target_id}' is not approved"
                )
            if target_id not in bound_ids:
                raise ValidationError(
                    f"{doc.path}: edit target '{target_id}' must also appear "
                    "in reference_bindings"
                )

    from topology_contract import (
        expected_hard_gates,
        validate_qa_completeness,
    )

    for qa_doc in qa_reports:
        qa = qa_doc.data
        request = edits.get(qa["request_id"])
        if request is None:
            continue
        if request["asset_id"] != qa["asset_id"]:
            raise ValidationError(
                f"{qa_doc.path}: QA asset_id does not match linked edit request"
            )
        asset = assets.get(qa["asset_id"])
        if asset is None:
            continue
        required = expected_hard_gates(asset, request)
        if required:
            try:
                validate_qa_completeness(required, qa)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc


def iter_toml_paths(inputs: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.toml")))
        elif path.suffix == ".toml":
            paths.append(path)
        else:
            raise ValidationError(
                f"{path}: expected a TOML file or directory"
            )
    return sorted(dict.fromkeys(paths))


def validate_paths(paths: Iterable[Path]) -> list[LoadedDocument]:
    documents: list[LoadedDocument] = []
    for path in paths:
        doc = load_document(path)
        validate_document(doc.data, doc.path)
        documents.append(doc)
    cross_validate(documents)
    return documents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        default=["examples"],
        help="TOML file(s) or directories. Default: examples",
    )
    args = parser.parse_args(argv)

    try:
        paths = iter_toml_paths(args.paths)
        if not paths:
            raise ValidationError("no TOML documents found")
        documents = validate_paths(paths)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for doc in documents:
        print(f"OK  {doc.path}")
    print(f"Validated {len(documents)} document(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
