"""Regression: independent visual QA can truthfully say NOT_VERIFIABLE.

No external image generation or real commercial approval occurs in these tests.
"""
from __future__ import annotations
import sys
import tempfile
import unittest
import json
import subprocess
from unittest.mock import patch
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


    def test_readonly_critic_receives_digest_bound_technical_preflight(self):
        from artifact_integrity import packet_digest
        from native_codex_host import NativeCodexHost
        from next_action import build_from_paths
        from test_v09_autopilot import StubHost
        import production_autopilot
        for expected, verdict in (("40x40", "PASS"), ("32x32", "FAIL")):
            with self.subTest(verdict=verdict), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                asset, edit, run_file, _ = baseline.V06IntegrationTests()._init(root, tech=True)
                host = StubHost((root / "master.png").read_bytes())
                step = production_autopilot.drive(asset, edit, root, run_file,
                                                  resume=True, max_actions=1, host=host)
                self.assertEqual(step["state"], "QA_PENDING")
                packet = build_from_paths(asset, edit, run_file)
                packet["technical_output"]["expected_size"] = expected
                packet["packet_id"] = packet_digest(packet)
                seen = []
                def fake_run(argv, **kw):
                    if argv[1:] == ["login", "status"]:
                        return subprocess.CompletedProcess(argv, 0, b"Logged in using ChatGPT", b"")
                    prompt = kw["input"].decode("utf-8")
                    seen.append(prompt)
                    self.assertEqual(argv[argv.index("-s")+1], "read-only")
                    stage = Path(argv[argv.index("-C")+1])
                    self.assertIn("input-0.png", [x.name for x in stage.glob("input-*.png")])
                    output = Path(argv[argv.index("-o")+1])
                    gates = [
                        {"name": gate, "status": verdict if gate == "image.technical_output" else "PASS",
                         "note": "Controlled synthetic pixels and observable shape",
                         "inspection_method": "Synthetic fixture actual pixel comparison",
                         "observation": "Unique fixture pixel evidence for " + gate}
                        for gate in packet["required_hard_gates"]
                    ]
                    qa = {"status": "PASS" if verdict=="PASS" else "BLOCKED",
                          "summary":"Synthetic controlled fixture independent QA",
                          "repair_directives":[], "gates":gates}
                    output.write_text(json.dumps(qa))
                    return subprocess.CompletedProcess(argv, 0, b'{"type":"turn.completed"}\n', b"")
                with patch("native_codex_host.subprocess.run", side_effect=fake_run):
                    answer, evidence, transcript = NativeCodexHost("/fake/codex").execute(packet, reviewer=True)
                self.assertEqual(answer["status"], "PASS" if verdict=="PASS" else "BLOCKED")
                self.assertEqual(evidence["technical_precheck"]["status"], verdict)
                self.assertIn("DIGEST-BOUND TECHNICAL IMAGE MEASUREMENT", seen[0])
                self.assertIn(f"status={verdict}", seen[0])
                self.assertIn(packet["result_binding"]["sha256"], seen[0])

    def test_critic_may_not_report_technical_pass_against_measured_failure(self):
        from artifact_integrity import packet_digest
        from native_codex_host import NativeCodexHost
        from next_action import build_from_paths
        from test_v09_autopilot import StubHost
        import production_autopilot
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            asset, edit, run_file, _ = baseline.V06IntegrationTests()._init(root, tech=True)
            production_autopilot.drive(asset, edit, root, run_file, resume=True,
                                       max_actions=1, host=StubHost((root / "master.png").read_bytes()))
            packet = build_from_paths(asset, edit, run_file)
            packet["technical_output"]["expected_size"] = "800x800"
            packet["packet_id"] = packet_digest(packet)
            def fake_run(argv, **kw):
                if argv[1:] == ["login", "status"]:
                    return subprocess.CompletedProcess(argv, 0, b"Logged in using ChatGPT", b"")
                gates = [
                    {"name": name, "status": "PASS", "note":"Synthetic deliberate false approval",
                     "inspection_method":"Mocked controlled image inspection",
                     "observation":"Synthetic per-gate evidence for "+name}
                    for name in packet["required_hard_gates"]
                ]
                Path(argv[argv.index("-o")+1]).write_text(json.dumps({
                    "status":"PASS", "summary":"False critic approval in synthetic test",
                    "repair_directives":[], "gates": gates}))
                return subprocess.CompletedProcess(argv, 0, b"{}\n", b"")
            with patch("native_codex_host.subprocess.run", side_effect=fake_run):
                with self.assertRaises(ValidationError):
                    NativeCodexHost("/fake/codex").execute(packet, reviewer=True)


if __name__ == "__main__":
    unittest.main()
