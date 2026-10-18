from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_root_skill_description_is_trigger_only(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r"^description:\s*(.+)$", text, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        description = match.group(1).strip()
        self.assertTrue(description.startswith("Use when"))
        self.assertLess(len(description), 500)

    def test_required_reference_docs_exist(self) -> None:
        required = [
            "references/runtime-preflight.md",
            "references/topology-contract.md",
            "references/reference-sufficiency.md",
            "references/visual-qa-contract.md",
            "references/host-failure-protocol.md",
        ]
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_root_skill_points_to_progressive_disclosure_docs(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for relative in (
            "references/runtime-preflight.md",
            "references/topology-contract.md",
            "references/reference-sufficiency.md",
            "references/visual-qa-contract.md",
            "references/host-failure-protocol.md",
        ):
            self.assertIn(relative, text)

    def test_visual_qa_skill_exposes_not_verifiable_contract(self) -> None:
        text = (
            ROOT / "skills/visual-qa/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("NOT_VERIFIABLE", text)
        self.assertIn("references/visual-qa-contract.md", text)

    def test_execution_loop_skill_exposes_preflight_and_blocker_commands(self) -> None:
        text = (
            ROOT / "skills/execution-loop/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("--dry-run", text)
        self.assertIn("mark-blocked", text)
        self.assertIn("references/runtime-preflight.md", text)
        self.assertIn("references/host-failure-protocol.md", text)

    def test_host_action_protocol_documents_v2_contract_fields(self) -> None:
        text = (
            ROOT / "references/host-action-protocol.md"
        ).read_text(encoding="utf-8")
        for term in (
            "reference_sufficiency",
            "authoritative_facts",
            "provisional_fields",
            "prohibited_assumptions",
            "fallback_policy",
            "required_hard_gates",
        ):
            self.assertIn(term, text)


if __name__ == "__main__":
    unittest.main()
