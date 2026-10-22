"""Synthetic-only v0.13 material finishing tests; NO test sample is real ImageGen."""
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

from artifact_integrity import sha256_file
from production_autopilot import drive
from production_audit import audit_run
from native_strict_provenance import _proof,verify_native_strict_derivation
from material_finish import finish_material, verify_finished_material, PRESET
from validate_project import ValidationError
import test_v06_integration as fixture_inputs
import test_v13_native_strict_provenance as stub_inputs


class EnamelMaterialTests(unittest.TestCase):
    def fixture(self,root,*,invalid=None,no_red=False,rgba_master=False):
        from PIL import Image,ImageDraw
        asset,edit,run,_=fixture_inputs.V06IntegrationTests()._init(root)
        run.unlink()
        if rgba_master:
            with Image.open(root/"master.png") as source:
                rgba=source.convert("RGBA")
            rgba.save(root/"master.png")
        original=edit.read_text()
        mask=root/"mask.png"
        binary=Image.new("L",(40,40),255)
        ImageDraw.Draw(binary).rectangle((0,0,9,9),fill=0)
        binary.save(mask)
        strict=('\n[region_contract.strict_mask]\n'
                'path="mask.png"\n'
                f'sha256="{sha256_file(mask)}"\n'
                f'reference_sha256="{sha256_file(root/"master.png")}"\n'
                '\n[[region_contract.required_edit_points]]\n'
                'id="face_center"\nuv=[0.12,0.12]\n')
        spec=('\n[material_finish]\n'
              f'preset="{PRESET}"\n'
              '[[material_finish.faces]]\n'
              'id="control_face"\n'
              'center_uv=[0.12,0.12]\n'
              'radius_uv=[0.10,0.10]\n')
        if invalid=="bad_center":
            spec=spec.replace("center_uv=[0.12,0.12]","center_uv=[0.75,0.75]")
        if invalid=="overlap":
            spec+='[[material_finish.faces]]\nid="overlapping_face"\ncenter_uv=[0.12,0.12]\nradius_uv=[0.10,0.10]\n'
        edit.write_text(original+strict+spec)
        img=Image.new("RGB",(40,40),(255,255,255))
        if not no_red:
            pix=img.load()
            for y in range(40):
                for x in range(40):
                    rad=((x-4.8)/4.0)**2+((y-4.8)/4.0)**2
                    if rad<=1:
                        r=95+(23 if x<4.8 and y<4.8 else (-14 if x>=4.8 and y<4.8 else 8))
                        pix[x,y]=(r,5,13)
            pix[3,2]=(198,109,115)
            pix[4,2]=(190,99,110)
        ImageDraw.Draw(img).rectangle((28,28,35,35),fill=(8,8,8))
        buf=io.BytesIO();img.save(buf,format="PNG")
        host=stub_inputs.StrictStubHost(buf.getvalue())
        return asset,edit,run,host

    def start(self,root,*,invalid=None,no_red=False,rgba_master=False):
        a,e,r,host=self.fixture(root,invalid=invalid,no_red=no_red,
                                rgba_master=rgba_master)
        outcome=drive(a,e,root,r,host=host,max_actions=1)
        step=root/"run.json.production/0000-imagegen_edit"
        return a,e,r,host,outcome,step

    def binding(self,run,step):
        state=json.loads(run.read_text())
        packet=json.loads((step/"packet.json").read_text())
        receipt=json.loads((step/"receipt.json").read_text())
        att=json.loads((step/"attestation.json").read_text())
        return state,packet,receipt,att

    def test_real_native_derivation_layers_remain_distinct_synthetic(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a,e,run,host,first,step=self.start(root)
            self.assertEqual(first["state"],"QA_PENDING")
            self.assertEqual(host.actions,["imagegen_edit"])
            for file in ("native-generated.png","material-finished-native.png",
                         "material-finish-report.json","precision-compose-report.json",
                         "generated.png","receipt.json","packet.json","events.jsonl"):
                self.assertTrue((step/file).is_file(),file)
            source=step/"native-generated.png"
            retouched=step/"material-finished-native.png"
            delivered=step/"generated.png"
            self.assertNotEqual(sha256_file(source),sha256_file(retouched))
            self.assertNotEqual(sha256_file(delivered),sha256_file(source))
            state,packet,receipt,att=self.binding(run,step)
            proof=verify_native_strict_derivation(state,packet,receipt,att,step)
            self.assertEqual(proof["status"],"PASS")
            self.assertEqual(proof["material_finish_replay"]["status"],
                             "PASS_REPLAYED_NATIVE_MATERIAL_FINISH")
            self.assertEqual(receipt["result_sha256"],sha256_file(delivered))
            self.assertEqual(att["result_sha256"],sha256_file(source))
            self.assertEqual(att["postprocess"]["material_finish"]["human_art_approved"],False)
            from PIL import Image
            with Image.open(root/"master.png") as src,Image.open(delivered) as dst:
                self.assertEqual(src.getpixel((30,30)),dst.getpixel((30,30)))

    def test_output_can_be_independently_regenerated_byte_identical(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,edit,run,_,first,step=self.start(root)
            self.assertEqual(first["state"],"QA_PENDING")
            from validate_project import load_document
            request=load_document(edit).data
            a=finish_material(root,root/"master.png",step/"native-generated.png",
                root/"mask.png",request["region_contract"],request["material_finish"],
                root/"repeat-material.png",root/"repeat-material.json")
            self.assertEqual(a["status"],"CANDIDATE_NEEDS_VISUAL_REVIEW")
            self.assertEqual(sha256_file(root/"repeat-material.png"),
                             sha256_file(step/"material-finished-native.png"))
            verified=verify_finished_material(root,root/"master.png",step/"native-generated.png",
                root/"mask.png",request["region_contract"],request["material_finish"],
                root/"repeat-material.png",root/"repeat-material.json")
            self.assertEqual(verified["status"],"PASS_REPLAYED_NATIVE_MATERIAL_FINISH")
            self.assertEqual(verified["protected_pixel_mismatches"],0)

    def test_finish_and_report_tamper_rejected_even_if_attestation_rewritten(self):
        from PIL import Image
        for target in ("material-finished-native.png","material-finish-report.json",
                       "generated.png","native-generated.png"):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as d:
                root=Path(d)
                _,_,run,_,first,step=self.start(root)
                state,packet,receipt,att=self.binding(run,step)
                artifact=step/target
                if target.endswith(".png"):
                    with Image.open(artifact) as im:
                        manipulated=im.copy()
                    manipulated.putpixel((4,4),(255,255,255))
                    manipulated.save(artifact)
                else:
                    data=json.loads(artifact.read_text())
                    data["protected_pixel_mismatches"]=0
                    data["human_art_approved"]=True
                    artifact.write_text(json.dumps(data))
                with self.assertRaises((ValidationError,OSError,ValueError)):
                    verify_native_strict_derivation(state,packet,receipt,att,step)

    def test_forged_derived_hash_must_still_match_replayed_pixels(self):
        from PIL import Image
        from validate_project import load_document
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,edit,run,_,first,step=self.start(root)
            record,packet,receipt,att=self.binding(run,step)
            candidate=step/"material-finished-native.png"
            with Image.open(candidate) as im:
                new=im.copy()
            new.putpixel((4,4),(255,0,0))
            new.save(candidate)
            contract=record["region_contract"]
            recipe=load_document(edit).data["material_finish"]
            # Simulate forged success hashes without actually re-rendering pixels.
            att["postprocess"]=_proof(root,step,contract,root/"master.png",
                                      root/"mask.png",recipe)
            receipt["host_attestation"]=att
            with self.assertRaisesRegex(ValidationError,"deterministic replay"):
                verify_native_strict_derivation(record,packet,receipt,att,step)

    def test_bad_face_geometry_rejected_before_any_model_action(self):
        for kind in ("bad_center","overlap"):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
                root=Path(d)
                _,_,run,host,first,step=self.start(root,invalid=kind)
                self.assertEqual(first["state"],"BLOCKED")
                self.assertEqual(host.actions,[])
                self.assertFalse(step.exists())
                self.assertEqual(json.loads(run.read_text())["iteration"],0)

    def test_rgba_material_source_blocks_before_call(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,run,host,first,step=self.start(root,rgba_master=True)
            self.assertEqual(first["state"],"BLOCKED")
            self.assertEqual(host.actions,[])
            self.assertFalse(step.exists())

    def test_nonred_native_input_blocks_without_fake_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,run,host,first,step=self.start(root,no_red=True)
            self.assertEqual(first["state"],"BLOCKED")
            self.assertEqual(host.actions,["imagegen_edit"])
            self.assertTrue((step/"native-generated.png").is_file())
            self.assertFalse((step/"receipt.json").exists())
            self.assertFalse((step/"generated.png").exists())

    def test_synthetic_host_cannot_pass_formal_native_audit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a,e,run,host,first,step=self.start(root)
            self.assertEqual(first["state"],"QA_PENDING")
            final=drive(a,e,root,run,host=host,resume=True,max_actions=1)
            self.assertEqual(final["state"],"ACCEPTED")
            result=audit_run(run)
            self.assertEqual(result["status"],"BLOCKED")
            self.assertFalse(result["steam_approved"])
            self.assertTrue(any("native" in item.lower() for item in result["failures"]))


if __name__=="__main__":
    unittest.main()

