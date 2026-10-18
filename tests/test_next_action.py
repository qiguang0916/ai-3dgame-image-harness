from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import execution_loop  # noqa: E402
import next_action  # noqa: E402
import topology_contract  # noqa: E402
import validate_project  # noqa: E402


class NextActionTests(unittest.TestCase):
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

    def _qa(self, status: str, directives: list[str] | None = None) -> dict:
        required = topology_contract.expected_hard_gates(
            self.asset, self.edit
        )
        gates = [
            {
                "name": name,
                "severity": "hard",
                "status": "PASS",
                "note": "",
            }
            for name in required
        ]
        if status == "REPAIR_MINOR":
            next(
                item
                for item in gates
                if item["name"] == "exact rivet centers"
            )["status"] = "FAIL"
        elif status == "REGENERATE_MAJOR":
            next(
                item
                for item in gates
                if item["name"] == "blade broad silhouette"
            )["status"] = "FAIL"

        qa = {
            "document_type": "qa_report",
            "schema_version": 1,
            "report_id": f"QA_{status}",
            "asset_id": "KNIFE_001",
            "request_id": "KNIFE_001_EDIT_RIVETS_001",
            "status": status,
            "summary": status,
            "repair_directives": directives or [],
            "gates": gates,
        }
        validate_project.validate_document(qa, Path("qa.toml"))
        return qa

    def test_ready_packet_has_explicit_edit_target(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        packet = next_action.build_action_packet(self.asset, self.edit, run)

        self.assertEqual("imagegen_edit", packet["action"])
        self.assertEqual(
            "ASSEMBLED_MASTER",
            packet["edit_target"]["reference_id"],
        )
        self.assertEqual(
            "references/KNIFE_001_ASSEMBLED_MASTER.png",
            packet["edit_target"]["path"],
        )
        self.assertEqual(2, len(packet["references"]))
        self.assertIn("EDIT TARGET:", packet["prompt"])

    def test_qa_pending_packet_requests_visual_qa(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        run = execution_loop.mark_generated(run, "out/knife-v1.png")
        packet = next_action.build_action_packet(self.asset, self.edit, run)

        self.assertEqual("visual_qa", packet["action"])
        self.assertEqual("out/knife-v1.png", packet["result_path"])
        self.assertIn("exact rivet centers", packet["hard_gates"])
        self.assertIn("wood color", packet["soft_gates"])

    def test_repair_packet_uses_failed_result_as_edit_target(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        run = execution_loop.mark_generated(run, "out/knife-v1.png")
        run = execution_loop.apply_qa(
            run,
            self._qa(
                "REPAIR_MINOR",
                ["Restore only the rear rivet center."],
            ),
        )
        packet = next_action.build_action_packet(self.asset, self.edit, run)

        self.assertEqual("imagegen_edit", packet["action"])
        self.assertEqual(
            "failed_generated_result",
            packet["edit_target"]["kind"],
        )
        self.assertEqual("out/knife-v1.png", packet["edit_target"]["path"])
        self.assertIn("CORRECTION DELTA:", packet["prompt"])
        self.assertIn("Restore only the rear rivet center.", packet["prompt"])

    def test_regeneration_packet_returns_to_approved_target(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        run = execution_loop.mark_generated(run, "out/bad.png")
        run = execution_loop.apply_qa(
            run,
            self._qa("REGENERATE_MAJOR"),
        )
        packet = next_action.build_action_packet(self.asset, self.edit, run)

        self.assertEqual("imagegen_edit", packet["action"])
        self.assertEqual(
            "ASSEMBLED_MASTER",
            packet["edit_target"]["reference_id"],
        )
        self.assertEqual(
            "approved_source_not_failed_result",
            packet["restart_policy"],
        )

    def test_accepted_packet_delivers_current_result(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        run = execution_loop.mark_generated(run, "out/final.png")
        run = execution_loop.apply_qa(run, self._qa("PASS"))
        packet = next_action.build_action_packet(self.asset, self.edit, run)

        self.assertEqual("deliver", packet["action"])
        self.assertEqual("out/final.png", packet["result_path"])


if __name__ == "__main__":
    unittest.main()
