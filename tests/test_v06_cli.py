from __future__ import annotations
import json
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/"bin"/"ai-3dgame-image-harness"

class ImageHarnessCliTests(unittest.TestCase):
    def test_cli_name_and_doctor(self):
        version=subprocess.run([str(CLI),"version"],capture_output=True,text=True)
        self.assertEqual(0,version.returncode,version.stderr)
        self.assertIn("ai-3dgame-image-harness",version.stdout)
        result=subprocess.run([str(CLI),"doctor"],capture_output=True,text=True)
        self.assertIn(result.returncode,{0,2})
        self.assertEqual("NOT_VERIFIED (must be checked inside Codex host)",
                         json.loads(result.stdout)["real_host_imagegen"])

    def test_bootstrap_example_is_statically_valid(self):
        result=subprocess.run([str(CLI),"validate",
              str(ROOT/"examples"/"BOOTSTRAP_PROP_001")],
              capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr)

if __name__=="__main__":unittest.main()
