"""Regression: independent visual QA can truthfully say NOT_VERIFIABLE.

No external image generation or real commercial approval occurs in these tests.
"""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import execution_loop as loop
from asset_report import verify_output_gate
import test_v06_integration as baseline
from validate_project import ValidationError


class TechnicalUncertaintyTests(unittest.TestCase):
    def test_measured_pass_but_critic_not_verifiable_remains_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture = baseline.V06IntegrationTests()
            asset, edit, run_path, packet = fixture._init(root, tech=True)
            run = fixture._generate(root, run_path, packet, corrupt=False)
            report = fixture._qa(run, status="BLOCKED", technical="NOT_VERIFIABLE")
            final = loop.apply_qa(run, report)
            self.assertEqual(final["state"], "BLOCKED")
            self.assertEqual(final["blocker"]["reason_code"], "visual_inspection_unavailable")
            self.assertEqual(final["last_qa"]["status"], "BLOCKED")
            self.assertEqual(final["last_qa"]["technical_output"]["status"], "PASS")
            self.assertIn("image.technical_output", run["required_hard_gates"])

    def test_measured_failure_with_uncertain_critic_never_upgrades_to_pass(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            wrong = Path(d) / "wrong.png"
            Image.new("RGB", (32, 32), "gray").save(wrong)
            contract = {"expected_size": "64x32"}
            measured = verify_output_gate(contract, wrong, "NOT_VERIFIABLE")
            self.assertEqual(measured["status"], "FAIL")
            with self.assertRaises(ValidationError):
                verify_output_gate(contract, wrong, "PASS")

    def test_unknown_status_is_always_rejected(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / "output.png"
            Image.new("RGB", (64, 32), "gray").save(image)
            with self.assertRaises(ValidationError):
                verify_output_gate({"expected_size": "64x32"}, image, "SKIPPED")
            with self.assertRaises(ValidationError):
                verify_output_gate({"expected_size": "64x32"}, image, "NOT_CHECKED")


if __name__ == "__main__":
    unittest.main()
