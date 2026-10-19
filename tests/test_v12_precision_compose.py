"""v0.12 precision pixel preservation — synthetic test images, no art approval."""
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
from region_quality import compare_images, validate_region_contract
from precision_composite import strict_composite
from validate_project import ValidationError


class StrictCompositeTests(unittest.TestCase):
    def fixture(self, root):
        src, edited, mask = (root / n for n in
                              ("master.png", "generated.png", "protect.png"))
        Image.new("RGB", (12, 12), (99, 99, 99)).save(src)
        Image.new("RGB", (12, 12), (220, 33, 28)).save(edited)
        protection = Image.new("L", (12, 12), 0)
        protection.putpixel((5, 5), 255)
        protection.save(mask)
        contract = {
            "mode": "enforce", "pixel_threshold": 0,
            "max_outside_changed_fraction": 0.0,
            "targets": [{"id": "editable", "bbox": [0.25, 0.25, 0.75, 0.75]}],
            "protected": [],
            "strict_mask": {
                "path": mask.name, "sha256": sha256_file(mask),
                "reference_sha256": sha256_file(src),
            },
        }
        return src, edited, mask, contract

    def composite(self, root, contract, source, edited,
                  out="fixed.png", report="report.json"):
        return strict_composite(source, edited, contract, root,
                                root / out, root / report)

    def test_strict_mask_preserves_original_outside_and_inside(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src, edited, mask, contract = self.fixture(root)
            before = (sha256_file(src), sha256_file(edited))
            result = self.composite(root, contract, src, edited)
            self.assertEqual(result["state"], "CANDIDATE_NEEDS_VISUAL_REVIEW")
            self.assertEqual(result["protected_pixel_mismatches"], 0)
            self.assertEqual(result["outside_target_pixel_mismatches"], 0)
            self.assertGreater(result["changed_editable_pixels"], 0)
            self.assertTrue(result["visual_seam_review_required"])
            self.assertFalse(result["commercial_release_certified"])
            self.assertIn("boundary_changed_pixels", result)
            self.assertEqual(before, (sha256_file(src), sha256_file(edited)))
            with Image.open(root / "fixed.png") as output:
                self.assertEqual(output.size, (12, 12))
                self.assertEqual(output.getpixel((0, 0)), (99, 99, 99))
                self.assertEqual(output.getpixel((4, 4)), (220, 33, 28))
                self.assertEqual(output.getpixel((5, 5)), (99, 99, 99))
                self.assertEqual(output.getpixel((10, 10)), (99, 99, 99))
            saved = json.loads((root / "report.json").read_text())
            self.assertEqual(saved["output_sha256"], sha256_file(root / "fixed.png"))
            self.assertEqual(saved["mask_sha256"], sha256_file(mask))
            self.assertEqual(compare_images(src, root / "fixed.png",
                                            contract)["status"], "PASS")

    def test_wrong_mask_digest_blocks_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); src,edited,mask,c=self.fixture(root)
            c["strict_mask"]["sha256"]="0"*64
            with self.assertRaises(ValidationError):
                self.composite(root,c,src,edited)
            self.assertFalse((root/"fixed.png").exists())

    def test_wrong_source_digest_blocks_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); src,edited,mask,c=self.fixture(root)
            c["strict_mask"]["reference_sha256"]="f"*64
            with self.assertRaises(ValidationError):
                self.composite(root,c,src,edited)
            self.assertFalse((root/"fixed.png").exists())

    def test_mask_is_binary_grayscale_and_size_locked(self):
        for issue in ("grey", "wrong_size", "rgb"):
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); src,edited,mask,c=self.fixture(root)
                if issue=="grey":
                    with Image.open(mask) as im:
                        image=im.copy()
                    image.putpixel((1,1),128); image.save(mask)
                elif issue=="wrong_size":
                    Image.new("L",(6,6),0).save(mask)
                else:
                    Image.new("RGB",(12,12),"white").save(mask)
                c["strict_mask"]["sha256"]=sha256_file(mask)
                with self.assertRaises(ValidationError):
                    self.composite(root,c,src,edited)

    def test_misaligned_or_different_color_mode_rejected(self):
        for issue in ("size","mode"):
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); src,edited,mask,c=self.fixture(root)
                if issue=="size":
                    Image.new("RGB",(24,12),"white").save(edited)
                else:
                    Image.new("RGBA",(12,12),(120,130,140,255)).save(edited)
                with self.assertRaises(ValidationError):
                    self.composite(root,c,src,edited)
                self.assertFalse((root/"fixed.png").exists())

    def test_zero_edit_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); src,edited,mask,c=self.fixture(root)
            with Image.open(src) as im: im.save(edited)
            with self.assertRaises(ValidationError):
                self.composite(root,c,src,edited)
            self.assertFalse((root/"fixed.png").exists())

    def test_fully_protected_area_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); src,edited,mask,c=self.fixture(root)
            Image.new("L",(12,12),255).save(mask)
            c["strict_mask"]["sha256"]=sha256_file(mask)
            with self.assertRaises(ValidationError):
                self.composite(root,c,src,edited)

    def test_existing_artifacts_unchanged(self):
        for name in ("fixed.png","report.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); src,edited,mask,c=self.fixture(root)
                (root/name).write_bytes(b"retain historical bytes")
                with self.assertRaises(ValidationError):
                    self.composite(root,c,src,edited)
                self.assertEqual((root/name).read_bytes(),b"retain historical bytes")

    def test_workspace_escape_and_symlink_block(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"project"; root.mkdir()
            src,edited,mask,c=self.fixture(root)
            c["strict_mask"]["path"]="../escape.png"
            with self.assertRaises(ValidationError):
                self.composite(root,c,src,edited)
            c["strict_mask"]["path"]="protect.png"
            (root/"fixed.png").symlink_to(mask)
            with self.assertRaises(ValidationError):
                self.composite(root,c,src,edited)

    def test_enforce_target_mask_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); src,edited,mask,c=self.fixture(root)
            validate_region_contract({"operation":"local_edit","region_contract":c},"test")
            variants = [
                lambda x: x.update(mode="report"),
                lambda x: x.update(targets=[]),
                lambda x: x["strict_mask"].update(sha256="broken"),
                lambda x: x["strict_mask"].update(extra=True),
                lambda x: x["strict_mask"].update(path="/absolute/protect.png"),
            ]
            for change in variants:
                cloned=json.loads(json.dumps(c))
                change(cloned)
                with self.assertRaises(ValidationError):
                    validate_region_contract(
                        {"operation":"local_edit","region_contract":cloned},"test")

    def test_output_paths_cannot_shadow_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); src,edited,mask,c=self.fixture(root)
            with self.assertRaises(ValidationError):
                self.composite(root,c,src,edited,out="generated.png")
            with self.assertRaises(ValidationError):
                self.composite(root,c,src,edited,report="master.png")


    def test_complete_cli_and_contract_binding(self):
        import contextlib
        import io
        from PIL import Image
        from artifact_integrity import canonical_json_bytes, sha256_bytes
        import test_v06_integration as fixtures
        import cli
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset, edit, run_file, _ = fixtures.V06IntegrationTests()._init(root)
            reference = root / "master.png"
            generated = root / "generated.png"
            with Image.open(reference) as image:
                altered = image.copy()
            altered.putpixel((2, 2), (10, 120, 225))
            altered.save(generated)
            protected = Image.new("L", (40, 40), 0)
            protected.putpixel((4, 4), 255)
            mask = root / "protect.png"
            protected.save(mask)
            edit.write_text(edit.read_text() + (
                "\n[region_contract.strict_mask]\n"
                'path = "protect.png"\n'
                f'sha256 = "{sha256_file(mask)}"\n'
                f'reference_sha256 = "{sha256_file(reference)}"\n'
            ))
            output, report = root / "merged.png", root / "merged-report.json"
            args = ["precision-compose", "--workspace-root", str(root),
                    "--edit", str(edit), "--reference", str(reference),
                    "--candidate", str(generated), "--output", str(output),
                    "--report", str(report)]
            with contextlib.redirect_stdout(io.StringIO()) as capture:
                exit_code = cli.main(args)
            self.assertEqual(exit_code, 0)
            result = json.loads(capture.getvalue())
            self.assertEqual(result["state"], "CANDIDATE_NEEDS_VISUAL_REVIEW")
            self.assertTrue(result["visual_seam_review_required"])
            from validate_project import load_document
            spec = load_document(edit).data["region_contract"]
            self.assertEqual(result["contract_sha256"],
                             sha256_bytes(canonical_json_bytes(spec)))
            self.assertEqual(result["output_sha256"], sha256_file(output))
            self.assertEqual(result["outside_target_pixel_mismatches"], 0)
            self.assertEqual(result["protected_pixel_mismatches"], 0)
            self.assertEqual(compare_images(reference, output, spec)["status"], "PASS")
            first_sha = sha256_file(output)
            with contextlib.redirect_stdout(io.StringIO()) as error:
                repeated = cli.main(args)
            self.assertEqual(repeated, 2)
            self.assertEqual(json.loads(error.getvalue())["state"], "BLOCKED")
            self.assertEqual(sha256_file(output), first_sha)


    def test_seam_gradient_metric_exposes_edge_risk_without_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src, generated, mask, contract = self.fixture(root)
            qa = self.composite(root, contract, src, generated)
            self.assertGreater(qa["seam_crossing_pairs"], 0)
            self.assertGreater(qa["seam_excess_max_channel_jump"], 0)
            self.assertGreater(qa["seam_excess_mean_channel_jump"], 0)
            self.assertTrue(qa["visual_seam_review_required"])
            self.assertEqual(qa["state"], "CANDIDATE_NEEDS_VISUAL_REVIEW")
            self.assertFalse(qa["steam_approved"])


if __name__=="__main__":
    unittest.main()
