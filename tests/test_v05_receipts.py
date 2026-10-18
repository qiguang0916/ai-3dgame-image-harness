from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import artifact_integrity  # noqa: E402
import execution_loop  # noqa: E402
import next_action  # noqa: E402
import runtime_preflight  # noqa: E402
import topology_contract  # noqa: E402
import validate_project  # noqa: E402


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class V05ReceiptTests(unittest.TestCase):
    def _asset(self) -> dict:
        return {
            "document_type": "asset_manifest",
            "schema_version": 1,
            "asset_id": "A",
            "primary_master": "MASTER",
            "locks": {"hard": ["identity"], "soft": []},
            "references": [
                {
                    "id": "MASTER",
                    "path": "refs/master.png",
                    "state": "approved",
                    "roles": ["identity", "geometry"],
                },
                {
                    "id": "SUPPORT",
                    "path": "refs/support.png",
                    "state": "approved",
                    "roles": ["material"],
                },
            ],
        }

    def _edit(self) -> dict:
        return {
            "document_type": "edit_request",
            "schema_version": 1,
            "request_id": "E",
            "asset_id": "A",
            "operation": "local_edit",
            "target": "finish",
            "change": "change finish only",
            "execution": {"edit_target_reference_id": "MASTER"},
            "preserve": {"hard": ["identity"], "soft": []},
            "reference_sufficiency": {
                "required_roles": ["identity", "material"],
                "allow_provisional": False,
                "provisional_fields": [],
                "prohibited_assumptions": [],
            },
            "reference_bindings": [
                {"reference_id": "MASTER", "roles": ["identity"]},
                {"reference_id": "SUPPORT", "roles": ["material"]},
            ],
        }

    def _write_png(self, root: Path, relative: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG_1X1)
        return path

    def _auditable_run(self, root: Path) -> tuple[dict, dict]:
        self._write_png(root, "refs/master.png")
        self._write_png(root, "refs/support.png")
        run = execution_loop.init_run(self._asset(), self._edit(), "RUN_1")
        run["workspace_root"] = str(root.resolve())
        run["auditable"] = True
        run["current_receipt"] = None
        run["preflight"] = runtime_preflight.run_preflight(
            self._asset(), self._edit(), root
        )
        packet = next_action.build_action_packet(
            self._asset(), self._edit(), run
        )
        return run, packet

    def _attestation(self) -> dict:
        return {
            "host": "codex-test-host",
            "backend": "host_native_imagegen",
            "statement": "The packet action was executed without fallback.",
        }

    def _record(
        self,
        root: Path,
        run: dict,
        packet: dict,
    ) -> tuple[dict, dict]:
        result = self._write_png(root, "out/result.png")
        receipt_path = root / "audit/receipt.json"
        updated = execution_loop._record_generated_cli(
            run,
            "out/result.png",
            dry_run=False,
            packet=packet,
            receipt_path=receipt_path,
            host_attestation=self._attestation(),
        )
        return updated, json.loads(receipt_path.read_text(encoding="utf-8"))

    def _qa(self, run: dict) -> dict:
        receipt = run["current_receipt"]
        gates = []
        for name in run["required_hard_gates"]:
            gates.append(
                {
                    "name": name,
                    "severity": "hard",
                    "status": "PASS",
                    "note": "Compared the output with the approved input.",
                    "inspection_method": "pixel_comparison",
                    "reference_digest": receipt["input_bindings"][0]["sha256"],
                }
            )
        return {
            "document_type": "qa_report",
            "schema_version": 1,
            "report_id": "QA_1",
            "asset_id": "A",
            "request_id": "E",
            "run_id": run["run_id"],
            "iteration": run["iteration"],
            "receipt_id": receipt["receipt_id"],
            "result_sha256": receipt["result_sha256"],
            "status": "PASS",
            "summary": "Inspected real pixels.",
            "repair_directives": [],
            "gates": gates,
        }

    def test_workspace_resolution_rejects_escape_and_is_cwd_independent(self) -> None:
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as cwd:
            root = Path(td)
            expected = self._write_png(root, "refs/master.png").resolve()
            before = Path.cwd()
            try:
                os.chdir(cwd)
                self.assertEqual(
                    expected,
                    artifact_integrity.resolve_in_workspace(
                        root, "refs/master.png"
                    ),
                )
            finally:
                os.chdir(before)

            with self.assertRaises(validate_project.ValidationError):
                artifact_integrity.resolve_in_workspace(root, "../escape.png")

    def test_preflight_binds_sha256_and_png_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_png(root, "refs/master.png")
            self._write_png(root, "refs/support.png")
            preflight = runtime_preflight.run_preflight(
                self._asset(), self._edit(), root
            )
            self.assertEqual("PASS", preflight["status"])
            self.assertEqual(str(root.resolve()), preflight["workspace_root"])
            self.assertEqual(64, len(preflight["checks"][0]["sha256"]))
            self.assertEqual(1, preflight["checks"][0]["png"]["width"])
            self.assertEqual(1, preflight["checks"][0]["png"]["height"])

    def test_packet_is_self_identifying_and_binds_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run, packet = self._auditable_run(Path(td))
            self.assertEqual(3, packet["schema_version"])
            self.assertEqual(
                packet["packet_id"],
                artifact_integrity.packet_digest(packet),
            )
            self.assertEqual(run["run_id"], packet["run_id"])
            self.assertEqual(run["iteration"], packet["iteration"])
            self.assertEqual("edit_target", packet["input_bindings"][0]["kind"])
            self.assertEqual(64, len(packet["input_bindings"][0]["sha256"]))
            self.assertEqual(
                str((Path(td) / "refs/master.png").resolve()),
                packet["input_bindings"][0]["resolved_path"],
            )

    def test_short_host_attestation_is_accepted_as_a_statement(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            attestation = execution_loop._load_host_attestation(
                "Built-in imagegen executed this packet without fallback.",
                Path(td),
            )
            self.assertEqual(
                "Built-in imagegen executed this packet without fallback.",
                attestation["statement"],
            )

    def test_receipt_binds_packet_inputs_result_png_time_and_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, packet = self._auditable_run(root)
            updated, receipt = self._record(root, run, packet)
            self.assertEqual("QA_PENDING", updated["state"])
            self.assertEqual(receipt, updated["current_receipt"])
            self.assertEqual(packet["packet_id"], receipt["packet_id"])
            self.assertEqual("imagegen_edit", receipt["action"])
            self.assertEqual(64, len(receipt["result_sha256"]))
            self.assertEqual(1, receipt["result"]["png"]["width"])
            self.assertTrue(receipt["created_at"].endswith("+00:00"))
            self.assertEqual(
                "codex-test-host", receipt["host_attestation"]["host"]
            )

    def test_record_rejects_packet_run_mismatch_or_packet_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, packet = self._auditable_run(root)
            self._write_png(root, "out/result.png")
            for mutation in (
                lambda item: item.__setitem__("run_id", "OTHER"),
                lambda item: item.__setitem__("requested_delta", "tampered"),
                lambda item: item.__setitem__("action", "visual_qa"),
                lambda item: item.__setitem__("fallback_policy", "api"),
            ):
                bad = json.loads(json.dumps(packet))
                mutation(bad)
                with self.subTest(packet=bad):
                    with self.assertRaises(validate_project.ValidationError):
                        execution_loop._record_generated_cli(
                            run,
                            "out/result.png",
                            dry_run=False,
                            packet=bad,
                            receipt_path=root / "receipt.json",
                            host_attestation=self._attestation(),
                        )

    def test_record_rejects_recomputed_tampered_packet(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, packet = self._auditable_run(root)
            self._write_png(root, "out/result.png")
            bad = json.loads(json.dumps(packet))
            bad["requested_delta"] = "attacker-controlled replacement"
            bad["input_bindings"] = []
            bad["packet_id"] = artifact_integrity.packet_digest(bad)
            with self.assertRaisesRegex(
                validate_project.ValidationError, "does not match the action issued"
            ):
                execution_loop._record_generated_cli(
                    run,
                    "out/result.png",
                    dry_run=False,
                    packet=bad,
                    receipt_path=root / "receipt.json",
                    host_attestation=self._attestation(),
                )

    def test_receipt_path_cannot_overwrite_bound_artifact_or_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, packet = self._auditable_run(root)
            self._write_png(root, "out/result.png")
            master = root / "refs/master.png"
            original_master = master.read_bytes()
            with self.assertRaisesRegex(
                validate_project.ValidationError, "collides with a bound artifact"
            ):
                execution_loop._record_generated_cli(
                    run,
                    "out/result.png",
                    dry_run=False,
                    packet=packet,
                    receipt_path=master,
                    host_attestation=self._attestation(),
                )
            self.assertEqual(original_master, master.read_bytes())

            existing = root / "receipt.json"
            existing.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(
                validate_project.ValidationError, "refusing to overwrite"
            ):
                execution_loop._record_generated_cli(
                    run,
                    "out/result.png",
                    dry_run=False,
                    packet=packet,
                    receipt_path=existing,
                    host_attestation=self._attestation(),
                )
            self.assertEqual("keep", existing.read_text(encoding="utf-8"))

    def test_record_rejects_replaced_bound_input(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, packet = self._auditable_run(root)
            self._write_png(root, "out/result.png")
            (root / "refs/master.png").write_bytes(PNG_1X1 + b"changed")
            with self.assertRaises(validate_project.ValidationError):
                execution_loop._record_generated_cli(
                    run,
                    "out/result.png",
                    dry_run=False,
                    packet=packet,
                    receipt_path=root / "receipt.json",
                    host_attestation=self._attestation(),
                )

    def test_real_mark_generated_requires_audit_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, _ = self._auditable_run(root)
            self._write_png(root, "out/result.png")
            with self.assertRaises(validate_project.ValidationError):
                execution_loop._record_generated_cli(
                    run, "out/result.png", dry_run=False
                )

    def test_real_non_auditable_run_is_rejected_even_with_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run = execution_loop.init_run(self._asset(), self._edit(), "RUN_1")
            self._write_png(root, "out/result.png")
            with self.assertRaisesRegex(
                validate_project.ValidationError, "requires an auditable run"
            ):
                execution_loop._record_generated_cli(
                    run,
                    "out/result.png",
                    dry_run=False,
                    packet={"packet_id": "x"},
                    receipt_path=root / "receipt.json",
                    host_attestation=self._attestation(),
                )

    def test_real_cli_requires_audit_arguments_even_for_legacy_run_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_path = root / "run.json"
            result_path = self._write_png(root, "out/result.png")
            execution_loop.save_run(
                run_path,
                execution_loop.init_run(self._asset(), self._edit(), "RUN_1"),
            )
            exit_code = execution_loop.main(
                [
                    "mark-generated",
                    "--run",
                    str(run_path),
                    "--result",
                    str(result_path),
                ]
            )
            self.assertEqual(1, exit_code)
            self.assertEqual(
                "READY", execution_loop.load_run(run_path)["state"]
            )

    def test_qa_must_bind_current_receipt_and_rehash_result(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, packet = self._auditable_run(root)
            run, _ = self._record(root, run, packet)
            qa = self._qa(run)
            accepted = execution_loop.apply_qa(run, qa)
            self.assertEqual("ACCEPTED", accepted["state"])

            for key, wrong in (
                ("run_id", "OTHER"),
                ("iteration", 999),
                ("receipt_id", "bad"),
                ("result_sha256", "0" * 64),
            ):
                bad = json.loads(json.dumps(qa))
                bad[key] = wrong
                with self.subTest(key=key):
                    with self.assertRaises(validate_project.ValidationError):
                        execution_loop.apply_qa(run, bad)

            (root / "out/result.png").write_bytes(PNG_1X1 + b"replaced")
            with self.assertRaises(validate_project.ValidationError):
                execution_loop.apply_qa(run, qa)

    def test_qa_rehashes_bound_reference_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, packet = self._auditable_run(root)
            run, _ = self._record(root, run, packet)
            qa = self._qa(run)
            (root / "refs/master.png").write_bytes(PNG_1X1 + b"replaced")
            with self.assertRaisesRegex(
                validate_project.ValidationError, "input was replaced before QA"
            ):
                execution_loop.apply_qa(run, qa)

    def test_qa_packet_exposes_current_receipt_and_result_binding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, packet = self._auditable_run(root)
            run, receipt = self._record(root, run, packet)

            qa_packet = next_action.build_action_packet(
                self._asset(), self._edit(), run
            )

            self.assertEqual("visual_qa", qa_packet["action"])
            self.assertEqual(receipt["receipt_id"], qa_packet["receipt_id"])
            self.assertEqual(
                receipt["result_sha256"], qa_packet["result_sha256"]
            )
            self.assertEqual(receipt["result"], qa_packet["result_binding"])

    def test_pass_gate_requires_evidence_method_and_reference_or_observation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, packet = self._auditable_run(root)
            run, _ = self._record(root, run, packet)
            qa = self._qa(run)
            gate = qa["gates"][0]
            mutations = (
                lambda item: item.__setitem__("note", ""),
                lambda item: item.__setitem__("inspection_method", ""),
                lambda item: item.pop("reference_digest"),
            )
            for mutation in mutations:
                bad = json.loads(json.dumps(qa))
                mutation(bad["gates"][0])
                with self.subTest(gate=gate):
                    with self.assertRaises(validate_project.ValidationError):
                        execution_loop.apply_qa(run, bad)


if __name__ == "__main__":
    unittest.main()
