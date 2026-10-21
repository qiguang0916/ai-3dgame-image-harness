"""Approval record binding tests; synthetic only, never a reviewer identity proof."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from artifact_integrity import sha256_file
from roi_mask_approval import verify_roi_mask_approval
from precision_quality import build_quality_report
from validate_project import ValidationError
from test_v12_precision_quality import PrecisionQualityTests


class RoiApprovalReceiptTests(unittest.TestCase):
    def fixture(self, root):
        src, raw, result, mask, contract = PrecisionQualityTests().inputs(root)
        receipt = {
            "schema_version": 1,
            "document_type": "human_review_decision",
            "decision": "APPROVE_ROI_AND_PROTECTION_MASK",
            "decision_source": "explicit project owner decision in conversation",
            "scope": "v002 source-specific ROI/Mask only",
            "inputs_immutable": True,
            "not_approved": [
                "visual QA", "Unity", "rights", "Steam", "Master promotion"
            ],
            "assets": [{
                "asset_id": "TEST_PROP_001",
                "approved_roi_targets": contract["targets"],
                "approved_binary_mask_sha256": sha256_file(mask),
                "pinned_master_sha256": sha256_file(src),
                "approval_granted": "ROI_AND_MASK_ONLY",
                "final_art_qa": "REVIEW_REQUIRED",
                "visual_alignment_review": "REVIEW_REQUIRED",
                "steam_approved": False,
            }],
        }
        evidence = root / "roi-user-decision.json"
        evidence.write_text(json.dumps(receipt), encoding="utf-8")
        return src, raw, result, mask, contract, evidence

    def verify(self, root, src, mask, contract, evidence, *, asset="TEST_PROP_001"):
        return verify_roi_mask_approval(
            workspace_root=root,
            approval_path=evidence,
            approval_sha256=sha256_file(evidence),
            asset_id=asset,
            reference=src, mask_path=mask,
            contract=contract,
        )

    def test_approved_mask_only_binds_without_art_or_steam_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, result, mask, contract, receipt = self.fixture(root)
            verdict = self.verify(root, src, mask, contract, receipt)
            self.assertEqual(verdict["status"], "ROI_MASK_DECISION_RECORD_BOUND")
            self.assertEqual(verdict["review_scope"], "ROI_AND_MASK_ONLY")
            self.assertEqual(verdict["approved_mask_sha256"], sha256_file(mask))
            self.assertFalse(verdict["reviewer_identity_cryptographically_attested"])
            self.assertFalse(verdict["master_promotion"])
            self.assertFalse(verdict["steam_approved"])
            measured = build_quality_report(
                src, raw, result, contract, root,
                root / "approved-quality.json", root / "approved-heatmaps",
                roi_approval_file=receipt, roi_approval_sha256=sha256_file(receipt),
                asset_id="TEST_PROP_001")
            self.assertEqual(measured["state"], "MEASURED_NEEDS_VISUAL_REVIEW")
            self.assertEqual(measured["roi_mask_review"]["status"],
                             "ROI_MASK_DECISION_RECORD_BOUND")
            self.assertEqual(measured["artistic_visual_qa"], "REQUIRED")

    def test_wrong_record_digest_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, comp, mask, contract, receipt = self.fixture(root)
            with self.assertRaises(ValidationError):
                verify_roi_mask_approval(
                    workspace_root=root, approval_path=receipt,
                    approval_sha256="0"*64, asset_id="TEST_PROP_001",
                    reference=src, mask_path=mask, contract=contract)

    def test_wrong_asset_does_not_borrow_another_mask_authority(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, comp, mask, contract, receipt = self.fixture(root)
            with self.assertRaises(ValidationError):
                self.verify(root, src, mask, contract, receipt, asset="DIFFERENT_ASSET")

    def test_changed_regions_do_not_reuse_prior_approval(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, comp, mask, contract, receipt = self.fixture(root)
            contract["targets"][0]["bbox"] = [0.2, 0.2, 0.8, 0.8]
            with self.assertRaises(ValidationError):
                self.verify(root, src, mask, contract, receipt)

    def test_mask_tampering_blocks_even_if_contract_is_rewritten(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, comp, mask, contract, receipt = self.fixture(root)
            Image.new("L", (24, 24), 0).save(mask)
            contract["strict_mask"]["sha256"] = sha256_file(mask)
            with self.assertRaises(ValidationError):
                self.verify(root, src, mask, contract, receipt)

    def test_false_art_or_steam_approval_rejected(self):
        for mutation in ("final_art", "steam", "scope", "duplicate"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                src, raw, comp, mask, contract, receipt = self.fixture(root)
                record = json.loads(receipt.read_text())
                case = record["assets"][0]
                if mutation == "final_art":
                    case["final_art_qa"] = "PASS"
                elif mutation == "steam":
                    case["steam_approved"] = True
                elif mutation == "scope":
                    case["approval_granted"] = "FULL_COMMERCIAL_APPROVED"
                else:
                    record["assets"].append(case.copy())
                receipt.write_text(json.dumps(record))
                with self.assertRaises(ValidationError):
                    self.verify(root, src, mask, contract, receipt)

    def test_partial_approval_trio_fails_before_any_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, comp, mask, contract, receipt = self.fixture(root)
            with self.assertRaises(ValidationError):
                build_quality_report(
                    src, raw, comp, contract, root,
                    root / "q.json", root / "heatmaps",
                    roi_approval_file=receipt)
            self.assertFalse((root / "q.json").exists())
            self.assertFalse((root / "heatmaps").exists())

    def test_workspace_escape_and_record_path_collision_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, comp, mask, contract, receipt = self.fixture(root)
            with self.assertRaises(ValidationError):
                verify_roi_mask_approval(
                    workspace_root=root, approval_path="../outside.json",
                    approval_sha256=sha256_file(receipt),
                    asset_id="TEST_PROP_001",
                    reference=src, mask_path=mask, contract=contract)

    def test_approved_original_source_does_not_certify_new_model_result(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, raw, comp, mask, contract, receipt = self.fixture(root)
            verified = self.verify(root, src, mask, contract, receipt)
            self.assertEqual(verified["review_scope"], "ROI_AND_MASK_ONLY")
            # A later native output can reuse approved source/ROI/mask, but must
            # undergo its own new native provenance, quality, and visual QA.
            self.assertNotIn("candidate_sha256", verified)
            self.assertEqual(verified["independent_visual_qa"], "REQUIRED")


if __name__ == "__main__":
    unittest.main()
