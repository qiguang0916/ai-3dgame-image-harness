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


class V04RoutingTests(unittest.TestCase):
    def _asset(self) -> dict:
        return {
            "document_type": "asset_manifest",
            "schema_version": 1,
            "asset_id": "RADIO_001",
            "primary_master": "MASTER",
            "locks": {"hard": ["identity"], "soft": ["lighting"]},
            "qa": {
                "max_repair_passes": 2,
                "max_regeneration_passes": 1,
            },
            "references": [
                {
                    "id": "MASTER",
                    "path": "refs/master.png",
                    "state": "approved",
                    "roles": ["identity", "geometry", "material", "camera"],
                }
            ],
            "topology": {
                "forbid_extra_components": True,
                "components": [
                    {"id": "housing", "required": True, "count": 1},
                    {"id": "knob", "required": True, "count": 2},
                    {"id": "speaker_grille", "required": True, "count": 1},
                ],
                "relationships": [
                    {
                        "id": "grille_mounted_on_housing",
                        "type": "mounted_on",
                        "members": ["speaker_grille", "housing"],
                        "required": True,
                    }
                ],
            },
        }

    def _edit(self) -> dict:
        return {
            "document_type": "edit_request",
            "schema_version": 1,
            "request_id": "EDIT_1",
            "asset_id": "RADIO_001",
            "operation": "local_edit",
            "target": "knob finish",
            "change": "change knob finish only",
            "execution": {"edit_target_reference_id": "MASTER"},
            "preserve": {"hard": ["identity"], "soft": ["lighting"]},
            "reference_sufficiency": {
                "required_roles": ["identity", "geometry"],
                "allow_provisional": False,
                "provisional_fields": [],
                "prohibited_assumptions": ["hidden interior geometry"],
            },
            "reference_bindings": [
                {
                    "reference_id": "MASTER",
                    "roles": ["identity", "geometry", "material", "camera"],
                }
            ],
        }

    def _qa(self, status: str, topology_gate_status: str) -> dict:
        required = topology_contract.expected_hard_gates(
            self._asset(), self._edit()
        )
        return {
            "document_type": "qa_report",
            "schema_version": 1,
            "report_id": "QA_1",
            "asset_id": "RADIO_001",
            "request_id": "EDIT_1",
            "status": status,
            "summary": "",
            "repair_directives": (
                ["Adjust the isolated knob finish only."]
                if status == "REPAIR_MINOR"
                else []
            ),
            "gates": [
                {
                    "name": name,
                    "severity": "hard",
                    "status": (
                        topology_gate_status
                        if name.startswith("topology.")
                        else "PASS"
                    ),
                    "note": "",
                }
                for name in required
            ],
        }

    def test_topology_failure_forces_regeneration(self) -> None:
        run = execution_loop.init_run(self._asset(), self._edit())
        run = execution_loop.mark_generated(run, "out/v1.png")
        qa = self._qa("REPAIR_MINOR", "FAIL")
        validate_project.validate_document(qa, Path("qa.toml"))
        run = execution_loop.apply_qa(run, qa)
        self.assertEqual("REGENERATE_READY", run["state"])

    def test_required_topology_not_verifiable_blocks(self) -> None:
        run = execution_loop.init_run(self._asset(), self._edit())
        run = execution_loop.mark_generated(run, "out/v1.png")
        qa = self._qa("BLOCKED", "NOT_VERIFIABLE")
        validate_project.validate_document(qa, Path("qa.toml"))
        run = execution_loop.apply_qa(run, qa)
        self.assertEqual("BLOCKED", run["state"])
        self.assertEqual(
            "visual_inspection_unavailable",
            run["blocker"]["reason_code"],
        )
        self.assertEqual("QA_1", run["last_qa"]["report_id"])
        self.assertEqual("BLOCKED", run["last_qa"]["status"])

    def test_ready_packet_contains_v04_contracts(self) -> None:
        run = execution_loop.init_run(self._asset(), self._edit())
        packet = next_action.build_action_packet(
            self._asset(), self._edit(), run
        )
        self.assertEqual(2, packet["schema_version"])
        self.assertEqual("none", packet["fallback_policy"])
        self.assertEqual("local_edit", packet["operation"])
        self.assertIn("required_components", packet["topology"])
        self.assertEqual(
            "sufficient",
            packet["reference_sufficiency"]["status"],
        )
        self.assertIn(
            "hidden interior geometry",
            packet["knowledge"]["prohibited_assumptions"],
        )
        self.assertEqual(2, packet["budget"]["repair_passes_max"])

    def test_blocked_packet_never_returns_imagegen_action(self) -> None:
        run = execution_loop.init_run(self._asset(), self._edit())
        run = execution_loop.mark_blocked(
            run,
            reason_code="host_native_imagegen_failed",
            action="imagegen_edit",
            message="Host call failed.",
            retryable=True,
        )
        packet = next_action.build_action_packet(
            self._asset(), self._edit(), run
        )
        self.assertEqual("report_blocked", packet["action"])
        self.assertEqual(
            "host_native_imagegen_failed",
            packet["blocker"]["reason_code"],
        )


if __name__ == "__main__":
    unittest.main()
