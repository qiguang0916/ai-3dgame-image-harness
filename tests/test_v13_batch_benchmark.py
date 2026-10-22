"""Offline v0.13 KPI tests; mock Host never counts as actual production proof."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))

import batch_production as batch
import batch_benchmark as metrics
import test_v10_batch_production as batch_fixtures
from validate_project import ValidationError


class BatchBenchmarkTests(unittest.TestCase):
    def fixture(self,root,*,jobs=1,complete=False):
        manifest,state_path,host,_=batch_fixtures.BatchTests().fixture(root,jobs=jobs)
        plan=batch.make_plan(manifest,root)
        if complete:
            batch.run_batch(manifest,root,state_path,host=host,max_jobs=jobs)
            state=batch.read_json(state_path)
        else:
            state={"schema_version":1,"plan":plan,
                   "jobs":[{"id":j["id"],"status":"PENDING"} for j in plan["jobs"]]}
        return manifest,state_path,host,plan,state

    def test_zero_real_samples_remain_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,_,plan,state=self.fixture(root)
            r=metrics.build_report(plan,state,"pilot")
            self.assertEqual(r["independent_audited_native_results"],0)
            self.assertEqual(r["planned_jobs"],1)
            self.assertEqual(r["started_jobs"],0)
            self.assertIsNone(r["first_pass_rate_observed"])
            self.assertIsNone(r["final_pass_95pct_wilson"])
            self.assertEqual(r["status"],"INSUFFICIENT_VERIFIED_REAL_PRODUCTION")
            self.assertEqual(r["jobs"][0]["reason"],"never_started")
            self.assertFalse(r["commercial_release_certified"])
            self.assertEqual(r["imagegen_calls_triggered_by_report"],0)

    def test_stub_accepted_does_not_count_as_native(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,host,plan,state=self.fixture(root,complete=True)
            calls=list(host.actions)
            r=metrics.build_report(plan,state,"pilot")
            self.assertEqual(r["started_jobs"],1)
            self.assertEqual(r["independent_audited_native_results"],0)
            self.assertEqual(r["jobs"][0]["reason"],"production_audit_not_pass")
            self.assertEqual(r["first_pass_rate_observed"],0)
            self.assertEqual(r["final_pass_rate_observed"],0)
            self.assertEqual(host.actions,calls)

    def test_firstpass_math_only_with_mocked_auditor(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,_,plan,state=self.fixture(root,complete=True)
            # Stub auditor only exercises the math. Real CLI never injects it.
            r=metrics.build_report(plan,state,"pilot",auditor=lambda _:{"status":"PASS"})
            self.assertEqual(r["started_jobs"],1)
            self.assertEqual(r["independent_audited_native_results"],1)
            self.assertEqual(r["first_pass_accepted"],1)
            self.assertEqual(r["first_pass_rate_observed"],1)
            self.assertEqual(r["final_pass_rate_observed"],1)
            self.assertEqual(r["status"],"INSUFFICIENT_VERIFIED_REAL_PRODUCTION")
            self.assertEqual(r["total_repair_passes_verified"],0)
            self.assertEqual(r["manual_intervention_rate"],"NOT_VERIFIABLE_WITHOUT_HUMAN_DECISION_EVIDENCE")

    def test_duplicate_run_result_and_contract_all_disqualified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,_,plan,state=self.fixture(root,jobs=2,complete=True)
            r=metrics.build_report(plan,state,"pilot",auditor=lambda _:{"status":"PASS"})
            self.assertEqual(r["started_jobs"],2)
            self.assertEqual(r["duplicate_native_result_sha_count"],1)
            self.assertEqual(r["duplicate_native_run_id_count"],1)
            self.assertEqual(r["duplicate_source_asset_edit_contract_count"],1)
            self.assertEqual(r["independent_audited_native_results"],0)
            self.assertTrue(all(j["reason"]=="duplicate_native_result_sha" for j in r["jobs"]))

    def test_wilson_bounds(self):
        self.assertIsNone(metrics.wilson_interval(0,0))
        self.assertEqual(metrics.wilson_interval(1,1)[1],1)
        self.assertEqual(metrics.wilson_interval(0,8)[0],0)
        self.assertLess(metrics.wilson_interval(1,2)[0],.5)
        with self.assertRaises(ValidationError):
            metrics.wilson_interval(3,2)

    def test_malformed_plan_identity_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,_,plan,state=self.fixture(root,jobs=2)
            state["jobs"][1]["id"]="WRONG"
            with self.assertRaises(ValidationError):
                metrics.build_report(plan,state,"pilot")

    def test_markdown_does_not_assert_release_ready(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _,_,_,plan,state=self.fixture(root)
            md=metrics.markdown(metrics.build_report(plan,state,"candidate"))
            self.assertIn("BLOCKED_PENDING_ART_UNITY_RIGHTS_STEAM",md)
            self.assertIn("Audited Native",md)
            self.assertIn("| Category |",md)
            self.assertNotIn("STEAM_APPROVED",md)

    def test_new_only_json_report_no_second_model_action(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            m,s,host,plan,state=self.fixture(root)
            s.write_text(json.dumps(state))
            args=["--workspace-root",str(root),"--manifest",str(m),
                  "--state",str(s),"--phase","pilot",
                  "--output",str(root/"report.json")]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(metrics.main(args),2)
            dest=root/"report.json"
            self.assertTrue(dest.is_file())
            self.assertEqual(json.loads(dest.read_text())["independent_audited_native_results"],0)
            data=dest.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(metrics.main(args),2)
            self.assertEqual(dest.read_bytes(),data)
            self.assertEqual(host.actions,[])

    def test_markdown_cli_and_wrong_extension(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            m,s,_,plan,state=self.fixture(root)
            s.write_text(json.dumps(state))
            params=["--workspace-root",str(root),"--manifest",str(m),
                    "--state",str(s),"--format","markdown"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(metrics.main([*params,"--output",str(root/"report.md")]),2)
            self.assertIn("sample benchmark",(root/"report.md").read_text().lower())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(metrics.main([*params,"--output",str(root/"wrong.json")]),2)
            self.assertFalse((root/"wrong.json").exists())

    def test_rights_source_sha_mutation_refuses_report(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            m,s,_,plan,state=self.fixture(root)
            s.write_text(json.dumps(state))
            (root/"rights-proof.txt").write_text("tampered rights!")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(metrics.main(["--workspace-root",str(root),
                    "--manifest",str(m),"--state",str(s),
                    "--output",str(root/"r.json")]),2)
            self.assertFalse((root/"r.json").exists())


if __name__=="__main__":
    unittest.main()
