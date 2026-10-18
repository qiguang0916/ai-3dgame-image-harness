from __future__ import annotations

import sys
import unittest
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import execution_loop
import next_action
import validate_project
from artifact_integrity import packet_digest


class HostFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.asset = validate_project.load_document(
            ROOT / "examples" / "KNIFE_001" / "asset.toml"
        ).data
        self.edit = validate_project.load_document(
            ROOT
            / "examples"
            / "KNIFE_001"
            / "edits"
            / "rivets-brushed-silver.toml"
        ).data

    def _auditable_packet(self, run: dict, root: Path) -> dict:
        run["auditable"] = True
        run["workspace_root"] = str(root)
        run["current_receipt"] = None
        packet = {
            "schema_version": 3,
            "run_id": run["run_id"],
            "asset_id": run["asset_id"],
            "request_id": run["request_id"],
            "state": run["state"],
            "iteration": run["iteration"],
            "action": "imagegen_edit",
            "backend": "host_native_imagegen",
            "fallback_policy": "none",
            "input_bindings": [],
            "workspace_root": str(root),
        }
        packet["packet_id"] = packet_digest(packet)
        run["issued_packet"] = {
            "packet_id": packet["packet_id"],
            "action": packet["action"],
            "state": run["state"],
            "iteration": run["iteration"],
        }
        return packet

    def test_host_unavailable_persists_blocked_without_budget_use(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        blocked = execution_loop.mark_blocked(
            run,
            reason_code="host_native_imagegen_unavailable",
            action="imagegen_edit",
            message="Built-in image tool is unavailable.",
            retryable=False,
        )
        self.assertEqual("BLOCKED", blocked["state"])
        self.assertEqual(
            "host_native_imagegen_unavailable",
            blocked["blocker"]["reason_code"],
        )
        self.assertEqual(0, blocked["repair_passes"])
        self.assertEqual(0, blocked["regeneration_passes"])

        packet = next_action.build_action_packet(
            self.asset, self.edit, blocked
        )
        self.assertEqual("report_blocked", packet["action"])
        self.assertEqual(
            "host_native_imagegen_unavailable",
            packet["blocker"]["reason_code"],
        )

    def test_moderation_blocked_is_first_class_blocker(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        blocked = execution_loop.mark_blocked(
            run,
            reason_code="host_native_imagegen_moderation_blocked",
            action="imagegen_edit",
            message="Host safety system blocked the request.",
            retryable=False,
        )
        self.assertEqual("BLOCKED", blocked["state"])
        self.assertFalse(blocked["blocker"]["retryable"])

    def test_missing_generated_result_blocks_formally(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run = execution_loop.init_run(self.asset, self.edit)
            packet = self._auditable_packet(run, root)
            blocked = execution_loop._record_generated_cli(
                run,
                "missing.png",
                dry_run=False,
                packet=packet,
                receipt_path="receipt.json",
                host_attestation="built-in imagegen",
            )
        self.assertEqual("BLOCKED", blocked["state"])
        self.assertEqual(
            "generated_result_missing",
            blocked["blocker"]["reason_code"],
        )

    def test_invalid_generated_result_blocks_formally(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run = execution_loop.init_run(self.asset, self.edit)
            packet = self._auditable_packet(run, root)
            path = root / "bad.png"
            path.write_text("not an image", encoding="utf-8")
            blocked = execution_loop._record_generated_cli(
                run,
                "bad.png",
                dry_run=False,
                packet=packet,
                receipt_path="receipt.json",
                host_attestation="built-in imagegen",
            )
        self.assertEqual("BLOCKED", blocked["state"])
        self.assertEqual(
            "generated_result_unreadable",
            blocked["blocker"]["reason_code"],
        )

    def test_unknown_reason_code_is_rejected(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        with self.assertRaises(validate_project.ValidationError):
            execution_loop.mark_blocked(
                run,
                reason_code="made_up_reason",
                action="imagegen_edit",
                message="bad",
                retryable=False,
            )


if __name__ == "__main__":
    unittest.main()
