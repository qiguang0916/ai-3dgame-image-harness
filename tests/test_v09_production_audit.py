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

    def test_blocked_run_with_null_receipt_and_qa_returns_blocked_report(self):
        import json
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            path=root/"run.json"
            path.write_text(json.dumps({
                "state":"BLOCKED","auditable":True,
                "workspace_root":str(root),
                "current_receipt":None,"last_qa":None,
                "required_hard_gates":["requested_change"],
                "iteration":0,"asset_id":"LAMP_001"
            }))
            result=audit_run(path)
            self.assertEqual(result["status"],"BLOCKED")
            self.assertFalse(result["steam_approved"])
            self.assertTrue(any("receipt" in x for x in result["failures"]))

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


    def synthetic_origin_for_binding_test(self, path):
        # UNIT-TEST ONLY: fake a native source to exercise QA consistency.
        # Never use this helper in actual CLI or production evidence.
        import json
        from unittest.mock import patch
        from artifact_integrity import sha256_bytes
        step=next(path.parent.rglob("*-imagegen_*"))
        att_path=step/"attestation.json"
        att=json.loads(att_path.read_text())
        att["backend"]="native_codex_chatgpt"
        att["event_transcript_sha256"]=sha256_bytes((step/"events.jsonl").read_bytes())
        att_path.write_text(json.dumps(att))
        critic=next(path.parent.rglob("*-visual_qa"))
        critic_att=critic/"attestation.json"
        reviewer=json.loads(critic_att.read_text())
        reviewer["event_transcript_sha256"]=sha256_bytes((critic/"events.jsonl").read_bytes())
        critic_att.write_text(json.dumps(reviewer))
        with patch("production_audit.native_generated_source",
                   side_effect=lambda events, image, home: image):
            return audit_run(path)

    def test_intact_qa_roundtrip_in_unit_only_stub_environment(self):
        with tempfile.TemporaryDirectory() as raw:
            path=self.accepted_stub(Path(raw))
            # Source-matching is mocked in this unit case, not real model proof.
            report=self.synthetic_origin_for_binding_test(path)
            self.assertEqual("PASS",report["status"],report["failures"])

    def test_critic_receipt_identity_and_final_verdict_mismatches_are_named_blockers(self):
        import json
        tamper_cases = (
            ("result_sha256", "0" * 64, "critic QA output SHA mismatches its native receipt"),
            ("request_id", "SWAPPED_REQUEST", "critic QA run/request/iteration identity mismatch"),
            ("summary", "Forged critic description", "final Run QA differs from persisted critic report"),
        )
        for field, forged, expected in tamper_cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as raw:
                root=Path(raw)
                run=self.accepted_stub(root)
                qa_path=next(root.rglob("qa.toml"))
                lines=qa_path.read_text().splitlines(keepends=True)
                matches=[i for i,line in enumerate(lines) if line.startswith(field+" = ")]
                self.assertEqual(len(matches),1)
                lines[matches[0]]=field+" = "+json.dumps(forged)+chr(10)
                qa_path.write_text("".join(lines))
                report=self.synthetic_origin_for_binding_test(run)
                self.assertEqual("BLOCKED",report["status"])
                self.assertTrue(any(expected in issue for issue in report["failures"]),
                                report["failures"])

    def test_changed_final_run_qa_cannot_override_persisted_critic(self):
        import json
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            path=self.accepted_stub(root)
            payload=json.loads(path.read_text())
            payload["last_qa"]["summary"]="Forged final PASS despite unchanged critic evidence"
            path.write_text(json.dumps(payload))
            report=self.synthetic_origin_for_binding_test(path)
            self.assertEqual("BLOCKED",report["status"])
            self.assertTrue(any("final Run QA differs from persisted critic report" in issue
                                for issue in report["failures"]), report["failures"])


if __name__=="__main__":
    unittest.main()

