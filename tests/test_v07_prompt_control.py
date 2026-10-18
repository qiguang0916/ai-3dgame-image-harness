"""v0.7 opt-in prompt intelligence: style, role conflict, host vision evidence."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))

import artifact_integrity
import compile_brief
import compile_repair
import execution_loop
import next_action
import runtime_preflight
import validate_project


def make_asset():
    return {
        "document_type": "asset_manifest", "schema_version": 1,
        "asset_id": "HERO_TEST", "primary_master": "FRONT",
        "locks":{"hard":["approved blade silhouette","exactly three fasteners",
                         "camera framing"],"soft":["neutral background"]},
        "references": [
            {"id":"FRONT", "path":"refs/front.png","state":"approved",
             "roles":["identity","geometry","camera","material","color"]},
            {"id":"SIDE", "path":"refs/side.png","state":"approved",
             "roles":["geometry","silhouette","interface"]},
        ],
        "topology":{"components":[{"id":"fastener","required":True,"count":3,
                                   "count_unit":"visible_instance",
                                   "visual_definition":"three visible fasteners",
                                   "excludes":["specular highlights"]}],
                    "relationships":[]},
    }


def make_edit():
    return {
        "document_type":"edit_request","schema_version":1,
        "asset_id":"HERO_TEST","request_id":"RIVET_SILVER",
        "operation":"local_edit",
        "target":"only three metal handle fasteners",
        "change":"Recolor only the existing three fasteners to brushed silver.",
        "execution":{"edit_target_reference_id":"FRONT"},
        "preserve":{"hard":["rivet centers","camera framing"],"soft":[]},
        "reference_bindings":[
            {"reference_id":"FRONT","roles":["identity","geometry","camera","material","color"]},
            {"reference_id":"SIDE","roles":["geometry","silhouette","interface"]},
        ],
        "reference_sufficiency":{"required_roles":["identity","geometry","camera"],
                                 "allow_provisional":False,
                                 "provisional_fields":[],
                                 "prohibited_assumptions":["hidden tang thickness"]},
    }


def write_real_input(root:Path):
    from PIL import Image
    for leaf,color in (("front",(90,80,80)),("side",(100,100,95))):
        path=root/"refs"/(leaf+".png")
        path.parent.mkdir(parents=True,exist_ok=True)
        Image.new("RGB",(48,40),color).save(path)


def intelligence(root:Path,**overrides):
    from prompt_control import reference_digest_for
    sha=reference_digest_for(root/"refs"/"front.png")
    base={
        "mode":"guided",
        "style_profile":"studio_hero_prop",
        "role_authority":{"geometry":"SIDE"},
        "observations":[{
            "reference_id":"FRONT",
            "source_sha256":sha,
            "inspected_pixels":True,
            "subject":"Same fictional game knife",
            "camera":"three-quarter fixed view",
            "composition":"single centered subject",
            "visible_features":["three round fasteners","dark hardwood handle"],
            "materials":["brushed steel","wood"],
            "palette":["cold silver","deep brown"],
            "unknowns":["hidden tang geometry not visible in this view"],
        }],
        "count_requests":[{"component_id":"fastener","count":3}],
    }
    base.update(overrides)
    return base


def documents(asset,edit):
    return [
      validate_project.LoadedDocument(Path("asset.toml"),asset),
      validate_project.LoadedDocument(Path("edit.toml"),edit)
    ]


class StyleProfileTests(unittest.TestCase):
    def test_curated_profiles_and_auto_create_vs_edit(self):
        from prompt_control import style_profiles, resolve_style_profile
        styles=style_profiles()
        self.assertGreaterEqual(len(styles),5)
        self.assertIn("studio_hero_prop",styles)
        self.assertNotIn("famous_artist",json.dumps(styles).lower())
        edit=make_edit()
        self.assertIsNone(resolve_style_profile("auto",edit))
        creation=deepcopy(edit)
        creation["operation"]="create"
        creation["art_direction"]={"purpose":"hero_prop_reference"}
        self.assertEqual("studio_hero_prop",resolve_style_profile("auto",creation)["id"])

    def test_opt_in_style_never_changes_approved_master_requirements(self):
        from prompt_control import format_prompt_intelligence
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            edit=make_edit();edit["prompt_intelligence"]=intelligence(root)
            validate_project.cross_validate(documents(make_asset(),edit))
            enriched=compile_brief.compile_brief(make_asset(),edit)
            bare=compile_brief.compile_brief(make_asset(),make_edit())
            self.assertIn("STYLE GUIDANCE",enriched)
            self.assertIn("brushed steel",enriched)
            self.assertIn("geometry: SIDE",enriched)
            self.assertIn("three round fasteners",enriched)
            self.assertIn("hidden tang geometry",enriched)
            self.assertIn("Do not override HARD PRESERVE",enriched)
            self.assertIn("approved blade silhouette",enriched)
            self.assertNotIn("STYLE GUIDANCE",bare)
            self.assertIsInstance(format_prompt_intelligence(make_asset(),edit),str)


class ConflictTests(unittest.TestCase):
    def test_overlapping_role_requires_authoritative_reference(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            edit=make_edit()
            config=intelligence(root)
            config["role_authority"]={}
            edit["prompt_intelligence"]=config
            with self.assertRaisesRegex(validate_project.ValidationError,"ambiguous geometry"):
                validate_project.cross_validate(documents(make_asset(),edit))

    def test_authority_must_be_selected_for_same_role(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            edit=make_edit()
            edit["prompt_intelligence"]=intelligence(root,role_authority={"geometry":"NOT_SELECTED"})
            with self.assertRaises(validate_project.ValidationError):
                validate_project.cross_validate(documents(make_asset(),edit))

    def test_wrong_topology_count_is_a_hard_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            edit=make_edit()
            edit["prompt_intelligence"]=intelligence(root,count_requests=[
                {"component_id":"fastener","count":4}
            ])
            with self.assertRaisesRegex(validate_project.ValidationError,"count conflict"):
                validate_project.cross_validate(documents(make_asset(),edit))

    def test_camera_change_conflicts_with_hard_lock(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            edit=make_edit()
            edit["prompt_intelligence"]=intelligence(root,camera_change=True)
            with self.assertRaisesRegex(validate_project.ValidationError,"camera"):
                validate_project.cross_validate(documents(make_asset(),edit))

    def test_authorized_material_edit_is_not_falsely_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            edit=make_edit()
            edit["prompt_intelligence"]=intelligence(root)
            validate_project.cross_validate(documents(make_asset(),edit))

    def test_wrong_digest_schema_and_unverified_observation_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            for override in ({"source_sha256":"deadbeef"},
                             {"inspected_pixels":False},
                             {"materials":[""]}):
                edit=make_edit()
                bad=intelligence(root)
                bad["observations"][0].update(override)
                edit["prompt_intelligence"]=bad
                with self.assertRaises(validate_project.ValidationError):
                    validate_project.validate_document(edit,Path("edit.toml"))

    def test_binding_unknown_observation_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            edit=make_edit();conf=intelligence(root)
            conf["observations"][0]["reference_id"]="UNAPPROVED"
            edit["prompt_intelligence"]=conf
            with self.assertRaises(validate_project.ValidationError):
                validate_project.cross_validate(documents(make_asset(),edit))


class AuditableEvidenceTests(unittest.TestCase):
    def test_live_input_digest_matches_visual_observation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            asset=make_asset();edit=make_edit()
            edit["prompt_intelligence"]=intelligence(root)
            check=runtime_preflight.run_preflight(asset,edit,root)
            self.assertEqual("PASS",check["status"])
            self.assertEqual("VERIFIED_DIGEST_ONLY",check["prompt_intelligence"]["status"])
            from PIL import Image
            Image.new("RGB",(48,40),"blue").save(root/"refs"/"front.png")
            check=runtime_preflight.run_preflight(asset,edit,root)
            self.assertEqual("BLOCKED",check["status"])
            self.assertEqual("reference_digest_mismatch",check["reason_code"])

    def test_dry_run_never_claims_pixel_observation_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            edit=make_edit();edit["prompt_intelligence"]=intelligence(root)
            result=runtime_preflight.run_preflight(make_asset(),edit,root,dry_run=True)
            self.assertEqual("PASS",result["status"])
            self.assertEqual("NOT_VERIFIED_DRY_RUN",result["prompt_intelligence"]["status"])

    def test_reference_review_action_includes_real_sha_and_inspection_questions(self):
        from prompt_control import reference_review_packet
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            data=reference_review_packet(make_asset(),make_edit(),root)
            self.assertEqual("host_vision_reference_review",data["action"])
            self.assertEqual(2,len(data["references"]))
            self.assertEqual(64,len(data["references"][0]["sha256"]))
            self.assertIn("camera",data["references"][0]["inspection_fields"])
            self.assertEqual("no local model invoked",data["execution"])
            self.assertGreaterEqual(len(data["references"][0]["color_swatch_hints"]),1)
            self.assertTrue(data["references"][0]["color_swatch_hints"][0]["hex"].startswith("#"))
            self.assertIn("NOT authoritative",data["references"][0]["color_note"])

    def test_imagegen_packet_binds_prompt_intelligence_without_regression(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            asset=make_asset();edit=make_edit()
            edit["prompt_intelligence"]=intelligence(root)
            validate_project.cross_validate(documents(asset,edit))
            run=execution_loop.init_run(asset,edit)
            packet=next_action.build_action_packet(asset,edit,run)
            self.assertEqual("imagegen_edit",packet["action"])
            self.assertEqual("host_native_imagegen",packet["backend"])
            self.assertEqual("none",packet["fallback_policy"])
            self.assertIn("prompt_intelligence",packet)
            self.assertIn("geometry: SIDE",packet["prompt"])

    def test_repair_keeps_tiny_delta_without_reapplying_full_style(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_real_input(root)
            asset=make_asset();edit=make_edit()
            edit["prompt_intelligence"]=intelligence(root)
            qa={"status":"REPAIR_MINOR","gates":[
                {"name":"material","status":"FAIL"},
                {"name":"geometry","status":"PASS"}],
                "repair_directives":["Fix only fastener brushed-silver finish."]}
            prompt=compile_repair.compile_repair_brief(asset,edit,qa)
            self.assertIn("Fix only fastener",prompt)
            self.assertNotIn("STYLE GUIDANCE",prompt)
            self.assertIn("SIDE",prompt)


if __name__=="__main__":
    unittest.main()

class RequestBindingTests(unittest.TestCase):
    def test_auditable_run_rejects_edit_changed_after_preflight(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            write_real_input(root)
            asset=make_asset()
            edit=make_edit()
            edit["prompt_intelligence"]=intelligence(root)
            from unittest.mock import patch
            # Use JSON->TOML paths without adding new third-party writer dependencies.
            # v0.7 real runs accept the existing TOML schema and bind its parsed content.
            asset_path=root/"asset.toml"
            edit_path=root/"edit.toml"
            asset_path.write_text(
                'document_type="asset_manifest"\n'
                'schema_version=1\nasset_id="HERO_TEST"\nprimary_master="FRONT"\n'
                '[locks]\nhard=["camera framing"]\nsoft=[]\n'
                '[[references]]\nid="FRONT"\npath="refs/front.png"\n'
                'state="approved"\nroles=["identity","geometry","camera"]\n'
            )
            edit_path.write_text(
                'document_type="edit_request"\n'
                'schema_version=1\nasset_id="HERO_TEST"\nrequest_id="E"\n'
                'operation="local_edit"\ntarget="fasteners"\nchange="recolor fasteners"\n'
                '[execution]\nedit_target_reference_id="FRONT"\n'
                '[preserve]\nhard=["camera framing"]\nsoft=[]\n'
                '[[reference_bindings]]\nreference_id="FRONT"\n'
                'roles=["identity","geometry","camera"]\n'
            )
            run=execution_loop.init_from_paths(asset_path,edit_path,workspace_root=root)
            self.assertEqual("READY",run["state"])
            path=root/"run.json"
            execution_loop.save_run(path,run)
            edit_path.write_text(edit_path.read_text().replace(
                'change="recolor fasteners"',
                'change="silently reframe entire scene"'
            ))
            with self.assertRaisesRegex(validate_project.ValidationError, "changed after run initialization"):
                next_action.build_from_paths(asset_path,edit_path,path)
