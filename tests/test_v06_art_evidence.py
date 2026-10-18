"""v0.6 art direction, reference evidence and technical game-asset delivery."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import compile_brief, runtime_preflight, topology_contract, validate_project


def asset():
    return {
        "document_type":"asset_manifest","schema_version":1,"asset_id":"A",
        "primary_master":"M","locks":{"hard":["identity"],"soft":[]},
        "references":[{"id":"M","path":"master.png","state":"approved",
                       "roles":["identity","geometry","camera","material"]}],
    }


def edit():
    return {
        "document_type":"edit_request","schema_version":1,"asset_id":"A",
        "request_id":"E","operation":"local_edit","target":"metal knob","change":"silver steel",
        "execution":{"edit_target_reference_id":"M"},
        "preserve":{"hard":["identity"],"soft":[]},
        "reference_bindings":[{"reference_id":"M","roles":["identity","geometry","camera","material"]}],
        "reference_sufficiency":{"required_roles":["identity","geometry","camera"],"allow_provisional":False,
                                 "provisional_fields":[],"prohibited_assumptions":["hidden interiors"]},
    }


class ArtDirectionTests(unittest.TestCase):
    def test_explicit_art_direction_is_valid_and_reaches_prompt(self):
        e=edit()
        e["art_direction"]={
            "purpose":"hero_prop_reference",
            "style_family":"photoreal studio prop",
            "camera":"three quarter",
            "lighting":"softbox, no blown highlights",
            "palette":["dark neutral","warm brown","cold steel"],
            "material_notes":["steel roughness looks realistic"],
            "game_scale_read":"knife tip and three rivets distinct at 1080p",
            "must_match":True,
        }
        validate_project.validate_document(e,Path("edit.toml"))
        prompt=compile_brief.compile_brief(asset(),e)
        self.assertIn("ART DIRECTION",prompt)
        self.assertIn("1080p",prompt)
        self.assertIn("art_direction.consistency",topology_contract.expected_hard_gates(asset(),e))

    def test_reference_visual_evidence_required_is_real_gate(self):
        e=edit()
        e["reference_evidence"]={"required":True,"observations":[]}
        pre=runtime_preflight.run_preflight(asset(),e,Path("."),dry_run=True)
        self.assertEqual("BLOCKED",pre["status"])
        e["reference_evidence"]["observations"]=[{
            "reference_id":"M",
            "roles":["identity","geometry","camera"],
            "visible_facts":["The front, side silhouette and camera angle are visually readable."],
            "unknowns":["The concealed rear-facing face is not shown."],
        }]
        validate_project.validate_document(e,Path("e.toml"))
        pre=runtime_preflight.run_preflight(asset(),e,Path("."),dry_run=True)
        self.assertEqual("PASS",pre["status"])
        self.assertEqual("sufficient",pre["reference_sufficiency"]["status"])
        self.assertIn("concealed rear",compile_brief.compile_brief(asset(),e))

    def test_made_up_reference_role_rejected(self):
        e=edit()
        e["reference_evidence"]={"required":True,"observations":[{
            "reference_id":"M","roles":["interface"],
            "visible_facts":["Unseen internal mechanism."],"unknowns":[],
        }]}
        with self.assertRaises(validate_project.ValidationError):
            validate_project.cross_validate([
                validate_project.LoadedDocument(Path("asset.toml"),asset()),
                validate_project.LoadedDocument(Path("edit.toml"),e),
            ])


class TechnicalOutputTests(unittest.TestCase):
    def test_png_output_profile_measures_dimensions_and_alpha(self):
        from PIL import Image
        from asset_report import inspect_output
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"out.png"
            Image.new("RGBA",(64,32),(80,90,100,0)).save(p)
            cfg={"expected_size":"64x32","require_transparency":True}
            self.assertEqual("PASS",inspect_output(p,cfg)["status"])
            self.assertEqual("FAIL",inspect_output(p,{"expected_size":"128x32"})["status"])
            self.assertEqual("FAIL",inspect_output(p,{"require_transparency":False})["status"])
            im=Image.new("RGB",(64,32),"white");im.save(p)
            self.assertEqual("FAIL",inspect_output(p,{"require_transparency":True})["status"])

    def test_output_specs_add_hard_gate_and_reject_invalid(self):
        e=edit()
        e["output"]={"expected_size":"1536x1024","require_transparency":False,
                     "purpose":"game_asset_reference"}
        validate_project.validate_document(e,Path("edit.toml"))
        self.assertIn("image.technical_output",topology_contract.expected_hard_gates(asset(),e))
        e["output"]["expected_size"]="8K"
        with self.assertRaises(validate_project.ValidationError):
            validate_project.validate_document(e,Path("edit.toml"))


if __name__=="__main__":
    unittest.main()
