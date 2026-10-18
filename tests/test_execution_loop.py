from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import execution_loop  # noqa: E402
import topology_contract  # noqa: E402
import validate_project  # noqa: E402


class ExecutionLoopTests(unittest.TestCase):
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
            target = "exact rivet centers"
            next(item for item in gates if item["name"] == target)[
                "status"
            ] = "FAIL"
        elif status == "REGENERATE_MAJOR":
            target = "blade broad silhouette"
            next(item for item in gates if item["name"] == target)[
                "status"
            ] = "FAIL"

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

    def test_init_local_edit_uses_host_native_edit(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        self.assertEqual("READY", run["state"])
        self.assertEqual("edit", run["execution_mode"])
        self.assertEqual("invoke_imagegen_edit", run["next_action"])
        self.assertEqual(2, run["max_repair_passes"])
        self.assertEqual(1, run["max_regeneration_passes"])

    def test_pass_accepts_run(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        run = execution_loop.mark_generated(run, "out/rivets-v1.png")
        self.assertEqual("QA_PENDING", run["state"])

        run = execution_loop.apply_qa(run, self._qa("PASS"))
        self.assertEqual("ACCEPTED", run["state"])
        self.assertEqual("deliver_final_asset", run["next_action"])

    def test_minor_failure_routes_to_repair(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        run = execution_loop.mark_generated(run, "out/rivets-v1.png")
        run = execution_loop.apply_qa(
            run,
            self._qa(
                "REPAIR_MINOR",
                ["Restore only the rear rivet center to the approved position."],
            ),
        )

        self.assertEqual("REPAIR_READY", run["state"])
        self.assertEqual(1, run["repair_passes"])
        self.assertEqual(
            "compile_repair_brief_and_invoke_imagegen_edit",
            run["next_action"],
        )

    def test_repair_budget_is_bounded(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)

        for index in range(2):
            run = execution_loop.mark_generated(run, f"out/repair-{index}.png")
            run = execution_loop.apply_qa(
                run,
                self._qa(
                    "REPAIR_MINOR",
                    ["Restore the failed hard gate only."],
                ),
            )
            self.assertEqual("REPAIR_READY", run["state"])

        run = execution_loop.mark_generated(run, "out/repair-final.png")
        run = execution_loop.apply_qa(
            run,
            self._qa(
                "REPAIR_MINOR",
                ["Restore the failed hard gate only."],
            ),
        )

        self.assertEqual("BLOCKED", run["state"])
        self.assertEqual(
            "report_repair_budget_exhausted",
            run["next_action"],
        )

    def test_major_failure_restarts_from_master(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        run = execution_loop.mark_generated(run, "out/bad-v1.png")
        run = execution_loop.apply_qa(run, self._qa("REGENERATE_MAJOR"))

        self.assertEqual("REGENERATE_READY", run["state"])
        self.assertEqual(1, run["regeneration_passes"])
        self.assertEqual(
            "restart_from_approved_master_with_original_brief",
            run["next_action"],
        )

    def test_regeneration_budget_is_bounded(self) -> None:
        run = execution_loop.init_run(self.asset, self.edit)
        run = execution_loop.mark_generated(run, "out/bad-v1.png")
        run = execution_loop.apply_qa(run, self._qa("REGENERATE_MAJOR"))
        run = execution_loop.mark_generated(run, "out/bad-v2.png")
        run = execution_loop.apply_qa(run, self._qa("REGENERATE_MAJOR"))

        self.assertEqual("BLOCKED", run["state"])
        self.assertEqual(
            "report_regeneration_budget_exhausted",
            run["next_action"],
        )


if __name__ == "__main__":
    unittest.main()
