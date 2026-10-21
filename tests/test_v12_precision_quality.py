"""v0.12 quantitative A/B QA: all inputs are synthetic, never art signoff."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from PIL import Image
from artifact_integrity import sha256_file
from precision_quality import _ssim_map, build_quality_report
from validate_project import ValidationError


class PrecisionQualityTests(unittest.TestCase):
    def inputs(self, root: Path, mode: str = "RGB"):
        source, candidate, composite, mask = (
            root / name for name in ("source.png", "raw.png", "composite.png", "mask.png"))
        before = (90, 90, 90) if mode == "RGB" else (90, 90, 90, 255)
        after = (200, 50, 80) if mode == "RGB" else (200, 50, 80, 0)
        Image.new(mode, (24, 24), before).save(source)
        Image.new(mode, (24, 24), after).save(candidate)
        protect = Image.new("L", (24, 24), 0)
        protect.putpixel((10, 10), 255)
        protect.save(mask)
        edit = Image.new(mode, (24, 24), before)
        for y in range(6, 18):
            for x in range(6, 18):
                if (x, y) != (10, 10):
                    edit.putpixel((x, y), after)
        edit.save(composite)
        contract = {
            "mode": "enforce", "pixel_threshold": 0,
            "max_outside_changed_fraction": 0.0,
            "targets": [{"id": "local", "bbox": [.25, .25, .75, .75]}],
            "protected": [],
            "strict_mask": {
                "path": mask.name, "sha256": sha256_file(mask),
                "reference_sha256": sha256_file(source),
            },
        }
        return source, candidate, composite, mask, contract

    def call(self, root, source, candidate, composite, contract,
             report="quality.json", heatmaps="heatmaps"):
        return build_quality_report(source, candidate, composite, contract, root,
                                    root / report, root / heatmaps)

    def test_real_pixel_metrics_and_immutable_heatmaps(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, merged, mask, spec = self.inputs(root)
            hashes = {p.name: sha256_file(p) for p in (src, raw, merged, mask)}
            result = self.call(root, src, raw, merged, spec)
            self.assertEqual(result["state"], "MEASURED_NEEDS_VISUAL_REVIEW")
            self.assertEqual(result["comparison_status"],
                             "NOT_COMPARABLE_UNTIL_SPATIAL_ALIGNMENT_REVIEW")
            self.assertEqual(result["strict_preservation"]["objective_gate"], "PASS")
            self.assertEqual(result["strict_preservation"]["locked_mismatches"], 0)
            self.assertEqual(result["strict_preservation"]["outside_target_mismatches"], 0)
            self.assertEqual(result["strict_preservation"]["mask_protected_mismatches"], 0)
            self.assertGreater(result["strict_preservation"]["changed_editable_pixels"], 0)
            self.assertGreater(result["raw_image"]["outside_target"]
                               ["thresholds_max_channel"]["15"]["changed_pixels"], 0)
            self.assertEqual(result["composited_image"]["outside_target"]
                             ["thresholds_max_channel"]["0"]["changed_pixels"], 0)
            self.assertGreater(result["seam_diagnostics"]["excess_max_rgb_gradient"], 0)
            self.assertGreater(result["composited_image"]["editable"]
                               ["delta_e76_srgb_mean"], 0)
            self.assertLess(result["composited_image"]["editable"]
                            ["ssim_luma_window7_mean"], 1.0)
            self.assertEqual(result["artistic_visual_qa"], "REQUIRED")
            self.assertFalse(result["steam_approved"])
            self.assertEqual(len(result["heatmaps"]), 5)
            saved = json.loads((root / "quality.json").read_text())
            self.assertEqual(saved["composited_sha256"], sha256_file(merged))
            for item in result["heatmaps"].values():
                self.assertEqual(sha256_file(root / item["path"]), item["sha256"])
                with Image.open(root / item["path"]) as image:
                    self.assertEqual(image.size, (24, 24))
            self.assertEqual(hashes, {p.name: sha256_file(p) for p in
                                      (src, raw, merged, mask)})

    def test_locked_pixel_violation_remains_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, merged, mask, spec = self.inputs(root)
            with Image.open(merged) as im:
                pixels = im.copy()
            pixels.putpixel((10, 10), (0, 0, 0))
            pixels.putpixel((0, 0), (1, 2, 3))
            pixels.save(merged)
            result = self.call(root, src, raw, merged, spec)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["strict_preservation"]["objective_gate"], "FAIL")
            self.assertEqual(result["strict_preservation"]["locked_mismatches"], 2)
            self.assertEqual(result["strict_preservation"]["mask_protected_mismatches"], 1)
            self.assertEqual(result["strict_preservation"]["outside_target_mismatches"], 1)
            self.assertFalse(result["commercial_release_certified"])

    def test_tampered_editable_pixels_cannot_masquerade_as_native_composite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, merged, mask, spec = self.inputs(root)
            with Image.open(merged) as original:
                updated = original.copy()
            # Protected/outside pixels remain identical. A naive 0-drift check
            # would falsely accept this altered in-target candidate.
            updated.putpixel((8, 8), (12, 34, 56))
            updated.save(merged)
            result = self.call(root, src, raw, merged, spec)
            self.assertEqual(result["strict_preservation"]["locked_mismatches"], 0)
            self.assertEqual(result["strict_preservation"]["candidate_pixel_mismatches_in_editable"], 1)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["strict_preservation"]["objective_gate"], "FAIL")

    def test_no_effective_local_edit_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, merged, mask, spec = self.inputs(root)
            with Image.open(src) as im:
                im.save(merged)
            result = self.call(root, src, raw, merged, spec)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["strict_preservation"]["changed_editable_pixels"], 0)

    def test_rgba_alpha_edge_diagnostic(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, merged, mask, spec = self.inputs(root, "RGBA")
            result = self.call(root, src, raw, merged, spec)
            self.assertGreater(result["composited_image"]["editable"]
                               ["alpha_changed_pixels"], 0)
            self.assertEqual(result["composited_image"]["strictly_locked"]
                             ["alpha_changed_pixels"], 0)
            self.assertTrue(result["seam_diagnostics"]["visual_seam_review_required"])
            self.assertTrue(result["alpha_boundary_diagnostics"]["applicable"])
            self.assertGreater(result["alpha_boundary_diagnostics"]["max_excess_alpha_jump"], 0)
            self.assertIn("alpha_seam_excess.png", result["heatmaps"])

    def test_size_mode_and_contract_hash_mismatches_block(self):
        for case in ("size", "mode", "source", "mask"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                src, raw, merged, mask, spec = self.inputs(root)
                if case == "size":
                    Image.new("RGB", (25, 24), "black").save(raw)
                elif case == "mode":
                    Image.new("RGBA", (24, 24), "black").save(raw)
                elif case == "source":
                    spec["strict_mask"]["reference_sha256"] = "0" * 64
                else:
                    spec["strict_mask"]["sha256"] = "f" * 64
                with self.assertRaises(ValidationError):
                    self.call(root, src, raw, merged, spec)
                self.assertFalse((root / "quality.json").exists())
                self.assertFalse((root / "heatmaps").exists())

    def test_existing_report_or_heatmap_refuses_overwrite(self):
        for existing in ("quality.json", "heatmaps"):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                src, raw, merged, mask, spec = self.inputs(root)
                if existing.endswith(".json"):
                    (root / existing).write_text("immutable existing review")
                else:
                    (root / existing).mkdir()
                with self.assertRaises(ValidationError):
                    self.call(root, src, raw, merged, spec)
                self.assertTrue((root / existing).exists())

    def test_source_collision_and_workspace_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, merged, mask, spec = self.inputs(root)
            with self.assertRaises(ValidationError):
                self.call(root, src, raw, merged, spec, report="source.png")
            with self.assertRaises(ValidationError):
                self.call(root, src, raw, merged, spec, heatmaps="../escape")

    def test_cli_precision_report_round_trip(self):
        import contextlib
        import io
        import cli

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, merged, mask, spec = self.inputs(root)
            edit = root / "edit.toml"
            edit.write_text(
                "[region_contract]\n"
                'mode = "enforce"\n'
                "pixel_threshold = 0\n"
                "max_outside_changed_fraction = 0.0\n"
                "[[region_contract.targets]]\n"
                'id = "local"\n'
                "bbox = [0.25, 0.25, 0.75, 0.75]\n"
                "[region_contract.strict_mask]\n"
                'path = "mask.png"\n'
                f'sha256 = "{sha256_file(mask)}"\n'
                f'reference_sha256 = "{sha256_file(src)}"\n'
            )
            arguments = [
                "precision-report", "--workspace-root", str(root),
                "--edit", str(edit), "--reference", str(src),
                "--candidate", str(raw), "--composite", str(merged),
                "--report", str(root / "quality.json"),
                "--heatmap-dir", str(root / "heatmaps"),
            ]
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                status = cli.main(arguments)
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(stdout.getvalue())["state"],
                             "MEASURED_NEEDS_VISUAL_REVIEW")
            with contextlib.redirect_stdout(io.StringIO()) as repeated:
                status = cli.main(arguments)
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(repeated.getvalue())["state"], "BLOCKED")

    def test_optional_composition_report_binds_actual_files(self):
        from precision_composite import strict_composite
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, _, mask, spec = self.inputs(root)
            output, compose_json = root / "from-compositor.png", root / "compose.json"
            strict_composite(src, raw, spec, root, output, compose_json)
            result = build_quality_report(
                src, raw, output, spec, root, root / "quality-bound.json",
                root / "heatmaps-bound", compose_report=compose_json
            )
            self.assertEqual(result["composition_evidence"]["status"],
                             "SHA_BOUND_REPORT_MATCH")
            self.assertEqual(result["composition_evidence"]["sha256"],
                             sha256_file(compose_json))
            self.assertEqual(result["strict_preservation"]["locked_mismatches"], 0)
            self.assertEqual(result["artistic_visual_qa"], "REQUIRED")

    def test_tampered_composition_report_refused_without_output(self):
        from precision_composite import strict_composite
        for mutation in ("bad_sha", "false_approval", "bad_change_count"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                src, raw, _, mask, spec = self.inputs(root)
                output, compose_json = root / "from-compositor.png", root / "compose.json"
                strict_composite(src, raw, spec, root, output, compose_json)
                record = json.loads(compose_json.read_text())
                if mutation == "bad_sha":
                    record["candidate_sha256"] = "0" * 64
                elif mutation == "false_approval":
                    record["commercial_release_certified"] = True
                else:
                    record["changed_editable_pixels"] += 1
                compose_json.write_text(json.dumps(record))
                with self.assertRaises(ValidationError):
                    build_quality_report(
                        src, raw, output, spec, root, root / "quality-bound.json",
                        root / "heatmaps-bound", compose_report=compose_json
                    )
                self.assertFalse((root / "quality-bound.json").exists())
                self.assertFalse((root / "heatmaps-bound").exists())

    def test_required_edit_points_are_verified_in_quality_report(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src, raw, merged, mask, spec=self.inputs(root)
            spec["required_edit_points"]=[{"id":"knob_center","uv":[.35,.35]}]
            result=self.call(root,src,raw,merged,spec)
            self.assertEqual(result["required_edit_points"],
                             [{"id":"knob_center","pixel_xy":[8,8],"editable":True}])

    def test_masked_required_edit_point_must_block_quality(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src, raw, merged, mask, spec=self.inputs(root)
            spec["required_edit_points"]=[{"id":"protected_knob_edge","uv":[.43,.43]}]
            with self.assertRaises(ValidationError):
                self.call(root,src,raw,merged,spec)
            self.assertFalse((root/"quality.json").exists())
            self.assertFalse((root/"heatmaps").exists())

    def test_ssim_identity(self):
        import numpy as np
        img = np.arange(12 * 12 * 3, dtype=np.uint8).reshape((12, 12, 3))
        observed = _ssim_map(img, img)
        self.assertTrue(np.allclose(observed, 1.0, atol=1e-9))


if __name__ == "__main__":
    unittest.main()
