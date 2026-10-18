from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_project as validator  # noqa: E402


class ValidateProjectTests(unittest.TestCase):
    def test_repository_examples_validate(self) -> None:
        paths = validator.iter_toml_paths([str(ROOT / "examples")])
        documents = validator.validate_paths(paths)
        self.assertGreaterEqual(len(documents), 5)  # legacy KNIFE + v0.6 bootstrap example

    def test_duplicate_reference_is_rejected(self) -> None:
        data = {
            "document_type": "asset_manifest",
            "schema_version": 1,
            "asset_id": "A",
            "primary_master": "M",
            "locks": {"hard": ["silhouette"], "soft": []},
            "references": [
                {
                    "id": "M",
                    "path": "a.png",
                    "state": "approved",
                    "roles": ["identity"],
                },
                {
                    "id": "M",
                    "path": "b.png",
                    "state": "approved",
                    "roles": ["geometry"],
                },
            ],
        }
        with self.assertRaises(validator.ValidationError):
            validator.validate_document(data, Path("asset.toml"))

    def test_primary_master_must_be_approved(self) -> None:
        data = {
            "document_type": "asset_manifest",
            "schema_version": 1,
            "asset_id": "A",
            "primary_master": "M",
            "locks": {"hard": ["silhouette"], "soft": []},
            "references": [
                {
                    "id": "M",
                    "path": "a.png",
                    "state": "draft",
                    "roles": ["identity"],
                },
                {
                    "id": "G",
                    "path": "g.png",
                    "state": "approved",
                    "roles": ["geometry"],
                },
            ],
        }
        with self.assertRaises(validator.ValidationError):
            validator.validate_document(data, Path("asset.toml"))

    def test_invalid_regeneration_budget_is_rejected(self) -> None:
        data = self._asset()
        data["qa"] = {
            "max_repair_passes": 2,
            "max_regeneration_passes": 4,
        }
        with self.assertRaises(validator.ValidationError):
            validator.validate_document(data, Path("asset.toml"))

    def test_local_edit_requires_explicit_edit_target(self) -> None:
        data = self._edit(reference_id="M", roles=["identity"])
        del data["execution"]
        with self.assertRaises(validator.ValidationError):
            validator.validate_document(data, Path("edit.toml"))

    def test_provisional_mode_requires_declared_fields(self) -> None:
        data = self._edit(reference_id="M", roles=["identity"])
        data["reference_sufficiency"] = {
            "required_roles": ["identity", "geometry"],
            "allow_provisional": True,
            "provisional_fields": [],
            "prohibited_assumptions": [],
        }
        with self.assertRaises(validator.ValidationError):
            validator.validate_document(data, Path("edit.toml"))

    def test_local_edit_requires_hard_preserve(self) -> None:
        data = self._edit(reference_id="M", roles=["identity"])
        data["preserve"]["hard"] = []
        with self.assertRaises(validator.ValidationError):
            validator.validate_document(data, Path("edit.toml"))

    def test_pass_report_cannot_have_failed_hard_gate(self) -> None:
        data = {
            "document_type": "qa_report",
            "schema_version": 1,
            "report_id": "Q",
            "asset_id": "A",
            "request_id": "E",
            "status": "PASS",
            "gates": [
                {
                    "name": "silhouette",
                    "severity": "hard",
                    "status": "FAIL",
                }
            ],
            "repair_directives": [],
        }
        with self.assertRaises(validator.ValidationError):
            validator.validate_document(data, Path("qa.toml"))

    def test_repair_minor_requires_directive(self) -> None:
        data = {
            "document_type": "qa_report",
            "schema_version": 1,
            "report_id": "Q",
            "asset_id": "A",
            "request_id": "E",
            "status": "REPAIR_MINOR",
            "gates": [
                {
                    "name": "silhouette",
                    "severity": "hard",
                    "status": "FAIL",
                }
            ],
            "repair_directives": [],
        }
        with self.assertRaises(validator.ValidationError):
            validator.validate_document(data, Path("qa.toml"))

    def test_repair_minor_with_directive_is_valid(self) -> None:
        data = {
            "document_type": "qa_report",
            "schema_version": 1,
            "report_id": "Q",
            "asset_id": "A",
            "request_id": "E",
            "status": "REPAIR_MINOR",
            "gates": [
                {
                    "name": "rivet_center",
                    "severity": "hard",
                    "status": "FAIL",
                }
            ],
            "repair_directives": [
                "Restore only the rivet center to the approved master position."
            ],
        }
        validator.validate_document(data, Path("qa.toml"))

    def test_unknown_reference_binding_is_rejected_cross_document(self) -> None:
        asset = self._asset()
        edit = self._edit(reference_id="UNKNOWN", roles=["identity"])
        edit["execution"]["edit_target_reference_id"] = "M"
        docs = [
            validator.LoadedDocument(Path("asset.toml"), asset),
            validator.LoadedDocument(Path("edit.toml"), edit),
        ]
        for doc in docs:
            validator.validate_document(doc.data, doc.path)
        with self.assertRaises(validator.ValidationError):
            validator.cross_validate(docs)

    def test_undeclared_reference_role_is_rejected(self) -> None:
        asset = self._asset()
        edit = self._edit(reference_id="M", roles=["material"])
        docs = [
            validator.LoadedDocument(Path("asset.toml"), asset),
            validator.LoadedDocument(Path("edit.toml"), edit),
        ]
        for doc in docs:
            validator.validate_document(doc.data, doc.path)
        with self.assertRaises(validator.ValidationError):
            validator.cross_validate(docs)

    def test_edit_target_must_be_bound_reference(self) -> None:
        asset = self._asset()
        asset["references"].append(
            {
                "id": "G",
                "path": "g.png",
                "state": "approved",
                "roles": ["geometry"],
            }
        )
        edit = self._edit(reference_id="M", roles=["identity"])
        edit["execution"]["edit_target_reference_id"] = "G"

        docs = [
            validator.LoadedDocument(Path("asset.toml"), asset),
            validator.LoadedDocument(Path("edit.toml"), edit),
        ]
        for doc in docs:
            validator.validate_document(doc.data, doc.path)

        with self.assertRaises(validator.ValidationError):
            validator.cross_validate(docs)

    @staticmethod
    def _asset() -> dict:
        return {
            "document_type": "asset_manifest",
            "schema_version": 1,
            "asset_id": "A",
            "primary_master": "M",
            "locks": {"hard": ["silhouette"], "soft": []},
            "references": [
                {
                    "id": "M",
                    "path": "a.png",
                    "state": "approved",
                    "roles": ["identity"],
                }
            ],
        }

    @staticmethod
    def _edit(reference_id: str, roles: list[str]) -> dict:
        return {
            "document_type": "edit_request",
            "schema_version": 1,
            "request_id": "E",
            "asset_id": "A",
            "operation": "local_edit",
            "target": "part",
            "change": "finish",
            "execution": {"edit_target_reference_id": reference_id},
            "preserve": {"hard": ["silhouette"], "soft": []},
            "reference_bindings": [
                {"reference_id": reference_id, "roles": roles}
            ],
        }


if __name__ == "__main__":
    unittest.main()
