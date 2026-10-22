"""v0.13 native strict-ROI lineage tests: SYNTHETIC ONLY, never production proof."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))

from artifact_integrity import sha256_bytes, sha256_file
from production_autopilot import drive
from production_audit import audit_run
from native_strict_provenance import _proof, verify_native_strict_derivation
from validate_project import ValidationError
import test_v06_integration as old_fixtures
import test_v09_autopilot as host_fixtures


class StrictStubHost(host_fixtures.StubHost):
    """Offline fake must never masquerade as an authenticated native source."""
    def execute(self, packet, reviewer=False):
        value, attestation, transcript = super().execute(packet, reviewer=reviewer)
        if not reviewer:
            attestation = {
                "backend": "synthetic_offline_stub_NOT_NATIVE",
                "packet_id": packet["packet_id"],
                "result_sha256": sha256_bytes(value),
                "event_transcript_sha256": sha256_bytes(transcript),
                "model_identity_verified": False,
            }
        else:
            attestation = {
                "backend": "synthetic_offline_stub_NOT_NATIVE",
                "event_transcript_sha256": sha256_bytes(transcript),
            }
        return value,attestation,transcript


class NativeStrictLineageTests(unittest.TestCase):
    def fixture(self, root, *, strict=True, misaligned=False):
        from PIL import Image,ImageDraw
        asset,edit,run,_=old_fixtures.V06IntegrationTests()._init(root)
        run.unlink()
        text=edit.read_text()
        if strict:
            mask=root/"mask.png"
            protected=Image.new("L",(40,40),255)
            draw=ImageDraw.Draw(protected)
            draw.rectangle((0,0,9,9),fill=0)
            protected.save(mask)
            text+=('\n[region_contract.strict_mask]\n'
                   'path="mask.png"\n'
                   f'sha256="{sha256_file(mask)}"\n'
                   f'reference_sha256="{sha256_file(root/"master.png")}"\n'
                   '\n[[region_contract.required_edit_points]]\n'
                   'id="target_corner"\nuv=[0.1,0.1]\n')
            edit.write_text(text)
        with Image.open(root/"master.png") as original:
            candidate=original.copy()
        draw=ImageDraw.Draw(candidate)
        draw.rectangle((1,1,6,6),fill="blue")
        draw.rectangle((28,28,35,35),fill="black")
        if misaligned:
            candidate=candidate.resize((42,40))
        buf=io.BytesIO()
        candidate.save(buf,format="PNG")
        return asset,edit,run,StrictStubHost(buf.getvalue())

    def started(self,root,*,strict=True,misaligned=False):
        asset,edit,run,host=self.fixture(root,strict=strict,misaligned=misaligned)
        first=drive(asset,edit,root,run,host=host,max_actions=1)
        step=root/"run.json.production"/"0000-imagegen_edit"
        return asset,edit,run,host,first,step

    def bound(self,run,step):
        record=json.loads(run.read_text())
        packet=json.loads((step/"packet.json").read_text())
        receipt=json.loads((step/"receipt.json").read_text())
        attestation=json.loads((step/"attestation.json").read_text())
        return record,packet,receipt,attestation

    def test_opt_in_generates_native_and_derived_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            asset,edit,run,host,first,step=self.started(root)
            self.assertEqual(first["state"],"QA_PENDING")
            self.assertEqual(host.actions,["imagegen_edit"])
            self.assertTrue((step/"native-generated.png").is_file())
            self.assertTrue((step/"generated.png").is_file())
            original=(root/"master.png")
            from PIL import Image
            with Image.open(original) as a, Image.open(step/"generated.png") as b, Image.open(step/"native-generated.png") as c:
                self.assertEqual(a.getpixel((30,30)), b.getpixel((30,30)))
                self.assertNotEqual(a.getpixel((30,30)), c.getpixel((30,30)))
                self.assertEqual(b.getpixel((3,3)), c.getpixel((3,3)))
            record,packet,receipt,att=self.bound(run,step)
            proof=verify_native_strict_derivation(record,packet,receipt,att,step)
            self.assertEqual(proof["status"],"PASS")
            self.assertGreater(proof["changed_editable_pixels"],0)
            self.assertEqual(receipt["result_sha256"],sha256_file(step/"generated.png"))
            self.assertEqual(att["result_sha256"],sha256_file(step/"native-generated.png"))
            self.assertNotEqual(att["result_sha256"],receipt["result_sha256"])
            # The true native Host identity remains UNSUBSTANTIATED in this unit fixture.
            self.assertNotEqual(att["backend"],"native_codex_chatgpt")

    def test_non_strict_legacy_generation_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            _,_,run,_,first,step=self.started(root,strict=False)
            self.assertEqual(first["state"],"QA_PENDING")
            self.assertFalse((step/"native-generated.png").exists())
            self.assertFalse((step/"precision-compose-report.json").exists())
            self.assertTrue((step/"generated.png").is_file())
            self.assertNotIn("postprocess",json.loads((step/"attestation.json").read_text()))

    def test_misaligned_real_style_candidate_blocks_and_keeps_raw(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            _,_,run,host,first,step=self.started(root,misaligned=True)
            self.assertEqual(first["state"],"BLOCKED")
            self.assertEqual(host.actions,["imagegen_edit"])
            self.assertTrue((step/"native-generated.png").is_file())
            self.assertFalse((step/"generated.png").exists())
            self.assertFalse((step/"receipt.json").exists())
            self.assertEqual(json.loads(run.read_text())["state"],"BLOCKED")

    def test_strict_receipts_block_tampered_native_output_and_mask(self):
        for target in ("native-generated.png","generated.png","precision-compose-report.json","mask.png"):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                _,_,run,_,first,step=self.started(root)
                record,packet,receipt,att=self.bound(run,step)
                file=root/target if target=="mask.png" else step/target
                file.write_bytes(b"tampered provenance source")
                with self.assertRaises((ValidationError,OSError,ValueError)):
                    verify_native_strict_derivation(record,packet,receipt,att,step)

    def test_concordant_forged_hashes_do_not_allow_pixel_leak(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            _,_,run,_,first,step=self.started(root)
            record,packet,receipt,att=self.bound(run,step)
            result=step/"generated.png"
            with Image.open(result) as im:
                manipulated=im.copy()
            manipulated.putpixel((30,30),(5,6,7))
            manipulated.save(result)
            # Simulate all self-reported derived digests being rewritten together.
            contract=record["region_contract"]
            fresh=_proof(root,step,contract,root/"master.png",root/"mask.png")
            att["postprocess"]=fresh
            receipt["host_attestation"]=att
            receipt["result_sha256"]=fresh["result_sha256"]
            with self.assertRaisesRegex(ValidationError,"derived pixels differ"):
                verify_native_strict_derivation(record,packet,receipt,att,step)

    def test_bounded_repair_preserves_approved_master_and_audits_two_derivations(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            asset,edit,run,host,first,step=self.started(root)
            host.statuses=iter(["REPAIR_MINOR","PASS"])
            first_review=drive(asset,edit,root,run,host=host,resume=True,max_actions=1)
            self.assertEqual(first_review["state"],"REPAIR_READY")
            subsequent=drive(asset,edit,root,run,host=host,resume=True,max_actions=1)
            self.assertEqual(subsequent["state"],"QA_PENDING")
            repair_step=root/"run.json.production/0001-imagegen_edit"
            self.assertTrue((repair_step/"native-generated.png").is_file())
            self.assertTrue((repair_step/"generated.png").is_file())
            current,packet,receipt,attestation=self.bound(run,repair_step)
            self.assertEqual(packet["state"],"REPAIR_READY")
            self.assertEqual(packet["iteration"],1)
            support=[b for b in packet["input_bindings"]
                     if b["kind"]=="support_reference"]
            self.assertEqual(len(support),1)
            self.assertEqual(support[0]["sha256"],sha256_file(root/"master.png"))
            self.assertEqual(
                verify_native_strict_derivation(current,packet,receipt,attestation,repair_step)["status"],
                "PASS"
            )
            final_review=drive(asset,edit,root,run,host=host,resume=True,max_actions=1)
            self.assertEqual(final_review["state"],"ACCEPTED")
            # Even a complete fake QA must not become real Codex native evidence.
            audit=audit_run(run)
            self.assertEqual(audit["status"],"BLOCKED")
            self.assertFalse(audit["steam_approved"])
            self.assertEqual(host.actions,["imagegen_edit","visual_qa","imagegen_edit","visual_qa"])

    def test_missing_previous_receipt_blocks_repair_before_host_call(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            asset,edit,run,host,first,step=self.started(root)
            host.statuses=iter(["REPAIR_MINOR"])
            review=drive(asset,edit,root,run,host=host,resume=True,max_actions=1)
            self.assertEqual(review["state"],"REPAIR_READY")
            (step/"receipt.json").unlink()  # Synthetic fixture sabotage only.
            before=list(host.actions)
            next_step=root/"run.json.production/0001-imagegen_edit"
            result=drive(asset,edit,root,run,host=host,resume=True,max_actions=1)
            self.assertEqual(result["state"],"BLOCKED")
            self.assertEqual(host.actions,before)  # No wasted native generation.
            self.assertFalse(next_step.exists())

    def test_fake_host_can_finish_qa_but_never_pass_native_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            asset,edit,run,host,first,step=self.started(root)
            self.assertEqual(first["state"],"QA_PENDING")
            final=drive(asset,edit,root,run,host=host,resume=True,max_actions=1)
            self.assertEqual(final["state"],"ACCEPTED")
            audit=audit_run(run)
            self.assertEqual(audit["status"],"BLOCKED")
            self.assertTrue(any("native" in issue.lower()
                                for issue in audit["failures"]),audit["failures"])
            self.assertFalse(audit["steam_approved"])


    def test_conservative_region_qa_is_persisted_with_real_run_blocked(self):
        """A measured region PASS cannot erase critic uncertainty or failed art."""
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            asset,edit,run,host,first,step=self.started(root)
            self.assertEqual(first["state"],"QA_PENDING")
            original_execute=host.execute

            def conservative(packet,reviewer=False):
                value,att,transcript=original_execute(packet,reviewer=reviewer)
                if reviewer:
                    value["status"]="REPAIR_MINOR"
                    value["repair_directives"]=["Check grain detail on the actual native pixel faces."]
                    for gate in value["gates"]:
                        if gate["name"]=="visual.region_preservation":
                            gate["status"]="NOT_VERIFIABLE"
                        if gate["name"]=="identity":
                            gate["status"]="FAIL"
                return value,att,transcript

            host.execute=conservative
            final=drive(asset,edit,root,run,host=host,resume=True,max_actions=1)
            stored=json.loads(run.read_text())
            self.assertEqual(final["state"],"BLOCKED")
            self.assertEqual(final["blocker"]["reason_code"],"visual_inspection_unavailable")
            self.assertIsNotNone(stored["last_qa"])
            self.assertEqual(stored["last_qa"]["status"],"REPAIR_MINOR")
            self.assertTrue((root/"run.json.production/0001-visual_qa/qa.toml").exists())
            gates={g["name"]:g["status"] for g in stored["last_qa"]["gates"]}
            self.assertEqual(gates["visual.region_preservation"],"NOT_VERIFIABLE")
            self.assertEqual(audit_run(run)["status"],"BLOCKED")
            self.assertEqual(host.actions,["imagegen_edit","visual_qa"])

    def test_region_critic_receives_real_sha_bound_pixel_measurement(self):
        import subprocess
        from unittest.mock import patch
        from native_codex_host import NativeCodexHost
        from next_action import build_from_paths
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            asset,edit,run,host,first,step=self.started(root)
            packet=build_from_paths(asset,edit,run)
            calls=[]

            def fake_subprocess(argv,**kwargs):
                if argv[1:]==["login","status"]:
                    return subprocess.CompletedProcess(argv,0,b"Logged in using ChatGPT",b"")
                prompt=kwargs.get("input",b"").decode()
                calls.append(prompt)
                self.assertIn("DETERMINISTIC SHA-BOUND REGION MEASUREMENT",prompt)
                self.assertIn("visual.region_preservation measured_status=PASS",prompt)
                self.assertIn("outside_target_changed_fraction=0.0",prompt)
                raw,_,_=host.execute(packet,reviewer=True)
                (Path(argv[argv.index("-o")+1])).write_text(json.dumps(raw))
                return subprocess.CompletedProcess(argv,0,b'{"type":"turn.completed"}\\n',b"")

            with patch("native_codex_host.subprocess.run",side_effect=fake_subprocess):
                answer,attestation,_=NativeCodexHost("/bin/false").execute(packet,reviewer=True)
            self.assertEqual(answer["status"],"PASS")
            self.assertEqual(attestation["region_precheck"]["status"],"PASS")
            self.assertEqual(attestation["region_precheck"]["outside_target_changed_fraction"],0.0)
            self.assertEqual(len(calls),1)


if __name__=="__main__":
    unittest.main()

