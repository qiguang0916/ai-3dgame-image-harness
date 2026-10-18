"""Auditable v0.6 QA workflow tests (synthetic images, not host imagegen calls)."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import execution_loop
import next_action
import validate_project


class V06IntegrationTests(unittest.TestCase):
    def _init(self, root: Path, *, tech: bool = False):
        from PIL import Image
        image=root/"master.png"
        Image.new("RGB",(40,40),"white").save(image)
        asset=root/"asset.toml";edit=root/"edit.toml";runpath=root/"run.json"
        asset.write_text('''document_type="asset_manifest"
schema_version=1
asset_id="REGION_001"
primary_master="M"
[locks]
hard=["identity"]
soft=[]
[[references]]
id="M"
path="master.png"
state="approved"
roles=["identity","geometry","camera"]
''')
        edit.write_text('''document_type="edit_request"
schema_version=1
request_id="REGION_EDIT"
asset_id="REGION_001"
operation="local_edit"
target="corner finish"
change="only recolor the small upper-left region"
[execution]
edit_target_reference_id="M"
[preserve]
hard=["identity"]
soft=[]
[region_contract]
mode="enforce"
pixel_threshold=15
max_outside_changed_fraction=0.02
[[region_contract.targets]]
id="editable"
bbox=[0.0,0.0,0.25,0.25]
[[region_contract.protected]]
id="protected"
bbox=[0.5,0.5,0.95,0.95]
max_changed_fraction=0.0
[[reference_bindings]]
reference_id="M"
roles=["identity","geometry","camera"]
''' + ('''
[output]
expected_size="40x40"
require_transparency=false
''' if tech else ''))
        run=execution_loop.init_from_paths(asset,edit,workspace_root=root)
        execution_loop.save_run(runpath,run)
        packet=next_action.build_from_paths(asset,edit,runpath)
        return asset,edit,runpath,packet

    def _generate(self, root: Path, runpath: Path, packet: dict, *, corrupt:bool):
        from PIL import Image,ImageDraw
        image=Image.open(root/"master.png")
        draw=ImageDraw.Draw(image)
        draw.rectangle((1,1,6,6),fill="blue")
        if corrupt:
            draw.rectangle((26,26,32,32),fill="black")
        result=root/"edited.png"
        image.save(result)
        run=execution_loop.load_run(runpath)
        updated=execution_loop._record_generated_cli(
            run,"edited.png",dry_run=False,packet=packet,receipt_path="receipt.json",
            host_attestation="Synthetic unit-test fixture; no real OpenAI image generation."
        )
        execution_loop.save_run(runpath,updated)
        return updated

    def _qa(self,run,*,status="PASS",region="PASS",technical="PASS"):
        gates=[]
        for gate in run["required_hard_gates"]:
            value=region if gate=="visual.region_preservation" else (
                technical if gate=="image.technical_output" else "PASS"
            )
            gates.append({
                "name":gate,"severity":"hard","status":value,
                "note":"Observed deterministic test pixels.",
                "inspection_method":"fixture_measured",
                "observation":"Synthetic image compare only.",
            })
        r=run["current_receipt"]
        return {
            "document_type":"qa_report","schema_version":1,
            "report_id":"QA","asset_id":run["asset_id"],
            "request_id":run["request_id"],"status":status,
            "summary":"Synthetic fixture; not real visual QA.",
            "repair_directives":["Restore the protected region."] if status=="REPAIR_MINOR" else [],
            "run_id":run["run_id"],"iteration":run["iteration"],
            "receipt_id":r["receipt_id"],"result_sha256":r["result_sha256"],
            "gates":gates,
        }

    def test_true_region_violation_cannot_be_accepted_by_false_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,runpath,packet=self._init(root)
            run=self._generate(root,runpath,packet,corrupt=True)
            with self.assertRaisesRegex(validate_project.ValidationError,"region QA measured FAIL"):
                execution_loop.apply_qa(run,self._qa(run))

    def test_measured_region_failure_routes_to_repair_with_objective_delta(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            asset,edit,runpath,packet=self._init(root)
            run=self._generate(root,runpath,packet,corrupt=True)
            repaired=execution_loop.apply_qa(
                run,self._qa(run,status="REPAIR_MINOR",region="FAIL")
            )
            self.assertEqual("REPAIR_READY",repaired["state"])
            self.assertGreater(len(repaired["last_qa"]["region_quality"]["failures"]),0)
            prompt=next_action.build_action_packet(
                validate_project.load_document(asset).data,
                validate_project.load_document(edit).data,
                repaired
            )["prompt"]
            self.assertIn("MEASURED REGION FAILURES",prompt)
            self.assertIn("protected region",prompt)

    def test_region_and_technical_gates_both_pass_on_unchanged_regions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,runpath,packet=self._init(root,tech=True)
            run=self._generate(root,runpath,packet,corrupt=False)
            accepted=execution_loop.apply_qa(run,self._qa(run))
            self.assertEqual("ACCEPTED",accepted["state"])
            self.assertEqual("PASS",accepted["last_qa"]["region_quality"]["status"])
            self.assertEqual("PASS",accepted["last_qa"]["technical_output"]["status"])

    def test_wrong_technical_size_cannot_be_falsely_passed(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,runpath,packet=self._init(root,tech=True)
            run=self._generate(root,runpath,packet,corrupt=False)
            # Replace result with a new size and re-bind a matching synthetic receipt.
            # The test calls deterministic gate directly: QA is never allowed to mark it PASS.
            Image.new("RGB",(20,20),"white").save(root/"smaller.png")
            from asset_report import verify_output_gate
            with self.assertRaisesRegex(validate_project.ValidationError,"technical output QA measured FAIL"):
                verify_output_gate({"expected_size":"40x40"},root/"smaller.png","PASS")


if __name__=="__main__":
    unittest.main()

class MajorTopologyRoutingTests(unittest.TestCase):
    def test_topology_fail_restarts_from_approved_source_not_failed_result(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture=V06IntegrationTests()
            asset,edit,runpath,_=fixture._init(root)
            with asset.open("a") as fh:
                fh.write('''
[topology]
forbid_extra_components=true
[[topology.components]]
id="control_knob"
required=true
count=2
count_unit="visible_instance"
visual_definition="two distinct visible control knobs"
excludes=["specular highlights"]
''')
            # Re-initialize so the new immutable topology contract is captured
            run=execution_loop.init_from_paths(asset,edit,workspace_root=root)
            execution_loop.save_run(runpath,run)
            packet=next_action.build_from_paths(asset,edit,runpath)
            run=fixture._generate(root,runpath,packet,corrupt=False)
            qa=fixture._qa(run,status="REPAIR_MINOR",region="PASS")
            for gate in qa["gates"]:
                if gate["name"]=="topology.component.control_knob.count":
                    gate["status"]="FAIL"
                    gate["note"]="Observed only one visible knob, expected two."
            updated=execution_loop.apply_qa(run,qa)
            self.assertEqual("REGENERATE_READY",updated["state"])
            self.assertEqual(1,updated["regeneration_passes"])
            pkt=next_action.build_action_packet(
                validate_project.load_document(asset).data,
                validate_project.load_document(edit).data,updated
            )
            self.assertEqual("approved_source_not_failed_result",pkt["restart_policy"])
            self.assertEqual("M",pkt["edit_target"]["reference_id"])
            self.assertNotEqual("edited.png",pkt["edit_target"]["path"])
