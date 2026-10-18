"""Commercial readiness gates: no synthetic fixture may be declared Steam-approved."""
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))

class CommercialReadinessTests(unittest.TestCase):
    def fake_glb(self, p, names):
        data=json.dumps({"asset":{"version":"2.0"},
            "nodes":[{"name":x,"mesh":i} for i,x in enumerate(names)],
            "meshes":[{"name":x,"primitives":[{"attributes":{}}]} for x in names],
        },separators=(",",":")).encode()
        data+=b" "*((-len(data))%4)
        p.write_bytes(struct.pack("<4sII",b"glTF",2,20+len(data))+
                struct.pack("<I4s",len(data),b"JSON")+data)

    def names(self):
        return ["KNIFE_001_BLADE","KNIFE_001_GUARD","KNIFE_001_HANDLE_L",
                "KNIFE_001_HANDLE_R","KNIFE_001_PIN_01","KNIFE_001_PIN_02",
                "KNIFE_001_PIN_03"]

    def test_glb_required_names_and_three_pins(self):
        from commercial_art_gate import inspect_glb
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"knife.glb"
            self.fake_glb(p,self.names())
            result=inspect_glb(p,{"KNIFE_001_PIN_":3,"KNIFE_001_BLADE":1,
                                   "KNIFE_001_HANDLE_L":1,"KNIFE_001_HANDLE_R":1})
            self.assertEqual("PASS",result["status"])
            self.fake_glb(p,self.names()[:-1])
            result=inspect_glb(p,{"KNIFE_001_PIN_":3})
            self.assertEqual("FAIL",result["status"])

    def test_malformed_glb_and_broken_chunk_block(self):
        from commercial_art_gate import inspect_glb
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"wrong.glb"
            p.write_bytes(b"not a glb")
            self.assertEqual("FAIL",inspect_glb(p,{"KNIFE_001_PIN_":3})["status"])

    def test_canonical_views_reject_empty_or_tampered_pixels(self):
        from commercial_art_gate import verify_canonical_views
        from artifact_integrity import sha256_file
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/"knife.glb";self.fake_glb(source,self.names())
            manifest={"schema_version":1,"source_glb":str(source),
                "source_sha256":sha256_file(source),
                "views":[]}
            for n in ("BROAD_A","BROAD_B","SPINE","QUARTER"):
                p=root/(n+".png")
                Image.new("RGB",(96,72),"gray").save(p)
                manifest["views"].append({"name":n,"image":p.name,
                                          "sha256":sha256_file(p),"width":96,"height":72})
            mp=root/"manifest.json";mp.write_text(json.dumps(manifest))
            result=verify_canonical_views(mp)
            self.assertEqual("FAIL",result["status"])
            self.assertTrue(any("empty" in x.lower() or "foreground" in x.lower()
                                for x in result["failures"]))
            # A changed file must never pass even when old manifest SHA remains.
            Image.new("RGB",(96,72),"white").save(root/"BROAD_A.png")
            result=verify_canonical_views(mp)
            self.assertTrue(any("digest" in x.lower() for x in result["failures"]))

    def test_unreviewed_model_cannot_be_steam_ready(self):
        from commercial_art_gate import evaluate_package
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/"knife.glb";self.fake_glb(p,self.names())
            from artifact_integrity import sha256_file
            package={"schema_version":1,"asset_id":"KNIFE_001",
                     "asset_kind":"ingame_3d_model",
                     "artifact":{"path":"knife.glb","sha256":sha256_file(p)},
                     "source":{"origin":"user_owned",
                               "rights_basis":"original digital game prop"}}
            report=evaluate_package(package,root)
            self.assertEqual("BLOCKED",report["status"])
            self.assertFalse(report["ready_for_release"])
            self.assertIn("rights_review",str(report["blockers"]))
            self.assertIn("unity_integration",str(report["blockers"]))

    def test_steam_screenshot_must_be_real_game_capture(self):
        from commercial_art_gate import evaluate_package
        from artifact_integrity import sha256_file
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);im=root/"screenshot.png"
            Image.new("RGB",(1920,1080),"gray").save(im)
            pkg={"schema_version":1,"asset_id":"TEST_SCREENSHOT",
                 "asset_kind":"steam_gameplay_screenshot",
                 "artifact":{"path":"screenshot.png","sha256":sha256_file(im)},
                 "source":{"origin":"openai_imagegen","rights_basis":"AI-generated concept"},
                 "capture_origin":"generated_concept"}
            report=evaluate_package(pkg,root)
            self.assertEqual("BLOCKED",report["status"])
            self.assertIn("real Unity Player gameplay",str(report["blockers"]))

    def test_store_capsule_dimensions_checked(self):
        from commercial_art_gate import evaluate_package
        from artifact_integrity import sha256_file
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);im=root/"capsule.png"
            Image.new("RGB",(960,430),"white").save(im)
            pkg={"schema_version":1,"asset_id":"CAPSULE",
                 "asset_kind":"steam_store_capsule",
                 "store_slot":"header",
                 "artifact":{"path":"capsule.png","sha256":sha256_file(im)},
                 "source":{"origin":"user_owned","rights_basis":"original"}}
            report=evaluate_package(pkg,root)
            self.assertEqual("BLOCKED",report["status"])
            self.assertIn("920x430",str(report["blockers"]))

    def test_forged_unity_gate_without_actual_player_capture_rejected(self):
        from commercial_art_gate import evaluate_package
        from artifact_integrity import sha256_file
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            knife=root/"knife.glb";self.fake_glb(knife,self.names())
            p=root/"evidence.txt";p.write_text("A fake claim of Unity success")
            proof={"status":"PASS","reviewer":"fixture",
                   "path":"evidence.txt","sha256":sha256_file(p)}
            package={"schema_version":1,"asset_id":"KNIFE_001",
                "asset_kind":"ingame_3d_model",
                "artifact":{"path":"knife.glb","sha256":sha256_file(knife)},
                "source":{"origin":"user_owned","rights_basis":"synthetic fixture",
                          "rights_review":proof},
                "visual_qa":proof,
                "unity_integration":proof,
                "expected_components":{"KNIFE_001_PIN_":3},
            }
            report=evaluate_package(package,root)
            self.assertEqual("BLOCKED",report["status"])
            self.assertIn("Unity Player screenshot",str(report["blockers"]))
            self.assertIn("build_id",str(report["blockers"]))

    def test_reference_only_is_not_shipping_asset(self):
        from commercial_art_gate import evaluate_package
        from artifact_integrity import sha256_file
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);im=root/"concept.png"
            Image.new("RGB",(512,512),"white").save(im)
            pkg={"schema_version":1,"asset_id":"CONCEPT",
                 "asset_kind":"concept_reference",
                 "artifact":{"path":"concept.png","sha256":sha256_file(im)},
                 "source":{"origin":"user_owned","rights_basis":"original"}}
            report=evaluate_package(pkg,root)
            self.assertEqual("REFERENCE_ONLY",report["status"])
            self.assertFalse(report["ready_for_release"])

    def test_release_success_means_review_ready_not_steam_approved(self):
        from commercial_art_gate import evaluate_package
        from artifact_integrity import sha256_file
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            picture=root/"capsule.png";Image.new("RGB",(920,430),"white").save(picture)
            proof=root/"rights.txt";proof.write_text("Synthetic QA test provenance")
            vis=root/"visual.txt";vis.write_text("Synthetic QA test visual approval")
            store=root/"store.txt";store.write_text("Synthetic QA test copyright-safe logo")
            def proof_record(p):return {"status":"PASS","reviewer":"test-fixture","path":p.name,"sha256":sha256_file(p)}
            pkg={"schema_version":1,"asset_id":"CAPSULE",
                 "asset_kind":"steam_store_capsule","store_slot":"header",
                 "artifact":{"path":"capsule.png","sha256":sha256_file(picture)},
                 "source":{"origin":"user_owned","rights_basis":"original",
                           "rights_review":proof_record(proof)},
                 "visual_qa":proof_record(vis),"store_content_review":proof_record(store),
                 "store_text_policy":"game_title_or_logo_only"}
            result=evaluate_package(pkg,root)
            self.assertEqual("READY_FOR_STEAM_SUBMISSION_REVIEW",result["status"])
            self.assertTrue(result["ready_for_release"])
            self.assertFalse(result["steam_approved"])

if __name__=="__main__":
    unittest.main()
