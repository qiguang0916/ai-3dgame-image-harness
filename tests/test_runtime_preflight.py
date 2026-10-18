from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import execution_loop
import runtime_preflight
from artifact_integrity import sha256_file


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class RuntimePreflightTests(unittest.TestCase):
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
                "prohibited_assumptions": ["hidden geometry"],
            },
            "reference_bindings": [
                {"reference_id": "MASTER", "roles": ["identity"]},
                {"reference_id": "SUPPORT", "roles": ["material"]},
            ],
        }

    def _write_png(self, root: Path, relative: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG_1X1)

    def test_missing_edit_target_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_png(root, "refs/support.png")
            result = runtime_preflight.run_preflight(
                self._asset(), self._edit(), root
            )
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual("edit_target_missing", result["reason_code"])

    def test_missing_required_support_reference_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_png(root, "refs/master.png")
            result = runtime_preflight.run_preflight(
                self._asset(), self._edit(), root
            )
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual("required_reference_missing", result["reason_code"])

    def test_invalid_image_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_png(root, "refs/master.png")
            bad = root / "refs/support.png"
            bad.parent.mkdir(parents=True, exist_ok=True)
            bad.write_text("not an image", encoding="utf-8")
            result = runtime_preflight.run_preflight(
                self._asset(), self._edit(), root
            )
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual("reference_image_invalid", result["reason_code"])

    def test_declared_reference_digest_mismatch_blocks_real_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_png(root, "refs/master.png")
            self._write_png(root, "refs/support.png")
            asset = self._asset()
            asset["references"][0]["content_sha256"] = sha256_file(
                root / "refs/master.png"
            )
            self.assertEqual(
                "PASS",
                runtime_preflight.run_preflight(asset, self._edit(), root)["status"],
            )

            (root / "refs/master.png").write_bytes(PNG_1X1 + b"replaced")
            result = runtime_preflight.run_preflight(asset, self._edit(), root)
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual("reference_digest_mismatch", result["reason_code"])

    def test_dry_run_allows_missing_fixture_images(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = runtime_preflight.run_preflight(
                self._asset(), self._edit(), Path(td), dry_run=True
            )
            self.assertEqual("PASS", result["status"])
            self.assertTrue(result["dry_run"])

    def test_dry_run_still_enforces_reference_sufficiency(self) -> None:
        edit = self._edit()
        edit["reference_sufficiency"]["required_roles"].append("interface")
        with tempfile.TemporaryDirectory() as td:
            result = runtime_preflight.run_preflight(
                self._asset(), edit, Path(td), dry_run=True
            )
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual(
                "reference_sufficiency_failed",
                result["reason_code"],
            )

    def test_reference_sufficiency_reports_authoritative_and_prohibited(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_png(root, "refs/master.png")
            self._write_png(root, "refs/support.png")
            result = runtime_preflight.run_preflight(
                self._asset(), self._edit(), root
            )
            self.assertEqual("PASS", result["status"])
            self.assertEqual(
                ["identity", "material"],
                result["reference_sufficiency"]["covered_roles"],
            )
            self.assertEqual(
                ["hidden geometry"],
                result["reference_sufficiency"]["prohibited_assumptions"],
            )

    def test_missing_required_role_blocks(self) -> None:
        edit = self._edit()
        edit["reference_sufficiency"]["required_roles"].append("interface")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_png(root, "refs/master.png")
            self._write_png(root, "refs/support.png")
            result = runtime_preflight.run_preflight(
                self._asset(), edit, root
            )
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual(
                "reference_sufficiency_failed",
                result["reason_code"],
            )

    def test_non_approved_support_reference_never_enters_runtime(self) -> None:
        asset = self._asset()
        asset["references"][1]["state"] = "draft"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_png(root, "refs/master.png")
            self._write_png(root, "refs/support.png")
            result = runtime_preflight.run_preflight(
                asset, self._edit(), root
            )
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual(
                "required_reference_missing",
                result["reason_code"],
            )

    def test_real_init_from_paths_blocks_when_example_images_are_absent(self) -> None:
        asset_path = ROOT / "examples/KNIFE_001/asset.toml"
        edit_path = (
            ROOT
            / "examples/KNIFE_001/edits/rivets-brushed-silver.toml"
        )
        run = execution_loop.init_from_paths(
            asset_path,
            edit_path,
            workspace_root=ROOT / "examples/KNIFE_001",
        )
        self.assertEqual("BLOCKED", run["state"])
        self.assertIn(
            run["blocker"]["reason_code"],
            {"edit_target_missing", "required_reference_missing"},
        )


if __name__ == "__main__":
    unittest.main()
