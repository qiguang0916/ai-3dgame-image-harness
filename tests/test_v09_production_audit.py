"""Production audit refuses stub/forged artifacts and missing real Native Codex proof."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))

from production_audit import audit_run
from production_autopilot import drive
import test_v09_autopilot as auto_suite


class AuditTests(unittest.TestCase):
    def accepted_stub(self, root):
        a,e,r,host=auto_suite.AutopilotTests().fixture(root)
        output=drive(a,e,root,r,resume=True,host=host)
        self.assertEqual("ACCEPTED",output["state"])
        return r

    def test_does_not_certify_missing_run(self):
        with tempfile.TemporaryDirectory() as raw:
            result=audit_run(Path(raw)/"missing.json")
            self.assertEqual("BLOCKED",result["status"])
            self.assertFalse(result["steam_approved"])

    def test_synthetic_qa_pass_cannot_masquerade_as_native_imagegen(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            run=self.accepted_stub(root)
            report=audit_run(run)
            self.assertEqual("BLOCKED",report["status"])
            self.assertEqual(1,len(report["generation_steps"]))
            self.assertIn("native",str(report["failures"]).lower())
            self.assertFalse(report["steam_approved"])

    def test_altered_generated_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            run=self.accepted_stub(root)
            img=next(root.rglob("generated.png"))
            img.write_bytes(b"broken image")
            report=audit_run(run)
            self.assertEqual("BLOCKED",report["status"])
            self.assertIn("final result",str(report["failures"]).lower())

    def test_unknown_transcript_not_acceptable(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            run=self.accepted_stub(root)
            trace=next(root.rglob("events.jsonl"))
            trace.write_bytes(b"{}")
            report=audit_run(run)
            self.assertEqual("BLOCKED",report["status"])


if __name__=="__main__":
    unittest.main()
