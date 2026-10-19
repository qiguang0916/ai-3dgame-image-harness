"""v0.10.1 fault-injection regressions; all Hosts here are synthetic fixtures."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import batch_production as batch
import execution_loop as loop
import production_autopilot as autopilot
import test_v06_integration as fixtures
from test_v09_autopilot import StubHost
import test_v10_batch_production as batch_fixtures
from validate_project import ValidationError


class DurabilityTests(unittest.TestCase):
    def fixture(self, root):
        return batch_fixtures.BatchTests().fixture(root)

    def test_run_state_atomic_replace_failure_preserves_previous_valid_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, original_run, _ = fixtures.V06IntegrationTests()._init(root)
            before = original_run.read_bytes()
            with patch("os.replace", side_effect=OSError("synthetic interrupted rename")):
                with self.assertRaises(OSError):
                    loop.save_run(original_run, loop.load_run(original_run))
            self.assertEqual(original_run.read_bytes(), before)
            self.assertEqual(loop.load_run(original_run)["state"], "READY")
            self.assertEqual(sorted(root.glob("." + original_run.name + ".*.tmp")), [])

    def test_accepted_batch_missing_run_is_not_reported_as_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, state, host, _ = self.fixture(root)
            self.assertEqual(batch.run_batch(manifest, root, state, host=host)["counts"]["ACCEPTED"], 1)
            plan = batch.make_plan(manifest, root)
            (root / plan["jobs"][0]["run"]).unlink()
            other_host = StubHost(host.image)
            result = batch.run_batch(manifest, root, state, resume=True, host=other_host)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["counts"]["ERROR"], 1)
            self.assertEqual(other_host.actions, [])

    def test_accepted_batch_swapped_run_is_not_silently_trusted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, state, host, _ = self.fixture(root)
            batch.run_batch(manifest, root, state, host=host)
            run_file = root / batch.make_plan(manifest, root)["jobs"][0]["run"]
            run = json.loads(run_file.read_text())
            run["edit_document_path"] = "other-edit.toml"
            run_file.write_text(json.dumps(run))
            other_host = StubHost(host.image)
            result = batch.run_batch(manifest, root, state, resume=True, host=other_host)
            self.assertEqual(result["counts"]["ERROR"], 1)
            self.assertEqual(other_host.actions, [])

    def test_orphan_batch_run_rejected_before_creating_batch_state(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, state, host, _ = self.fixture(root)
            run_path = root / batch.make_plan(manifest, root)["jobs"][0]["run"]
            run_path.parent.mkdir(parents=True, exist_ok=True)
            run_path.write_text("{}")
            with self.assertRaises(ValidationError):
                batch.run_batch(manifest, root, state, host=host)
            self.assertFalse(state.exists())
            self.assertEqual(host.actions, [])
            self.assertEqual(run_path.read_text(), "{}")

    def test_orphan_batch_evidence_rejected_before_state_created(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, state, host, _ = self.fixture(root)
            run_path = root / batch.make_plan(manifest, root)["jobs"][0]["run"]
            evidence = run_path.with_name(run_path.name + ".production")
            evidence.mkdir(parents=True)
            (evidence / "unfinished").write_text("ambiguous call")
            with self.assertRaises(ValidationError):
                batch.run_batch(manifest, root, state, host=host)
            self.assertFalse(state.exists())
            self.assertFalse(run_path.exists())
            self.assertEqual(host.actions, [])

    def test_standalone_orphan_evidence_does_not_initialize_new_run(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            asset, edit, run, _ = fixtures.V06IntegrationTests()._init(root)
            run.unlink()
            evidence = run.with_name(run.name + ".production")
            evidence.mkdir()
            (evidence / "0000-imagegen_edit").mkdir()
            host = StubHost((root / "master.png").read_bytes())
            with self.assertRaises(ValidationError):
                autopilot.drive(asset, edit, root, run, host=host)
            self.assertFalse(run.exists())
            self.assertEqual(host.actions, [])

    def test_standalone_resume_rejects_same_contents_from_different_spec_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            asset, edit, run, _ = fixtures.V06IntegrationTests()._init(root)
            run.unlink()
            host = StubHost((root / "master.png").read_bytes())
            self.assertEqual(autopilot.drive(asset, edit, root, run, host=host)["state"], "ACCEPTED")
            other = root / "other-edit.toml"
            shutil.copyfile(edit, other)
            followup = StubHost(host.image)
            with self.assertRaises(ValidationError):
                autopilot.drive(asset, other, root, run, resume=True, host=followup)
            self.assertEqual(followup.actions, [])



    def test_accepted_batch_deleted_or_replaced_png_blocks_without_model_retry(self):
        for failure in ("removed", "corrupt"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                manifest, state, host, _ = self.fixture(root)
                batch.run_batch(manifest, root, state, host=host)
                run_path = root / batch.make_plan(manifest, root)["jobs"][0]["run"]
                run = json.loads(run_path.read_text())
                source = root / run["current_receipt"]["result"]["path"]
                if failure == "removed":
                    source.unlink()
                else:
                    source.write_bytes(b"not-an-image")
                followup = StubHost(host.image)
                result = batch.run_batch(manifest, root, state, resume=True, host=followup)
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(result["counts"]["ERROR"], 1)
                self.assertEqual(followup.actions, [])

    def test_accepted_batch_receipt_tamper_blocks_without_host(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, state, host, _ = self.fixture(root)
            batch.run_batch(manifest, root, state, host=host)
            run_path = root / batch.make_plan(manifest, root)["jobs"][0]["run"]
            run = json.loads(run_path.read_text())
            run["current_receipt"]["result_sha256"] = "0" * 64
            run_path.write_text(json.dumps(run))
            followup = StubHost(host.image)
            result = batch.run_batch(manifest, root, state, resume=True, host=followup)
            self.assertEqual(result["counts"]["ERROR"], 1)
            self.assertEqual(followup.actions, [])


    def test_status_cli_does_not_report_invalid_accepted_run_as_success(self):
        for failure in ("missing_png", "changed_rights"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                manifest, state, host, rights = self.fixture(root)
                batch.run_batch(manifest, root, state, host=host)
                if failure == "missing_png":
                    run_path = root / batch.make_plan(manifest, root)["jobs"][0]["run"]
                    accepted = json.loads(run_path.read_text())
                    (root / accepted["current_receipt"]["result"]["path"]).unlink()
                else:
                    rights.write_text("changed source rights")
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    rc = batch.main(["status", "--state", str(state)])
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(output.getvalue())["state"], "ERROR")


    def test_two_jobs_same_specs_must_not_accept_swapped_run_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest, state, host, _ = batch_fixtures.BatchTests().fixture(root, jobs=2)
            self.assertEqual(batch.run_batch(manifest, root, state, host=host)["counts"]["ACCEPTED"], 2)
            specs = batch.make_plan(manifest, root)["jobs"]
            run_a, run_b = (root / spec["run"] for spec in specs)
            original_a, original_b = run_a.read_bytes(), run_b.read_bytes()
            run_a.write_bytes(original_b)
            run_b.write_bytes(original_a)
            followup = StubHost(host.image)
            checked = batch.run_batch(manifest, root, state, resume=True, host=followup)
            self.assertEqual(checked["state"], "BLOCKED")
            self.assertEqual(checked["counts"]["ERROR"], 2)
            self.assertEqual(followup.actions, [])

if __name__ == "__main__":
    unittest.main()
