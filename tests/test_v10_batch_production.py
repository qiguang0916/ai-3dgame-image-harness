"""v0.10 offline contract tests; stub Host != native model provenance."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from artifact_integrity import sha256_file
import batch_production as batch
import cli
import test_v06_integration as fixtures
from test_v09_autopilot import StubHost
from validate_project import ValidationError

class BatchTests(unittest.TestCase):
    def fixture(self, root, jobs=1):
        asset, edit, _, _ = fixtures.V06IntegrationTests()._init(root)
        rights = root / "rights-proof.txt"
        rights.write_text("Synthetic owner's explicit commercial source-rights record\n")
        review = {
            "basis": "user_owned", "license_id": "USER_OWNED",
            "review_status": "REVIEWED_FOR_COMMERCIAL_USE",
            "commercial_use_reviewed": True,
            "reviewer": "Fixture responsible reviewer",
            "evidence": {"path": rights.name, "sha256": sha256_file(rights)},
        }
        path = root / "batch.json"
        path.write_text(json.dumps({"schema_version": 1, "batch_id": "BATCH_001", "jobs": [
            {"id": f"JOB_{i}", "asset": asset.name, "edit": edit.name, "rights": review}
            for i in range(jobs)
        ]}))
        state = root / "batch-state.json"
        return path, state, StubHost((root / "master.png").read_bytes()), rights

    def modify(self, manifest, fn):
        value = json.loads(manifest.read_text())
        fn(value)
        manifest.write_text(json.dumps(value))

    def test_preflight_pause_resume_no_duplicate_model_calls(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m, s, host, _ = self.fixture(root)
            self.assertEqual(batch.make_plan(m, root)["jobs"][0]["preflight"], "READY")
            first = batch.run_batch(m, root, s, host=host, max_actions=1)
            self.assertEqual(first["state"], "IN_PROGRESS")
            self.assertEqual(first["counts"]["PAUSED"], 1)
            self.assertEqual(host.actions, ["imagegen_edit"])
            second = batch.run_batch(m, root, s, resume=True, host=host)
            self.assertEqual(second["state"], "ASSETS_ACCEPTED_NOT_STEAM_CERTIFIED")
            self.assertFalse(second["commercial_release_certified"])
            self.assertEqual(host.actions, ["imagegen_edit", "visual_qa"])
            batch.run_batch(m, root, s, resume=True, host=host)
            self.assertEqual(len(host.actions), 2)
            with self.assertRaises(ValidationError):
                batch.run_batch(m, root, s, host=host)

    def test_two_jobs_bounded_then_resume(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m, s, host, _ = self.fixture(root, jobs=2)
            first = batch.run_batch(m, root, s, max_jobs=1, host=host)
            self.assertEqual(first["counts"]["PENDING"], 1)
            self.assertEqual(first["counts"]["ACCEPTED"], 1)
            self.assertEqual(len(host.actions), 2)
            second = batch.run_batch(m, root, s, resume=True, host=host)
            self.assertEqual(second["counts"]["ACCEPTED"], 2)
            self.assertEqual(len(host.actions), 4)

    def test_crash_between_run_accept_and_state_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m, s, host, _ = self.fixture(root)
            batch.run_batch(m, root, s, host=host)
            state = json.loads(s.read_text())
            state["jobs"][0]["status"] = "PAUSED"
            s.write_text(json.dumps(state))
            replacement = StubHost(host.image)
            self.assertEqual(batch.run_batch(m, root, s, resume=True, host=replacement)["counts"]["ACCEPTED"], 1)
            self.assertEqual(replacement.actions, [])

    def test_license_missing_nc_or_tampered_blocks_before_model(self):
        changes = [
            lambda x: x["jobs"][0]["rights"].update(
                basis="commercial_licensed", license_id="CC-BY-NC-4.0"),
            lambda x: x["jobs"][0]["rights"].update(commercial_use_reviewed=False),
            lambda x: x["jobs"][0]["rights"].update(reviewer=""),
            lambda x: x["jobs"][0]["rights"]["evidence"].update(sha256="0"*64),
            lambda x: x["jobs"][0]["rights"]["evidence"].update(path="../bad.txt"),
            lambda x: x["jobs"][0].update(asset="../escape.toml"),
            lambda x: x["jobs"].append(dict(x["jobs"][0])),
        ]
        for mutate in changes:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                m, s, host, _ = self.fixture(root)
                self.modify(m, mutate)
                with self.assertRaises(ValidationError):
                    batch.run_batch(m, root, s, host=host)
                self.assertFalse(s.exists())
                self.assertEqual(host.actions, [])

    def test_cc_by_requires_attribution(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m, s, host, _ = self.fixture(root)
            self.modify(m, lambda x: x["jobs"][0]["rights"].update(
                basis="commercial_licensed", license_id="CC-BY-4.0"))
            with self.assertRaises(ValidationError):
                batch.make_plan(m, root)
            self.modify(m, lambda x: x["jobs"][0]["rights"].update(
                attribution="Author credit; https://example.com/illustration"))
            outcome = batch.run_batch(m, root, s, host=host, max_actions=1)
            self.assertEqual(outcome["counts"]["PAUSED"], 1)
            self.assertEqual(host.actions, ["imagegen_edit"])

    def test_source_mutation_prevents_resume(self):
        for kind in ("manifest", "rights", "asset"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                m, s, host, rights = self.fixture(root)
                batch.run_batch(m, root, s, host=host, max_actions=1)
                if kind == "manifest":
                    self.modify(m, lambda x: x.update(new_field="tampered"))
                elif kind == "rights":
                    rights.write_text("Changed")
                else:
                    f = root / "asset.toml"
                    f.write_text(f.read_text() + "\n")
                with self.assertRaises(ValidationError):
                    batch.run_batch(m, root, s, resume=True, host=host)
                self.assertEqual(len(host.actions), 1)

    def test_reject_swapped_accepted_run_and_do_not_reinvoke_host(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m, s, host, _ = self.fixture(root)
            batch.run_batch(m, root, s, host=host)
            plan = batch.make_plan(m, root)
            run_file = root / plan["jobs"][0]["run"]
            run = json.loads(run_file.read_text())
            run["asset_document_path"] = "unrelated/asset.toml"
            run_file.write_text(json.dumps(run))
            state = json.loads(s.read_text())
            state["jobs"][0]["status"] = "PAUSED"
            s.write_text(json.dumps(state))
            new_host = StubHost(host.image)
            outcome = batch.run_batch(m, root, s, resume=True, host=new_host)
            self.assertEqual(outcome["counts"]["ERROR"], 1)
            self.assertEqual(new_host.actions, [])
            with self.assertRaises(ValidationError):
                batch.stage_unity(m, root, s, root / "UnityStage")

    def test_unity_stage_copy_integrity_with_mocked_audit(self):
        # Synthetic stub: tests immutable file staging, NOT real ImageGen certification.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m, s, host, _ = self.fixture(root)
            batch.run_batch(m, root, s, host=host)
            out = root / "UnityStage"
            with patch("batch_production.audit_run", return_value={"status": "PASS"}):
                staged = batch.stage_unity(m, root, s, out)
            self.assertEqual(staged["state"], "STAGED_NOT_UNITY_VERIFIED")
            info = json.loads((out / "unity-staging-manifest.json").read_text())
            self.assertFalse(info["commercial_release_certified"])
            self.assertEqual(info["assets"][0]["sha256"], sha256_file(out / "JOB_0.png"))
            with patch("batch_production.audit_run", return_value={"status": "PASS"}):
                with self.assertRaises(ValidationError):
                    batch.stage_unity(m, root, s, out)

    def test_synthetic_host_cannot_stage_unity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m, s, host, _ = self.fixture(root)
            batch.run_batch(m, root, s, host=host)
            output = root / "UnityStage"
            with self.assertRaises(ValidationError):
                batch.stage_unity(m, root, s, output)
            self.assertFalse(output.exists())

    def test_cli_read_only_validate_and_status(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m, s, host, _ = self.fixture(root)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = cli.main(["batch", "validate", "--manifest", str(m), "--workspace-root", str(root)])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out.getvalue())["state"], "VALID")
            batch.run_batch(m, root, s, max_actions=1, host=host)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = cli.main(["batch", "status", "--state", str(s)])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out.getvalue())["counts"]["PAUSED"], 1)

if __name__ == "__main__":
    unittest.main()
