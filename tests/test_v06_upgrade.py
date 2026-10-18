"""v0.6 behavioral RED tests: first Master + bounded image-region QA."""
from __future__ import annotations

import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import execution_loop
import next_action
import validate_project


BOOTSTRAP_ASSET = """document_type = "asset_manifest"
schema_version = 1
asset_id = "TEST_FIRST"
status = "bootstrap"

[locks]
hard = ["asset_identity"]
soft = []

[qa]
max_repair_passes = 1
max_regeneration_passes = 1
"""

BOOTSTRAP_EDIT = """document_type = "edit_request"
schema_version = 1
request_id = "FIRST_CREATE"
asset_id = "TEST_FIRST"
operation = "create"
target = "a single lamp hero prop"
change = "Create a complete visible desk lamp with a base, arm, and shade."

[reference_sufficiency]
required_roles = []
allow_provisional = false
provisional_fields = []
prohibited_assumptions = ["unseen interiors"]

[preserve]
hard = []
soft = []
"""


def region_contract():
    return {
        "mode": "enforce",
        "pixel_threshold": 15,
        "max_outside_changed_fraction": 0.01,
        "targets": [{"id": "fastener", "bbox": [0.05, 0.05, 0.35, 0.35]}],
        "protected": [{"id": "body", "bbox": [0.6, 0.6, 0.9, 0.9],
                       "max_changed_fraction": 0.0}],
    }


class FirstMasterTests(unittest.TestCase):
    def test_bootstrap_manifest_can_be_validated_without_approved_master(self):
        asset = tomllib.loads(BOOTSTRAP_ASSET)
        edit = tomllib.loads(BOOTSTRAP_EDIT)
        validate_project.validate_document(asset, Path("bootstrap.toml"))
        validate_project.validate_document(edit, Path("edit.toml"))
        validate_project.cross_validate([
            validate_project.LoadedDocument(Path("bootstrap.toml"), asset),
            validate_project.LoadedDocument(Path("edit.toml"), edit),
        ])

    def test_bootstrap_cannot_be_exploited_by_edit_operation(self):
        asset = tomllib.loads(BOOTSTRAP_ASSET)
        edit = tomllib.loads(BOOTSTRAP_EDIT)
        edit["operation"] = "repair"
        edit["reference_bindings"] = []
        with self.assertRaises(validate_project.ValidationError):
            validate_project.cross_validate([
                validate_project.LoadedDocument(Path("bootstrap.toml"), asset),
                validate_project.LoadedDocument(Path("edit.toml"), edit),
            ])

    def test_first_master_real_protocol_and_approved_registration(self):
        from PIL import Image
        import master_lifecycle

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = root / "bootstrap.toml"
            e = root / "edit.toml"
            runpath = root / "run.json"
            a.write_text(BOOTSTRAP_ASSET)
            e.write_text(BOOTSTRAP_EDIT)
            run = execution_loop.init_from_paths(a, e, workspace_root=root)
            self.assertEqual("READY", run["state"])
            self.assertTrue(run["auditable"])
            self.assertEqual("PASS", run["preflight"]["status"])
            execution_loop.save_run(runpath, run)
            packet = next_action.build_from_paths(a, e, runpath)
            self.assertEqual("imagegen_generate", packet["action"])
            img = root / "output.png"
            Image.new("RGB", (24, 20), (65, 70, 80)).save(img)
            updated = execution_loop._record_generated_cli(
                execution_loop.load_run(runpath), "output.png", dry_run=False,
                packet=packet, receipt_path="receipt.json",
                host_attestation="Synthetic test fixture: no model invoked."
            )
            self.assertEqual("QA_PENDING", updated["state"])
            receipt = updated["current_receipt"]
            qa = {
                "document_type": "qa_report", "schema_version": 1,
                "report_id": "FIRST_QA", "asset_id": "TEST_FIRST",
                "request_id": "FIRST_CREATE", "status": "PASS",
                "summary": "Fixture QA only", "repair_directives": [],
                "run_id": updated["run_id"], "iteration": 1,
                "receipt_id": receipt["receipt_id"],
                "result_sha256": receipt["result_sha256"],
                "gates": [{
                    "name": "asset_identity", "status": "PASS", "severity": "hard",
                    "note": "Synthetic test object visible.", "inspection_method": "fixture",
                    "observation": "Known synthetic image."
                }],
            }
            updated = execution_loop.apply_qa(updated, qa)
            self.assertEqual("ACCEPTED", updated["state"])
            execution_loop.save_run(runpath, updated)
            candidate = root / "candidate.json"
            master_lifecycle.create_candidate(
                image_path=img, source_run_path=runpath, reference_id="MASTER_R1",
                revision=1, supersedes=None, output_path=candidate
            )
            qapath = root / "master_qa.toml"
            qapath.write_text("\n".join([
                'document_type = "qa_report"', 'schema_version = 1',
                'report_id = "FIRST_QA"', 'asset_id = "TEST_FIRST"',
                'request_id = "FIRST_CREATE"', 'status = "PASS"',
                'summary = "Synthetic test only"', 'repair_directives = []',
                f'run_id = "{updated["run_id"]}"', 'iteration = 1',
                f'receipt_id = "{receipt["receipt_id"]}"',
                f'result_sha256 = "{receipt["result_sha256"]}"',
                '[master_candidate]', 'reference_id = "MASTER_R1"',
                f'content_sha256 = "{receipt["result_sha256"]}"',
                'actual_pixels_inspected = true', f'source_run_id = "{updated["run_id"]}"',
                '[[gates]]', 'name = "asset_identity"', 'status = "PASS"',
                'severity = "hard"', 'note = "Synthetic fixture."',
                'inspection_method = "fixture"', 'observation = "One lamp."'
            ])+"\n")
            decision = root / "decision.json"
            approved_png = root / "references" / "MASTER_R1.png"
            approved = master_lifecycle.finalize_candidate(
                candidate_record_path=candidate, qa_path=qapath,
                output_path=decision, approved_image_path=approved_png,
            )
            self.assertEqual("approved", approved["state"])
            active = root / "asset.toml"
            master_lifecycle.register_first_master(
                bootstrap_asset_path=a, decision_path=decision,
                output_path=active, roles=["identity", "geometry", "camera", "style"],
            )
            prod = validate_project.load_document(active).data
            validate_project.validate_document(prod, active)
            self.assertEqual(prod["primary_master"], "MASTER_R1")
            self.assertEqual(prod["references"][0]["state"], "approved")
            self.assertEqual(prod["status"], "active")
            with self.assertRaises(validate_project.ValidationError):
                master_lifecycle.register_first_master(
                    bootstrap_asset_path=a, decision_path=decision,
                    output_path=active, roles=["identity"],
                )


class RegionContractTests(unittest.TestCase):
    def test_region_contract_validates_and_enters_prompt_and_packet(self):
        import compile_brief
        asset = {
            "document_type": "asset_manifest", "schema_version": 1,
            "asset_id": "A", "primary_master": "M",
            "references": [{"id":"M","path":"m.png","state":"approved","roles":["identity"]}],
            "locks": {"hard":["identity"],"soft":[]},
        }
        edit = {
            "document_type": "edit_request", "schema_version": 1,
            "request_id":"E","asset_id":"A","operation":"local_edit",
            "target":"fastener","change":"recolor","execution":{"edit_target_reference_id":"M"},
            "preserve":{"hard":["identity"],"soft":[]},
            "reference_bindings":[{"reference_id":"M","roles":["identity"]}],
            "region_contract":region_contract(),
        }
        validate_project.validate_document(edit, Path("edit.toml"))
        prompt=compile_brief.compile_brief(asset,edit)
        self.assertIn("fastener", prompt)
        self.assertIn("PROTECTED", prompt)
        run=execution_loop.init_run(asset,edit)
        self.assertIn("visual.region_preservation",run["required_hard_gates"])
        packet=next_action.build_action_packet(asset,edit,run)
        self.assertEqual(region_contract(),packet["region_contract"])

    def test_invalid_region_contract_rejected(self):
        asset = {
            "document_type": "edit_request", "schema_version":1,
            "request_id":"E","asset_id":"A","operation":"create",
            "target":"lamp","change":"make","preserve":{"hard":[],"soft":[]},
            "region_contract":region_contract(),
        }
        for bad in [
            {"bbox":[0,0,1.1,0.3]},
            {"bbox":[0.2,0.2,0.1,0.3]},
            {"bbox":[0.1,0.1,0.7,0.7]},
        ]:
            e=json.loads(json.dumps(asset))
            e["region_contract"]["targets"][0]["bbox"]=bad["bbox"]
            with self.assertRaises(validate_project.ValidationError):
                validate_project.validate_document(e,Path("edit.toml"))

    def test_changed_pixels_outside_target_are_caught(self):
        from PIL import Image, ImageDraw
        from region_quality import compare_images
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            before=root/"a.png"; after=root/"b.png"
            Image.new("RGB",(100,100),"white").save(before)
            im=Image.open(before)
            dr=ImageDraw.Draw(im)
            dr.rectangle((8,8,25,25),fill="black")
            im.save(after)
            result=compare_images(before,after,region_contract())
            self.assertEqual("PASS",result["status"])
            dr.rectangle((70,70,78,78),fill="black")
            im.save(after)
            result=compare_images(before,after,region_contract())
            self.assertEqual("FAIL",result["status"])
            self.assertGreater(result["outside_targets"]["changed_fraction"],0.0)
            self.assertEqual(64,len(result["result_sha256"]))

    def test_region_results_bound_to_actual_pixels_during_qa(self):
        """A gate must not be bypassable by a hand-written PASS."""
        from PIL import Image, ImageDraw
        from region_quality import compare_images
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            before=root/"a.png"; after=root/"b.png"
            Image.new("RGB",(100,100),"white").save(before)
            im=Image.open(before); ImageDraw.Draw(im).rectangle((70,70,78,78),fill="black");im.save(after)
            measured=compare_images(before,after,region_contract())
            self.assertEqual("FAIL",measured["status"])
            # Real apply-qa must recompute from receipt-bound source and reject fabricated PASS.
            from region_quality import verify_region_gate
            with self.assertRaises(validate_project.ValidationError):
                verify_region_gate(region_contract(),before,after,"PASS")

class FirstMasterDecisionIntegrityTests(unittest.TestCase):
    def test_forged_approved_decision_cannot_register_production_master(self):
        """A JSON claiming 'approved' is not enough without receipt/QA lineage."""
        from PIL import Image
        import master_lifecycle
        from artifact_integrity import sha256_file
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            image=root/"forged-approved.png"
            Image.new("RGB",(12,12),"white").save(image)
            bootstrap=root/"bootstrap.toml"
            bootstrap.write_text(BOOTSTRAP_ASSET)
            decision=root/"decision.json"
            decision.write_text(json.dumps({
                "state":"approved","asset_id":"TEST_FIRST","reference_id":"MASTER_R1",
                "approved_path":str(image),
                "lineage":{
                    "revision":1,"supersedes":None,
                    "content_sha256":sha256_file(image),
                    "source_run_id":"FORGED","source_qa_report_id":"FORGED_QA",
                    "source_run_path":str(root/"nonexistent-run.json"),
                    "source_qa_path":str(root/"nonexistent-qa.toml"),
                },
            }))
            with self.assertRaises((validate_project.ValidationError, OSError)):
                master_lifecycle.register_first_master(
                    bootstrap_asset_path=bootstrap,decision_path=decision,
                    output_path=root/"active.toml",roles=["identity"],
                )
