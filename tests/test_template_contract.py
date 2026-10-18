from __future__ import annotations

import json
import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_project  # noqa: E402


class TemplateContractTests(unittest.TestCase):
    def test_asset_template_contains_topology_contract(self) -> None:
        with (ROOT / "templates/asset-manifest.toml").open("rb") as handle:
            data = tomllib.load(handle)
        validate_project.validate_document(
            data, Path("templates/asset-manifest.toml")
        )
        self.assertIn("topology", data)
        self.assertTrue(data["topology"]["components"])
        self.assertTrue(data["topology"]["relationships"])

    def test_edit_template_contains_reference_sufficiency_and_qa_contract(self) -> None:
        with (ROOT / "templates/edit-request.toml").open("rb") as handle:
            data = tomllib.load(handle)
        validate_project.validate_document(
            data, Path("templates/edit-request.toml")
        )
        self.assertIn("reference_sufficiency", data)
        self.assertIn("qa_contract", data)
        self.assertIn(
            "asset_identity",
            data["qa_contract"]["required_hard_gates"],
        )

    def test_qa_template_demonstrates_not_verifiable_status(self) -> None:
        text = (ROOT / "templates/qa-report.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn("NOT_VERIFIABLE", text)

    def test_qa_template_pass_examples_include_evidence_notes(self) -> None:
        with (ROOT / "templates/qa-report.toml").open("rb") as handle:
            data = tomllib.load(handle)
        passing_hard_gates = [
            gate
            for gate in data["gates"]
            if gate["severity"] == "hard" and gate["status"] == "PASS"
        ]
        self.assertTrue(passing_hard_gates)
        self.assertTrue(all(gate["note"].strip() for gate in passing_hard_gates))

    def test_execution_run_template_contains_v04_runtime_fields(self) -> None:
        data = json.loads(
            (ROOT / "templates/execution-run.json").read_text(
                encoding="utf-8"
            )
        )
        for key in (
            "preflight",
            "blocker",
            "issued_packet",
            "required_hard_gates",
            "topology_hard_gates",
        ):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main()
