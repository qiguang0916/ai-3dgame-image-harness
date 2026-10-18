#!/usr/bin/env python3
"""Compile a delta-only repair brief from a Visual QA report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from validate_project import (
    ValidationError,
    cross_validate,
    load_document,
    validate_document,
)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def compile_repair_brief(
    asset: dict[str, Any],
    edit: dict[str, Any],
    qa: dict[str, Any],
) -> str:
    if qa["status"] != "REPAIR_MINOR":
        raise ValidationError(
            "repair brief requires a QA report with status REPAIR_MINOR"
        )
    directives = qa.get("repair_directives", [])
    if not directives:
        raise ValidationError(
            "REPAIR_MINOR QA must contain repair_directives"
        )

    reference_by_id = {ref["id"]: ref for ref in asset["references"]}
    reference_lines: list[str] = []
    for index, binding in enumerate(
        edit.get("reference_bindings", []),
        start=1,
    ):
        ref = reference_by_id[binding["reference_id"]]
        roles = ", ".join(binding["roles"])
        reference_lines.append(
            f"REF_{index}: {ref['id']} | path={ref['path']} | roles={roles}"
        )

    failed_gates = [
        gate["name"]
        for gate in qa.get("gates", [])
        if gate.get("status") not in {"PASS", "NOTE"}
    ]
    passed_gates = [
        gate["name"]
        for gate in qa.get("gates", [])
        if gate.get("status") == "PASS"
    ]

    hard_preserve = _dedupe(
        [
            *asset.get("locks", {}).get("hard", []),
            *edit.get("preserve", {}).get("hard", []),
        ]
    )
    soft_preserve = _dedupe(
        [
            *asset.get("locks", {}).get("soft", []),
            *edit.get("preserve", {}).get("soft", []),
        ]
    )

    lines = [
        f"ASSET: {asset['asset_id']}",
        "OPERATION: repair",
        "",
        "ORIGINAL TARGET:",
        str(edit["target"]),
        "",
        "FAILED QA GATES:",
    ]
    lines.extend(f"- {gate}" for gate in failed_gates or ["unspecified"])

    measured=qa.get("region_quality")
    if isinstance(measured, dict) and measured.get("failures"):
        lines.extend(["", "MEASURED REGION FAILURES:"])
        lines.extend(f"- {reason}" for reason in measured["failures"])
        lines.append("- Repair only the failed areas and restore other pixels toward the approved Master.")
    technical=qa.get("technical_output")
    if isinstance(technical, dict) and technical.get("failures"):
        lines.extend(["", "MEASURED TECHNICAL OUTPUT FAILURES:"])
        lines.extend(f"- {reason}" for reason in technical["failures"])

    lines.extend(["", "CORRECTION DELTA:"])
    lines.extend(f"- {directive}" for directive in directives)

    lines.extend(["", "REFERENCE ROLES:"])
    lines.extend(reference_lines or ["(none)"])
    if edit.get("prompt_intelligence"):
        from prompt_control import repair_authority_guidance
        lines.extend(["", repair_authority_guidance(asset, edit)])

    lines.extend(["", "HARD PRESERVE:"])
    lines.extend(f"- {item}" for item in hard_preserve)

    lines.extend(["", "SOFT PRESERVE:"])
    lines.extend(f"- {item}" for item in soft_preserve)

    lines.extend(["", "ALREADY PASSED — DO NOT DISTURB:"])
    lines.extend(f"- {gate}" for gate in passed_gates or ["all unaffected regions"])

    lines.extend(
        [
            "",
            "EDIT TARGET:",
            "Use the failed generated result as the edit target.",
            "",
            "EDIT BOUNDARY:",
            "Correct only the failed gates. Do not redesign unaffected regions.",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def compile_from_paths(
    asset_path: Path,
    edit_path: Path,
    qa_path: Path,
) -> str:
    asset_doc = load_document(asset_path)
    edit_doc = load_document(edit_path)
    qa_doc = load_document(qa_path)

    for doc in (asset_doc, edit_doc, qa_doc):
        validate_document(doc.data, doc.path)
    cross_validate([asset_doc, edit_doc, qa_doc])

    return compile_repair_brief(
        asset_doc.data,
        edit_doc.data,
        qa_doc.data,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset_manifest", type=Path)
    parser.add_argument("edit_request", type=Path)
    parser.add_argument("qa_report", type=Path)
    args = parser.parse_args(argv)

    try:
        print(
            compile_from_paths(
                args.asset_manifest,
                args.edit_request,
                args.qa_report,
            ),
            end="",
        )
    except (OSError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
