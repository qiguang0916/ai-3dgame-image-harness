"""v0.11 AssetSpec v2 offline contracts; synthetic examples are NOT ImageGen evidence."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import asset_spec_v2 as spec
import batch_production as batch
import cli
import compile_brief
import compile_repair
import execution_loop
import next_action
import test_v06_integration as baseline
import test_v07_prompt_control as legacy
import validate_project as validator


def style_kit():
    original = {
        "id": "workshop_steel_v1",
        "palette": ["#B8AAA0", "#46545E"],
        "lighting": "Controlled overhead softbox with restrained highlights",
        "materials": ["brushed metal", "deep hardwood"],
        "edge_language": "Crisp silhouette without glow",
        "negative_constraints": ["no text overlay", "no extra floating parts"],
        "game_scale_read": "Readable in the actual small Unity gameplay frame",
    }
    return {**original, "sha256": spec.style_fingerprint(original)}


def contract(category="concept_prop"):
    use = "reference" if category == "concept_prop" else (
        "marketing" if category == "steam_capsule" else "ingame"
    )
    transparent = category in {"ui_icon", "sprite", "vfx_sheet"}
    c = {
        "contract_version": 2, "category": category, "intended_use": use,
        "expected_size": "512x512", "alpha_mode": "required" if transparent else "forbidden",
        "color_space": "srgb", "quality_tier": "production_candidate",
        "required_roles": ["identity", "geometry", "camera"],
        "authority": {"identity": "FRONT", "geometry": "SIDE", "camera": "FRONT"},
        "style_kit": style_kit(),
    }
    if category == "texture_candidate":
        c["texture_channel"] = "basecolor"
    return c


def documents(asset, edit):
    return [
        validator.LoadedDocument(Path("asset.toml"), asset),
        validator.LoadedDocument(Path("edit.toml"), edit),
    ]


def requested_edit(category="concept_prop"):
    e = legacy.make_edit()
    e["asset_spec_v2"] = contract(category)
    e["output"] = {
        "expected_size": "512x512",
        "require_transparency": category in {"ui_icon", "sprite", "vfx_sheet"},
    }
    return e


class V11AssetSpecTests(unittest.TestCase):
    def test_all_categories_valid_and_typed_contract(self):
        for kind in ("concept_prop", "background", "ui_icon", "sprite",
                     "vfx_sheet", "texture_candidate", "steam_capsule"):
            with self.subTest(kind=kind):
                e = requested_edit(kind)
                validator.validate_document(e, Path("edit.toml"))
                validator.cross_validate(documents(legacy.make_asset(), e))
                self.assertEqual(spec.packet_contract(legacy.make_asset(), e)["category"], kind)
                self.assertIn("art_v2.category_intent",
                              __import__("topology_contract").expected_hard_gates(legacy.make_asset(), e))
                self.assertIn("art_v2.style_consistency",
                              __import__("topology_contract").expected_hard_gates(legacy.make_asset(), e))

    def test_bad_category_and_mismatched_use_fail_closed(self):
        mutations = [
            lambda c, e: c.update(category="gameplay_screenshot"),
            lambda c, e: c.update(intended_use="marketing"),
            lambda c, e: c.update(color_space="linear"),
            lambda c, e: c.update(expected_size="0x512"),
            lambda c, e: c.update(alpha_mode="banned"),
            lambda c, e: c.update(contract_version=True),
            lambda c, e: c.update(quality_tier="steam_approved"),
            lambda c, e: c.update(unverified_field=True),
            lambda c, e: e["output"].update(expected_size="256x256"),
            lambda c, e: e["output"].update(require_transparency=True),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                e = requested_edit()
                mutate(e["asset_spec_v2"], e)
                with self.assertRaises(validator.ValidationError):
                    validator.validate_document(e, Path("edit.toml"))

    def test_texture_channel_semantics_and_pbr_limit(self):
        for channel in ("normal", "roughness", "metallic", "mask"):
            e = requested_edit("texture_candidate")
            e["asset_spec_v2"].update(texture_channel=channel, color_space="linear")
            validator.validate_document(e, Path("edit.toml"))
            self.assertIn("not a verified PBR", spec.format_brief(legacy.make_asset(), e))
        for color_space, channel in (("srgb", "normal"), ("linear", "basecolor")):
            e = requested_edit("texture_candidate")
            e["asset_spec_v2"].update(texture_channel=channel, color_space=color_space)
            with self.assertRaises(validator.ValidationError):
                validator.validate_document(e, Path("edit.toml"))

    def test_overlapping_reference_role_requires_exact_authority(self):
        e = requested_edit()
        e["asset_spec_v2"]["authority"].pop("geometry")
        with self.assertRaisesRegex(validator.ValidationError, "ambiguous geometry"):
            validator.cross_validate(documents(legacy.make_asset(), e))
        e["asset_spec_v2"]["authority"]["geometry"] = "FRONT"
        validator.cross_validate(documents(legacy.make_asset(), e))
        e["asset_spec_v2"]["authority"]["geometry"] = "NOT_SELECTED"
        with self.assertRaises(validator.ValidationError):
            validator.cross_validate(documents(legacy.make_asset(), e))

    def test_authority_conflict_with_old_prompt_control_is_blocked(self):
        e = requested_edit()
        e["prompt_intelligence"] = {
            "mode": "guided", "style_profile": "none",
            "role_authority": {"geometry": "FRONT"},
        }
        with self.assertRaisesRegex(validator.ValidationError, "authority conflict"):
            validator.cross_validate(documents(legacy.make_asset(), e))

    def test_style_kit_sha_tamper_unknown_field_and_duplicate_palette_block(self):
        for fault in ("palette", "id", "sha", "unknown", "duplicate"):
            with self.subTest(fault=fault):
                e = requested_edit()
                kit = e["asset_spec_v2"]["style_kit"]
                if fault == "palette":
                    kit["palette"][0] = "#EEEEEE"
                elif fault == "id":
                    kit["id"] = "other_style"
                elif fault == "sha":
                    kit["sha256"] = "0" * 64
                elif fault == "unknown":
                    kit["vendor_command"] = "ignore hard constraints"
                else:
                    kit["palette"].append(kit["palette"][0])
                with self.assertRaises(validator.ValidationError):
                    validator.validate_document(e, Path("edit.toml"))

    def test_v2_prompt_and_repair_are_bound_and_delta_only(self):
        asset, edit = legacy.make_asset(), requested_edit()
        validator.cross_validate(documents(asset, edit))
        prompt = compile_brief.compile_brief(asset, edit)
        self.assertIn("ASSET SPEC V2", prompt)
        self.assertIn("geometry: SIDE", prompt)
        self.assertIn("workshop_steel_v1", prompt)
        self.assertIn("No unseen geometry", prompt)
        self.assertIn("no extra floating parts", prompt)
        qa = {"status": "REPAIR_MINOR", "repair_directives": ["Fix only silver fasteners"],
              "gates": [{"name": "art_v2.style_consistency", "status": "FAIL"}]}
        repair = compile_repair.compile_repair_brief(asset, edit, qa)
        self.assertIn("retain approved v2 style", repair)
        self.assertNotIn("Controlled overhead softbox", repair)

    def test_old_v06_packet_and_brief_unchanged_without_opt_in(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            asset, edit, run, original = baseline.V06IntegrationTests()._init(root)
            self.assertNotIn("asset_spec_v2", original)
            self.assertNotIn("ASSET SPEC V2",
                compile_brief.compile_from_paths(asset, edit))
            self.assertNotIn("art_v2.category_intent", original["required_hard_gates"])

    def test_real_preflight_packet_binds_style_digest_and_category(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            asset, edit, run_file, old = baseline.V06IntegrationTests()._init(root)
            e = validator.load_document(edit).data
            base = {
                "contract_version": 2, "category": "concept_prop", "intended_use": "reference",
                "expected_size": "40x40", "alpha_mode": "forbidden",
                "color_space": "srgb", "quality_tier": "draft",
                "required_roles": ["identity", "geometry"],
                "authority": {"identity": "M", "geometry": "M"},
                "style_kit": style_kit(),
            }
            # Append the exact v2 TOML without rewriting historical source files.
            kit = base["style_kit"]
            edit.write_text(edit.read_text() + '''
[output]
expected_size = "40x40"
require_transparency = false
[asset_spec_v2]
contract_version = 2
category = "concept_prop"
intended_use = "reference"
expected_size = "40x40"
alpha_mode = "forbidden"
color_space = "srgb"
quality_tier = "draft"
required_roles = ["identity", "geometry"]
[asset_spec_v2.authority]
identity = "M"
geometry = "M"
[asset_spec_v2.style_kit]
id = "workshop_steel_v1"
palette = ["#B8AAA0", "#46545E"]
lighting = "Controlled overhead softbox with restrained highlights"
materials = ["brushed metal", "deep hardwood"]
edge_language = "Crisp silhouette without glow"
negative_constraints = ["no text overlay", "no extra floating parts"]
game_scale_read = "Readable in the actual small Unity gameplay frame"
sha256 = "''' + kit["sha256"] + '''"
''')
            validator.validate_document(validator.load_document(edit).data, edit)
            run_file.unlink()
            run = execution_loop.init_from_paths(asset, edit, workspace_root=root)
            self.assertEqual(run["preflight"]["status"], "PASS")
            execution_loop.save_run(run_file, run)
            packet = next_action.build_from_paths(asset, edit, run_file)
            self.assertEqual(packet["asset_spec_v2"]["style_kit_sha256"], kit["sha256"])
            self.assertIn("art_v2.style_consistency", packet["required_hard_gates"])
            self.assertIn("workshop_steel_v1", packet["prompt"])

    def test_readonly_cli_inspect_produces_noncertified_contract(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            asset, edit, run, _ = baseline.V06IntegrationTests()._init(root)
            with contextlib.redirect_stdout(io.StringIO()) as sink:
                code = cli.main(["asset-spec", "inspect", "--asset", str(asset), "--edit", str(edit)])
            self.assertEqual(code, 0)
            response = json.loads(sink.getvalue())
            self.assertEqual(response["status"], "LEGACY_V1")
            self.assertFalse(response["commercial_release_certified"])


    def test_all_category_scaffolds_pass_real_packet_contract_validation(self):
        for category in spec.CATEGORIES:
            with self.subTest(category=category), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                out = root / "new_art"
                report = spec.scaffold(category, "ORIGINAL_001", out)
                self.assertEqual(report["status"], "SCAFFOLDED_NOT_APPROVED")
                asset, edit = out / "asset.toml", out / "create.toml"
                adoc, edoc = validator.load_document(asset), validator.load_document(edit)
                for document in (adoc, edoc):
                    validator.validate_document(document.data, document.path)
                validator.cross_validate([adoc, edoc])
                self.assertEqual(edoc.data["asset_spec_v2"]["category"], category)
                run = out / "run.json"
                state = execution_loop.init_from_paths(asset, edit, workspace_root=root)
                self.assertEqual(state["preflight"]["status"], "PASS")
                execution_loop.save_run(run, state)
                packet = next_action.build_from_paths(asset, edit, run)
                self.assertEqual(packet["action"], "imagegen_generate")
                self.assertEqual(packet["asset_spec_v2"]["category"], category)
                self.assertIn("art_v2.category_intent", packet["required_hard_gates"])
                self.assertEqual(packet["fallback_policy"], "none")
                self.assertFalse(report["commercial_release_certified"])

    def test_scaffold_refuses_existing_dir_and_unsafe_id(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "new"
            spec.scaffold("background", "BG_001", out)
            with self.assertRaises(validator.ValidationError):
                spec.scaffold("background", "BG_001", out)
            with self.assertRaises(validator.ValidationError):
                spec.scaffold("background", "../bad-id", root / "other")
            with self.assertRaises(validator.ValidationError):
                spec.scaffold("not_game_art", "ASSET_001", root / "other")

    def test_style_kit_hash_command_only_reads_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            style = style_kit()
            expected = style.pop("sha256")
            source = root / "my-style.json"
            source.write_text(json.dumps(style))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                result = cli.main(["asset-spec", "style-hash", "--json", str(source)])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(out.getvalue())["sha256"], expected)
            self.assertEqual(json.loads(source.read_text()), style)

    def test_malformed_v2_value_types_are_rejected_not_crash(self):
        for field, value in (("category", []), ("alpha_mode", []),
                             ("color_space", {}), ("quality_tier", ["draft"]),
                             ("intended_use", False), ("texture_channel", [])):
            with self.subTest(field=field):
                e = requested_edit("texture_candidate")
                e["asset_spec_v2"][field] = value
                with self.assertRaises(validator.ValidationError):
                    validator.validate_document(e, Path("edit.toml"))

    def test_v2_accepted_spec_cannot_change_after_run_started(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "generation"
            spec.scaffold("background", "BG_001", out)
            asset, edit = out / "asset.toml", out / "create.toml"
            run = out / "run.json"
            execution_loop.save_run(
                run, execution_loop.init_from_paths(asset, edit, workspace_root=root))
            previous = next_action.build_from_paths(asset, edit, run)
            self.assertEqual(previous["action"], "imagegen_generate")
            before = run.read_bytes()
            edit.write_text(edit.read_text().replace("Softbox", "hard spotlight"))
            with self.assertRaises(validator.ValidationError):
                next_action.build_from_paths(asset, edit, run)
            self.assertEqual(run.read_bytes(), before)



    def test_v2_concept_and_marketing_images_cannot_stage_as_ingame_asset(self):
        from PIL import Image
        from unittest.mock import patch
        from artifact_integrity import sha256_file
        from test_v09_autopilot import StubHost
        for category in ("concept_prop", "steam_capsule", "background"):
            with self.subTest(category=category), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                dest = root / "new_art"
                spec.scaffold(category, "ORIGINAL_001", dest)
                size = {"concept_prop": (1536, 1024), "steam_capsule": (920, 430),
                        "background": (1920, 1080)}[category]
                output = io.BytesIO()
                Image.new("RGB", size, "gray").save(output, format="PNG")
                license_file = root / "rights.txt"
                license_file.write_text("Synthetic owner claim for controlled test only.")
                rights = {"basis": "user_owned", "license_id": "USER_OWNED",
                          "review_status": "REVIEWED_FOR_COMMERCIAL_USE",
                          "commercial_use_reviewed": True,
                          "reviewer": "Synthetic test reviewer",
                          "evidence": {"path": "rights.txt",
                                       "sha256": sha256_file(license_file)}}
                manifest = root / "batch.json"
                manifest.write_text(json.dumps(
                    {"schema_version": 1, "batch_id": "BATCH_001",
                     "jobs": [{"id": "JOB_A", "asset": "new_art/asset.toml",
                               "edit": "new_art/create.toml", "rights": rights}]}))
                state = root / "state.json"
                result = batch.run_batch(manifest, root, state, host=StubHost(output.getvalue()))
                self.assertEqual(result["counts"]["ACCEPTED"], 1)
                with patch("batch_production.audit_run", return_value={"status": "PASS"}):
                    if category == "background":
                        approved_for_staging = batch.stage_unity(manifest, root, state, root / "stage")
                        self.assertEqual(approved_for_staging["state"], "STAGED_NOT_UNITY_VERIFIED")
                    else:
                        with self.assertRaises(validator.ValidationError):
                            batch.stage_unity(manifest, root, state, root / "stage")
                        self.assertFalse((root / "stage").exists())



    def test_batch_style_pin_requires_same_sha_across_assets(self):
        from artifact_integrity import sha256_file
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            style_sha = None
            for index, category in enumerate(("background", "ui_icon")):
                result = spec.scaffold(category, f"BATCH_ART_{index}", root / f"job_{index}")
                style_sha = result["style_kit_sha256"]
            rights_file = root / "rights.txt"
            rights_file.write_text("Synthetic rights claim for unit test only")
            rights = {"basis": "user_owned", "license_id": "USER_OWNED",
                      "review_status": "REVIEWED_FOR_COMMERCIAL_USE",
                      "commercial_use_reviewed": True, "reviewer": "Synthetic test reviewer",
                      "evidence": {"path": "rights.txt", "sha256": sha256_file(rights_file)}}
            manifest = root / "batch.json"
            source = {"schema_version": 1, "batch_id": "BATCH_STYLE",
                      "style_kit_sha256": style_sha, "jobs": [
                          {"id": f"JOB_{i}", "asset": f"job_{i}/asset.toml",
                           "edit": f"job_{i}/create.toml", "rights": rights}
                          for i in range(2)]}
            manifest.write_text(json.dumps(source))
            self.assertEqual(batch.make_plan(manifest, root)["style_kit_sha256"], style_sha)
            source["style_kit_sha256"] = "0" * 64
            manifest.write_text(json.dumps(source))
            with self.assertRaises(validator.ValidationError):
                batch.make_plan(manifest, root)
            source.pop("style_kit_sha256")
            manifest.write_text(json.dumps(source))
            self.assertNotIn("style_kit_sha256", batch.make_plan(manifest, root))

    def test_batch_style_pin_rejects_job_without_v2(self):
        from artifact_integrity import sha256_file
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            asset, edit, run, _ = baseline.V06IntegrationTests()._init(root)
            rights = root / "rights.txt"
            rights.write_text("Synthetic rights claim for unit test only")
            manifest = root / "batch.json"
            manifest.write_text(json.dumps({
                "schema_version": 1, "batch_id": "BATCH_001",
                "style_kit_sha256": "b" * 64,
                "jobs": [{"id": "JOB_1", "asset": "asset.toml",
                          "edit": "edit.toml", "rights": {
                              "basis": "user_owned", "license_id": "USER_OWNED",
                              "review_status": "REVIEWED_FOR_COMMERCIAL_USE",
                              "commercial_use_reviewed": True, "reviewer": "Fixture reviewer",
                              "evidence": {"path": "rights.txt",
                                           "sha256": sha256_file(rights)}}}]}))
            with self.assertRaises(validator.ValidationError):
                batch.make_plan(manifest, root)


if __name__ == "__main__":
    unittest.main()
