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
        self.assertIn("produce check|run|status|export",stream.getvalue())

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

    def test_readonly_source_check_blocks_missing_knife_references_without_host(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=ROOT/"examples/KNIFE_001"
            (root/"edits").mkdir()
            shutil.copy2(original/"asset.toml",root/"asset.toml")
            shutil.copy2(original/"edits/rivets-brushed-silver.toml",
                         root/"edits/rivets-brushed-silver.toml")
            with patch.object(simple_produce,"NativeCodexHost") as host, \
                 patch.object(simple_produce,"drive") as drive:
                code,data=self.run_command(["check","--workspace-root",str(root),
                   "--asset","asset.toml","--edit","edits/rivets-brushed-silver.toml"])
            self.assertEqual(code,2)
            self.assertEqual(data["technical_preflight"],"BLOCKED")
            self.assertEqual(data["reason_code"],"edit_target_missing")
            self.assertEqual(data["selected_reference_count"],2)
            self.assertEqual([x["reference_id"] for x in data["selected_references"]],
                             ["ASSEMBLED_MASTER","HANDLE_L_OUTER_MASTER"])
            self.assertTrue(all(x["status"]=="MISSING_SOURCE"
                                for x in data["selected_references"]))
            self.assertEqual(data["codex_imagegen_calls"],0)
            self.assertFalse(data["run_state_written"])
            self.assertFalse((root/"run.json").exists())
            self.assertFalse((root/"run.json.production").exists())
            host.assert_not_called()
            drive.assert_not_called()

    def test_source_check_rejects_path_escape_and_never_contacts_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(simple_produce,"NativeCodexHost") as host, \
                 patch.object(simple_produce,"drive") as work:
                code,data=self.run_command(["check","--workspace-root",str(root),
                   "--asset","../unsafe/asset.toml","--edit","../unsafe/edit.toml"])
            self.assertEqual(code,2)
            self.assertEqual(data["technical_audit"],"BLOCKED")
            host.assert_not_called()
            work.assert_not_called()

    def test_export_isolated_technical_candidate_has_real_png_bytes_and_no_commercial_claim(self):
        """Fixture-only: audit verdict patched to test wrapper; NOT a real imagegen sample."""
        from PIL import Image
        from simple_produce import sha256_file
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            state=self.accepted_run(root)
            raw=root/"run.json.production/0000-imagegen_edit/generated.png"
            Image.new("RGB",(32,24),(75,111,137)).save(raw)
            state["current_receipt"]["result_sha256"]=sha256_file(raw)
            state["current_receipt"]["receipt_id"]="SYNTHETIC_FIXTURE_RECEIPT"
            (root/"run.json").write_text(json.dumps(state))
            with patch.object(simple_produce.execution_loop,"load_run",return_value=state), \
                 patch.object(simple_produce,"audit_run",return_value={"status":"PASS"}) as audit, \
                 patch.object(simple_produce,"NativeCodexHost") as host:
                code,data=self.run_command(["export","--run",str(root/"run.json"),"--name","RADIO_TEST"])
            self.assertEqual(code,0)
            self.assertEqual(data["technical_audit"],"PASS")
            self.assertEqual(audit.call_count,1)
            host.assert_not_called()
            candidate=root/"exports/RADIO_TEST/candidate.png"
            manifest=root/"exports/RADIO_TEST/manifest.json"
            self.assertEqual(candidate.read_bytes(),raw.read_bytes())
            meta=json.loads(manifest.read_text())
            self.assertEqual(meta["image"]["sha256"],sha256_file(raw))
            self.assertEqual(meta["image"]["width"],32)
            self.assertEqual(meta["image"]["height"],24)
            self.assertEqual(meta["independent_production_audit"],"PASS")
            self.assertEqual(meta["receipt_id"],"SYNTHETIC_FIXTURE_RECEIPT")
            self.assertFalse(meta["steam_approved"])
            self.assertEqual(meta["source_rights"],"NOT_VERIFIED")
            self.assertEqual(meta["commercial_release"],"BLOCKED")
            self.assertEqual(meta["human_art_approval"],"REQUIRED_NOT_VERIFIED")

    def test_export_refuses_failed_audit_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            state=self.accepted_run(root)
            (root/"run.json").write_text(json.dumps(state))
            with patch.object(simple_produce.execution_loop,"load_run",return_value=state), \
                 patch.object(simple_produce,"audit_run",return_value={
                     "status":"BLOCKED","failures":["synthetic model provenance missing"]
                 }):
                code,data=self.run_command(["export","--run",str(root/"run.json"),"--name","X1"])
            self.assertEqual(code,2)
            self.assertEqual(data["technical_audit"],"BLOCKED")
            self.assertFalse((root/"exports").exists())

    def test_export_refuses_unaudited_fake_png_even_if_report_were_fake_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            state=self.accepted_run(root)
            (root/"run.json").write_text(json.dumps(state))
            with patch.object(simple_produce.execution_loop,"load_run",return_value=state), \
                 patch.object(simple_produce,"audit_run",return_value={"status":"PASS"}):
                code,data=self.run_command(["export","--run",str(root/"run.json"),"--name","NO"])
            self.assertEqual(code,2)
            self.assertFalse((root/"exports").exists())

    def test_export_rejects_unsafe_name_before_touching_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            state=self.accepted_run(root)
            for name in ("..","x/y","../outside","a.b","", "x"*100):
                with self.subTest(name=name),patch.object(
                    simple_produce.execution_loop,"load_run"
                ) as read:
                    code,data=self.run_command([
                        "export","--run",str(root/"run.json"),"--name",name
                    ])
                    self.assertEqual(code,2)
                    self.assertEqual(data["commercial_release"],"BLOCKED")
                    read.assert_not_called()
            self.assertFalse((root/"exports").exists())

    def test_export_refuses_to_overwrite_existing_folder_and_file(self):
        from PIL import Image
        from simple_produce import sha256_file
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            state=self.accepted_run(root)
            raw=root/"run.json.production/0000-imagegen_edit/generated.png"
            Image.new("RGB",(16,10),(120,60,90)).save(raw)
            state["current_receipt"]["result_sha256"]=sha256_file(raw)
            state["current_receipt"]["receipt_id"]="SYNTHETIC"
            (root/"run.json").write_text(json.dumps(state))
            preserved=root/"exports/E1"
            preserved.mkdir(parents=True)
            (preserved/"candidate.png").write_bytes(b"ORIGINAL_MUST_STAY")
            with patch.object(simple_produce.execution_loop,"load_run",return_value=state), \
                 patch.object(simple_produce,"audit_run",return_value={"status":"PASS"}) as audit:
                code,data=self.run_command(["export","--run",str(root/"run.json"),"--name","E1"])
            self.assertEqual(code,2)
            audit.assert_not_called()
            self.assertEqual((preserved/"candidate.png").read_bytes(),b"ORIGINAL_MUST_STAY")
            self.assertFalse((preserved/"manifest.json").exists())

    def test_export_refuses_symlinked_export_root_to_outside_workspace(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            work=root/"work"
            work.mkdir()
            outside=root/"outside"
            outside.mkdir()
            state=self.accepted_run(work)
            with (work/"run.json").open("w") as f:json.dump(state,f)
            (work/"exports").symlink_to(outside,target_is_directory=True)
            with patch.object(simple_produce.execution_loop,"load_run",return_value=state):
                code,data=self.run_command(["export","--run",str(work/"run.json"),"--name","X1"])
            self.assertEqual(code,2)
            self.assertEqual(list(outside.iterdir()),[])

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
