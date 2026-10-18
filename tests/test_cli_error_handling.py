from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliErrorHandlingTests(unittest.TestCase):
    def test_invalid_topology_returns_clean_validation_error(self) -> None:
        content = """
document_type = "asset_manifest"
schema_version = 1
asset_id = "A"
asset_type = "prop"
status = "active"
primary_master = "MASTER"

[locks]
hard = ["identity"]
soft = []

[topology]
forbid_extra_components = true

[[topology.components]]
id = "body"
required = true
count = 1

[[topology.relationships]]
id = "broken"
type = "unsupported_relation"
members = ["body", "body"]
required = true

[[references]]
id = "MASTER"
path = "master.png"
state = "approved"
priority = 100
roles = ["identity"]
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.toml"
            path.write_text(content, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/validate_project.py"),
                    str(path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(1, result.returncode)
        self.assertIn("ERROR:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
