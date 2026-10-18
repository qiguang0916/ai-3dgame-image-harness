from __future__ import annotations

import base64
import binascii
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import master_lifecycle  # noqa: E402
import artifact_integrity  # noqa: E402
import topology_contract  # noqa: E402
import validate_project  # noqa: E402


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class V05TopologyTests(unittest.TestCase):
    def _asset(self) -> dict:
        return {
            "document_type": "asset_manifest",
            "schema_version": 1,
            "asset_id": "A",
            "primary_master": "MASTER",
            "locks": {"hard": ["identity"], "soft": []},
            "references": [
                {
                    "id": "MASTER",
                    "path": "master.png",
                    "state": "approved",
                    "roles": ["identity"],
                }
            ],
            "topology": {
                "forbid_extra_components": True,
                "allowed_visible_details": ["maker mark", "assembly seam"],
                "components": [
                    {
                        "id": "fastener",
                        "required": True,
                        "count": 3,
                        "count_unit": "visible_instance",
                        "visual_definition": "round fastener head visible from camera",
                        "excludes": ["reflections", "engraved circles"],
                    }
                ],
                "relationships": [],
            },
        }

    def test_enhanced_component_semantics_reach_packet(self) -> None:
        asset = self._asset()
        topology_contract.validate_topology_schema(asset, "asset.toml")
        packet = topology_contract.packet_topology(asset)
        self.assertEqual(
            {
                "id": "fastener",
                "count": 3,
                "count_unit": "visible_instance",
                "visual_definition": "round fastener head visible from camera",
                "excludes": ["reflections", "engraved circles"],
            },
            packet["required_components"][0],
        )
        self.assertEqual(
            ["maker mark", "assembly seam"],
            packet["allowed_visible_details"],
        )

    def test_enhanced_component_semantics_reach_image_prompt(self) -> None:
        import compile_brief

        edit = {
            "document_type": "edit_request",
            "schema_version": 1,
            "request_id": "E",
            "asset_id": "A",
            "operation": "create",
            "target": "asset",
            "change": "create the asset",
            "preserve": {"hard": [], "soft": []},
            "reference_bindings": [],
        }
        prompt = compile_brief.compile_brief(self._asset(), edit)
        self.assertIn("count_unit=visible_instance", prompt)
        self.assertIn("visual_definition=round fastener head", prompt)
        self.assertIn("excludes: reflections, engraved circles", prompt)
        self.assertIn("maker mark, assembly seam", prompt)

    def test_all_count_units_are_supported(self) -> None:
        for unit in ("assembly", "visible_instance", "piece"):
            asset = self._asset()
            asset["topology"]["components"][0]["count_unit"] = unit
            topology_contract.validate_topology_schema(asset, "asset.toml")

        asset = self._asset()
        asset["topology"]["components"][0]["count_unit"] = "object"
        with self.assertRaises(validate_project.ValidationError):
            topology_contract.validate_topology_schema(asset, "asset.toml")

    def test_bool_is_not_a_component_count(self) -> None:
        asset = self._asset()
        asset["topology"]["components"][0]["count"] = True
        with self.assertRaises(validate_project.ValidationError):
            topology_contract.validate_topology_schema(asset, "asset.toml")

    def test_required_and_forbid_extra_components_must_be_boolean(self) -> None:
        asset = self._asset()
        asset["topology"]["components"][0]["required"] = 1
        with self.assertRaises(validate_project.ValidationError):
            topology_contract.validate_topology_schema(asset, "asset.toml")

        asset = self._asset()
        asset["topology"]["forbid_extra_components"] = "yes"
        with self.assertRaises(validate_project.ValidationError):
            topology_contract.validate_topology_schema(asset, "asset.toml")

        asset = self._asset()
        asset["topology"]["relationships"] = [
            {
                "id": "self_alignment",
                "type": "aligned_with",
                "members": ["fastener", "fastener"],
                "required": 1,
            }
        ]
        with self.assertRaises(validate_project.ValidationError):
            topology_contract.validate_topology_schema(asset, "asset.toml")

    def test_explicit_enhanced_component_fields_must_be_complete(self) -> None:
        for missing in ("count_unit", "visual_definition", "excludes"):
            asset = self._asset()
            del asset["topology"]["components"][0][missing]
            with self.subTest(missing=missing):
                with self.assertRaises(validate_project.ValidationError):
                    topology_contract.validate_topology_schema(
                        asset, "asset.toml"
                    )

    def test_visual_definition_and_lists_are_strict(self) -> None:
        asset = self._asset()
        asset["topology"]["components"][0]["visual_definition"] = "  "
        with self.assertRaises(validate_project.ValidationError):
            topology_contract.validate_topology_schema(asset, "asset.toml")

        asset = self._asset()
        asset["topology"]["components"][0]["excludes"] = [
            "reflections",
            "reflections",
        ]
        with self.assertRaises(validate_project.ValidationError):
            topology_contract.validate_topology_schema(asset, "asset.toml")

        asset = self._asset()
        asset["topology"]["components"][0]["excludes"] = "reflections"
        with self.assertRaises(validate_project.ValidationError):
            topology_contract.validate_topology_schema(asset, "asset.toml")

        asset = self._asset()
        asset["topology"]["allowed_visible_details"] = [""]
        with self.assertRaises(validate_project.ValidationError):
            topology_contract.validate_topology_schema(asset, "asset.toml")

    def test_legacy_component_gets_compatible_packet_defaults(self) -> None:
        asset = self._asset()
        component = asset["topology"]["components"][0]
        for key in ("count_unit", "visual_definition", "excludes"):
            del component[key]
        del asset["topology"]["allowed_visible_details"]

        topology_contract.validate_topology_schema(asset, "asset.toml")
        packet = topology_contract.packet_topology(asset)
        self.assertEqual("piece", packet["required_components"][0]["count_unit"])
        self.assertEqual(
            "fastener",
            packet["required_components"][0]["visual_definition"],
        )
        self.assertEqual([], packet["required_components"][0]["excludes"])
        self.assertEqual([], packet["allowed_visible_details"])


class MasterLifecycleTests(unittest.TestCase):
    def _write_source_run(self, folder: Path, image: Path) -> Path:
        run_path = folder / "run.json"
        result = artifact_integrity.file_binding(folder, image)
        receipt = {
            "schema_version": 1,
            "run_id": "RUN_2",
            "iteration": 1,
            "packet_id": "1" * 64,
            "packet_sha256": "1" * 64,
            "action": "imagegen_edit",
            "fallback_policy": "none",
            "input_bindings": [],
            "result": result,
            "result_sha256": result["sha256"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "host_attestation": {"statement": "built-in imagegen"},
        }
        receipt["receipt_id"] = artifact_integrity.receipt_digest(receipt)
        run_path.write_text(
            json.dumps(
                {
                    "run_id": "RUN_2",
                    "asset_id": "A",
                    "request_id": "EDIT_2",
                    "state": "QA_PENDING",
                    "iteration": 1,
                    "workspace_root": str(folder),
                    "auditable": True,
                    "current_result_path": result["path"],
                    "current_receipt": receipt,
                    "required_hard_gates": ["identity"],
                }
            ),
            encoding="utf-8",
        )
        return run_path

    def _write_qa(self, folder: Path, digest: str, status: str = "PASS") -> Path:
        qa_path = folder / "qa.toml"
        run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        receipt = run["current_receipt"]
        gate_status = (
            "PASS"
            if status in {"PASS", "PASS_WITH_NOTES"}
            else "NOT_VERIFIABLE" if status == "BLOCKED" else "FAIL"
        )
        qa_path.write_text(
            "\n".join(
                [
                    'document_type = "qa_report"',
                    "schema_version = 1",
                    'report_id = "QA_2"',
                    'asset_id = "A"',
                    'request_id = "EDIT_2"',
                    f'status = "{status}"',
                    'summary = "Inspected actual candidate pixels."',
                    "repair_directives = []",
                    'run_id = "RUN_2"',
                    "iteration = 1",
                    f'receipt_id = "{receipt["receipt_id"]}"',
                    f'result_sha256 = "{receipt["result_sha256"]}"',
                    "",
                    "[master_candidate]",
                    'reference_id = "MASTER_R2"',
                    f'content_sha256 = "{digest}"',
                    "actual_pixels_inspected = "
                    + ("false" if status == "BLOCKED" else "true"),
                    'source_run_id = "RUN_2"',
                    "",
                    "[[gates]]",
                    'name = "identity"',
                    'severity = "hard"',
                    f'status = "{gate_status}"',
                    'note = "Compared with approved master."',
                    'inspection_method = "direct_pixel_inspection"',
                    'observation = "The candidate retains the required identity."',
                ]
            ),
            encoding="utf-8",
        )
        run_path = folder / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["state"] = "ACCEPTED"
        run["last_qa"] = {
            "report_id": "QA_2",
            "status": status,
            "receipt_id": receipt["receipt_id"],
            "result_sha256": receipt["result_sha256"],
        }
        run_path.write_text(json.dumps(run), encoding="utf-8")
        return qa_path

    def _candidate(self, folder: Path) -> tuple[Path, dict]:
        image = folder / "candidate.png"
        image.write_bytes(PNG_1X1)
        run = self._write_source_run(folder, image)
        record_path = folder / "candidate.json"
        record = master_lifecycle.create_candidate(
            image_path=image,
            source_run_path=run,
            reference_id="MASTER_R2",
            revision=2,
            supersedes="MASTER_R1",
            output_path=record_path,
        )
        return record_path, record

    def _distinct_png(self) -> bytes:
        text_data = b"audit\x00later"
        chunk = (
            len(text_data).to_bytes(4, "big")
            + b"tEXt"
            + text_data
            + (binascii.crc32(b"tEXt" + text_data) & 0xFFFFFFFF).to_bytes(
                4, "big"
            )
        )
        return PNG_1X1[:-12] + chunk + PNG_1X1[-12:]

    def test_candidate_requires_a_decodable_image_not_just_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            image = folder / "candidate.png"
            image.write_text("not an image", encoding="utf-8")
            source_result = folder / "source.png"
            source_result.write_bytes(PNG_1X1)
            run = self._write_source_run(folder, source_result)
            with self.assertRaises(validate_project.ValidationError):
                master_lifecycle.create_candidate(
                    image_path=image,
                    source_run_path=run,
                    reference_id="MASTER_R2",
                    revision=2,
                    supersedes="MASTER_R1",
                    output_path=folder / "candidate.json",
                )

    def test_candidate_rejects_non_png_even_when_decodable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            image = folder / "candidate.gif"
            image.write_bytes(b"GIF89a\x01\x00\x01\x00\x00\x00\x00,\x00;")
            source_result = folder / "source.png"
            source_result.write_bytes(PNG_1X1)
            run = self._write_source_run(folder, source_result)
            with self.assertRaisesRegex(
                validate_project.ValidationError, "must be PNG"
            ):
                master_lifecycle.create_candidate(
                    image_path=image,
                    source_run_path=run,
                    reference_id="MASTER_R2",
                    revision=2,
                    supersedes="MASTER_R1",
                    output_path=folder / "candidate.json",
                )

    def test_candidate_or_draft_reference_cannot_be_used_in_production(self) -> None:
        for state in ("candidate", "draft"):
            asset = {
                "document_type": "asset_manifest",
                "schema_version": 1,
                "asset_id": "A",
                "primary_master": "OLD",
                "locks": {"hard": ["identity"], "soft": []},
                "references": [
                    {
                        "id": "OLD",
                        "path": "old.png",
                        "state": "approved",
                        "roles": ["identity"],
                    },
                    {
                        "id": "MASTER_R2",
                        "path": "candidate.png",
                        "state": state,
                        "roles": ["identity"],
                    },
                ],
            }
            edit = {
                "document_type": "edit_request",
                "schema_version": 1,
                "request_id": "E",
                "asset_id": "A",
                "operation": "local_edit",
                "target": "surface",
                "change": "finish",
                "execution": {"edit_target_reference_id": "MASTER_R2"},
                "preserve": {"hard": ["identity"], "soft": []},
                "reference_bindings": [
                    {"reference_id": "MASTER_R2", "roles": ["identity"]}
                ],
            }
            docs = [
                validate_project.LoadedDocument(Path("asset.toml"), asset),
                validate_project.LoadedDocument(Path("edit.toml"), edit),
            ]
            for doc in docs:
                validate_project.validate_document(doc.data, doc.path)
            with self.subTest(state=state):
                with self.assertRaises(validate_project.ValidationError):
                    validate_project.cross_validate(docs)

    def test_explicit_approved_master_lineage_must_be_complete(self) -> None:
        asset = {
            "document_type": "asset_manifest",
            "schema_version": 1,
            "asset_id": "A",
            "primary_master": "MASTER_R2",
            "locks": {"hard": ["identity"], "soft": []},
            "references": [
                {
                    "id": "MASTER_R1",
                    "path": "r1.png",
                    "state": "superseded",
                    "roles": ["identity"],
                },
                {
                    "id": "MASTER_R2",
                    "path": "r2.png",
                    "state": "approved",
                    "roles": ["identity"],
                    "revision": 2,
                },
            ],
        }
        with self.assertRaises(validate_project.ValidationError):
            validate_project.validate_document(asset, Path("asset.toml"))

    def test_approval_binds_digest_qa_run_and_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            candidate_path, candidate = self._candidate(folder)
            qa = self._write_qa(folder, candidate["content_sha256"])
            approved_image = folder / "masters" / "master-r2.png"
            decision_path = folder / "approved.json"

            decision = master_lifecycle.finalize_candidate(
                candidate_record_path=candidate_path,
                qa_path=qa,
                output_path=decision_path,
                approved_image_path=approved_image,
            )

            self.assertEqual("approved", decision["state"])
            self.assertEqual(2, decision["lineage"]["revision"])
            self.assertEqual("MASTER_R1", decision["lineage"]["supersedes"])
            self.assertEqual(
                candidate["content_sha256"],
                decision["lineage"]["content_sha256"],
            )
            self.assertEqual("RUN_2", decision["lineage"]["source_run_id"])
            self.assertEqual("QA_2", decision["lineage"]["source_qa_report_id"])
            self.assertEqual(PNG_1X1, approved_image.read_bytes())

    def test_approval_rejects_qa_for_a_different_candidate_digest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            candidate_path, _ = self._candidate(folder)
            qa = self._write_qa(folder, "0" * 64)
            with self.assertRaises(validate_project.ValidationError):
                master_lifecycle.finalize_candidate(
                    candidate_record_path=candidate_path,
                    qa_path=qa,
                    output_path=folder / "approved.json",
                    approved_image_path=folder / "master-r2.png",
                )

    def test_approval_rejects_unrelated_gate_or_stale_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            candidate_path, candidate = self._candidate(folder)
            qa = self._write_qa(folder, candidate["content_sha256"])
            text = qa.read_text(encoding="utf-8")
            qa.write_text(text.replace('name = "identity"', 'name = "arbitrary"'), encoding="utf-8")
            with self.assertRaises(validate_project.ValidationError):
                master_lifecycle.finalize_candidate(
                    candidate_record_path=candidate_path,
                    qa_path=qa,
                    output_path=folder / "unrelated.json",
                    approved_image_path=folder / "unrelated.png",
                )

        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            candidate_path, candidate = self._candidate(folder)
            qa = self._write_qa(folder, candidate["content_sha256"])
            text = qa.read_text(encoding="utf-8")
            receipt_id = json.loads(
                (folder / "run.json").read_text(encoding="utf-8")
            )["current_receipt"]["receipt_id"]
            qa.write_text(text.replace(receipt_id, "0" * 64), encoding="utf-8")
            with self.assertRaises(validate_project.ValidationError):
                master_lifecycle.finalize_candidate(
                    candidate_record_path=candidate_path,
                    qa_path=qa,
                    output_path=folder / "stale.json",
                    approved_image_path=folder / "stale.png",
                )

    def test_approval_rejects_candidate_stale_against_later_run_result(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            candidate_path, candidate = self._candidate(folder)
            later = folder / "later.png"
            later.write_bytes(self._distinct_png())
            run_path = folder / "run.json"
            run = json.loads(run_path.read_text(encoding="utf-8"))
            result = artifact_integrity.file_binding(folder, later)
            receipt = run["current_receipt"]
            receipt["result"] = result
            receipt["result_sha256"] = result["sha256"]
            receipt.pop("receipt_id")
            receipt["receipt_id"] = artifact_integrity.receipt_digest(receipt)
            run["current_result_path"] = result["path"]
            run["current_receipt"] = receipt
            run_path.write_text(json.dumps(run), encoding="utf-8")
            qa = self._write_qa(folder, candidate["content_sha256"])

            with self.assertRaisesRegex(
                validate_project.ValidationError, "does not match source run current receipt"
            ):
                master_lifecycle.finalize_candidate(
                    candidate_record_path=candidate_path,
                    qa_path=qa,
                    output_path=folder / "stale-result.json",
                    approved_image_path=folder / "stale-result.png",
                )

    def test_approval_rejects_alternate_pass_qa_after_source_routes_to_repair(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            candidate_path, candidate = self._candidate(folder)
            qa = self._write_qa(folder, candidate["content_sha256"])
            run_path = folder / "run.json"
            run = json.loads(run_path.read_text(encoding="utf-8"))
            run["state"] = "REPAIR_READY"
            run["last_qa"]["status"] = "REPAIR_MINOR"
            run_path.write_text(json.dumps(run), encoding="utf-8")

            with self.assertRaisesRegex(
                validate_project.ValidationError, "requires an ACCEPTED source run"
            ):
                master_lifecycle.finalize_candidate(
                    candidate_record_path=candidate_path,
                    qa_path=qa,
                    output_path=folder / "alternate.json",
                    approved_image_path=folder / "alternate.png",
                )

    def test_promotion_requires_a_new_path_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            candidate_path, candidate = self._candidate(folder)
            qa = self._write_qa(folder, candidate["content_sha256"])

            with self.assertRaises(validate_project.ValidationError):
                master_lifecycle.finalize_candidate(
                    candidate_record_path=candidate_path,
                    qa_path=qa,
                    output_path=folder / "approved.json",
                    approved_image_path=Path(candidate["candidate_path"]),
                )

            existing = folder / "already-there.png"
            existing.write_bytes(PNG_1X1)
            with self.assertRaises(validate_project.ValidationError):
                master_lifecycle.finalize_candidate(
                    candidate_record_path=candidate_path,
                    qa_path=qa,
                    output_path=folder / "approved.json",
                    approved_image_path=existing,
                )

    def test_non_passing_qa_finishes_rejected_or_blocked_without_promotion(self) -> None:
        for qa_status, expected in (
            ("REGENERATE_MAJOR", "rejected"),
            ("BLOCKED", "blocked"),
        ):
            with self.subTest(qa_status=qa_status):
                with tempfile.TemporaryDirectory() as raw:
                    folder = Path(raw)
                    candidate_path, candidate = self._candidate(folder)
                    qa = self._write_qa(
                        folder, candidate["content_sha256"], qa_status
                    )
                    decision = master_lifecycle.finalize_candidate(
                        candidate_record_path=candidate_path,
                        qa_path=qa,
                        output_path=folder / "decision.json",
                    )
                    self.assertEqual(expected, decision["state"])
                    self.assertNotIn("approved_path", decision)


if __name__ == "__main__":
    unittest.main()
