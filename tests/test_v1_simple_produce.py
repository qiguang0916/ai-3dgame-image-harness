"""v1 core UX wrapper tests: no synthetic result may become commercial approval."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))

import cli
import simple_produce
from validate_project import ValidationError


class ProduceEntryTests(unittest.TestCase):

    def fixture(self,root:Path):
        (root/"asset.toml").write_text('document_type="asset"\n')
        (root/"edit.toml").write_text('document_type="edit"\n')
        return ["run","--workspace-root",str(root),
                "--asset","asset.toml","--edit","edit.toml",
                "--max-actions","1"]

    def run_command(self,argv):
        stream=io.StringIO()
        with redirect_stdout(stream):
            code=simple_produce.main(argv)
        return code,json.loads(stream.getvalue())

    def accepted_run(self,root:Path):
        step=root/"run.json.production/0000-imagegen_edit"
        step.mkdir(parents=True)
        final=step/"generated.png"
        final.write_bytes(b"synthetic placeholder only, NOT real model evidence")
        return {
            "run_id":"SYNTHETIC_TEST_NOT_IMAGEGEN",
            "state":"ACCEPTED",
            "workspace_root":str(root),
            "next_action":"deliver",
            "last_qa":{"status":"PASS"},
            "current_receipt":{
                "result":{"path":"run.json.production/0000-imagegen_edit/generated.png"},
                "result_sha256":"0"*64,
            },
        }

    def test_cli_produce_command_discoverable(self):
        stream=io.StringIO()
        with redirect_stdout(stream):
            code=cli.main(["--help"])
        self.assertEqual(code,0)
        self.assertIn("produce run|status",stream.getvalue())

    def test_status_success_is_only_machine_technical_not_commercial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            fake=self.accepted_run(root)
            with patch.object(simple_produce.execution_loop,"load_run",return_value=fake), \
                 patch.object(simple_produce,"audit_run",return_value={"status":"PASS"}):
                code,data=self.run_command(["status","--run",str(root/"run.json")])
            self.assertEqual(code,0)
            self.assertEqual(data["technical_audit"],"PASS")
            self.assertTrue(data["output_png"].endswith("generated.png"))
            self.assertEqual(data["human_art_approval"],"REQUIRED_NOT_VERIFIED")
            self.assertEqual(data["source_rights"],"NOT_VERIFIED")
            self.assertEqual(data["unity_in_game"],"NOT_VERIFIED")
            self.assertEqual(data["commercial_release"],"BLOCKED")
            self.assertFalse(data["steam_approved"])

    def test_fake_host_accepted_state_with_failed_audit_must_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            accepted=self.accepted_run(root)
            with patch.object(simple_produce.execution_loop,"load_run",return_value=accepted), \
                 patch.object(simple_produce,"audit_run",return_value={
                     "status":"BLOCKED","failures":["synthetic native model event absent"],
                 }):
                code,data=self.run_command(["status","--run",str(root/"run.json")])
            self.assertEqual(code,2)
            self.assertEqual(data["technical_audit"],"BLOCKED")
            self.assertIsNone(data["output_png"])
            self.assertIsNone(data["output_sha256"])
            self.assertEqual(data["audit_failures"],["synthetic native model event absent"])

    def test_blocked_run_avoids_unnecessary_full_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            data={"state":"BLOCKED","run_id":"synthetic",
                  "blocker":{"reason_code":"imagegen_failure"}}
            with patch.object(simple_produce.execution_loop,"load_run",return_value=data), \
                 patch.object(simple_produce,"audit_run") as audit:
                code,result=self.run_command(["status","--run",str(root/"run.json")])
            self.assertEqual(code,2)
            self.assertEqual(result["technical_audit"],"BLOCKED")
            audit.assert_not_called()

    def test_partial_run_exits_nonzero_without_fake_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            state={"state":"QA_PENDING","run_id":"synthetic",
                   "next_action":"visual_qa"}
            with patch.object(simple_produce.execution_loop,"load_run",return_value=state):
                code,result=self.run_command(["status","--run",str(root/"run.json")])
            self.assertEqual(code,3)
            self.assertEqual(result["technical_audit"],"IN_PROGRESS")
            self.assertIsNone(result["output_png"])
            self.assertFalse(result["steam_approved"])

    def test_run_reuses_existing_bounded_native_engine_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            argv=self.fixture(root)
            final=self.accepted_run(root)
            with patch.object(simple_produce,"drive",return_value={"state":"ACCEPTED"}) as work, \
                 patch.object(simple_produce,"NativeCodexHost",return_value=object()), \
                 patch.object(simple_produce.execution_loop,"load_run",return_value=final), \
                 patch.object(simple_produce,"audit_run",return_value={"status":"PASS"}):
                code,result=self.run_command(argv)
            self.assertEqual(code,0)
            self.assertEqual(result["technical_audit"],"PASS")
            self.assertEqual(work.call_count,1)
            self.assertEqual(work.call_args.args[0],(root/"asset.toml").resolve())
            self.assertEqual(work.call_args.args[1],(root/"edit.toml").resolve())
            self.assertEqual(work.call_args.kwargs["max_actions"],1)
            self.assertFalse(work.call_args.kwargs["resume"])

    def test_resume_forwarded_but_never_forced_on_existing_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            argv=self.fixture(root)+["--resume"]
            with patch.object(simple_produce,"drive",side_effect=ValidationError("bad receipt")) as work:
                code,result=self.run_command(argv)
            self.assertEqual(code,2)
            self.assertEqual(result["reason"],"INVALID_INPUT_OR_UNAUDITABLE_RUN")
            self.assertTrue(work.call_args.kwargs["resume"])

    def test_outside_workspace_path_fails_before_model_or_worktree_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            argv=self.fixture(root)
            index=argv.index("--asset")+1
            argv[index]="../not-safe/asset.toml"
            with patch.object(simple_produce,"drive") as work, \
                 patch.object(simple_produce,"NativeCodexHost") as host:
                code,result=self.run_command(argv)
            self.assertEqual(code,2)
            self.assertEqual(result["technical_audit"],"BLOCKED")
            work.assert_not_called()
            host.assert_not_called()

    def test_status_requires_location(self):
        code,data=self.run_command(["status"])
        self.assertEqual(code,2)
        self.assertEqual(data["technical_audit"],"BLOCKED")

    def test_summary_rejects_unbounded_result_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            state=self.accepted_run(root)
            state["current_receipt"]["result"]["path"]="../outside.png"
            with patch.object(simple_produce.execution_loop,"load_run",return_value=state), \
                 patch.object(simple_produce,"audit_run",return_value={"status":"PASS"}):
                code,data=self.run_command(["status","--run",str(root/"run.json")])
            self.assertEqual(code,2)
            self.assertEqual(data["commercial_release"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
