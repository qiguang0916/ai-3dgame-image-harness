"""Evidence-only Unity Player capture validation, no screen recording."""
from __future__ import annotations

import json
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from unity_player_capture import inspect_capture, verify_existing_report, EXPECTED
from artifact_integrity import sha256_file


class PlayerCaptureEvidenceTests(unittest.TestCase):
    def fixture(self,folder):
        root=Path(folder)
        app=root/"Workshop.app"
        (app/"Contents/MacOS").mkdir(parents=True)
        executable=app/"Contents/MacOS"/"Workshop"
        executable.write_bytes(b"test-only executable")
        with (app/"Contents/Info.plist").open("wb") as f:
            plistlib.dump({"CFBundleExecutable":"Workshop"},f)
        out=root/"proof"
        images=out/"captured"
        images.mkdir(parents=True)
        for n in EXPECTED:
            Image.new("RGB",(1440,900),(90,90,90)).save(images/n)
        log=out/"player.log"
        log.write_text("\n".join([
            "MINIMUM_LOOP_READY approved=TEST",
            f"INSPECT_HTML_QA_CAPTURE_A {images}/inspection-html-A-2880x1800.png",
            f"INSPECT_HTML_QA_CAPTURE_B {images}/inspection-html-B-2880x1800.png",
        ])+"\n",encoding="utf8")
        return app,out

    def test_live_files_require_three_real_images_and_engine_markers(self):
        with tempfile.TemporaryDirectory() as d:
            app,out=self.fixture(d)
            got=inspect_capture(app,out)
            self.assertEqual("PASS",got["capture_status"])
            self.assertEqual(3,len(got["screenshots"]))
            self.assertEqual("BLOCKED",got["seven_category_release_status"])
            self.assertFalse(got["steam_approved"])

    def test_missing_capture_and_fake_log_are_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            app,out=self.fixture(d)
            (out/"captured"/EXPECTED[-1]).unlink()
            got=inspect_capture(app,out)
            self.assertEqual("BLOCKED",got["capture_status"])
            (out/"captured"/EXPECTED[-1]).touch()
            (out/"player.log").write_text("a fabricated claim: all PASS")
            got=inspect_capture(app,out)
            self.assertEqual("BLOCKED",got["capture_status"])

    def test_report_digest_revalidation_detects_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            app,out=self.fixture(d)
            good=inspect_capture(app,out)
            (out/"report.json").write_text(json.dumps(good))
            self.assertEqual("PASS",verify_existing_report(app,out)["capture_status"])
            Image.new("RGB",(1440,900),(10,20,30)).save(out/"captured"/EXPECTED[0])
            result=verify_existing_report(app,out)
            self.assertEqual("BLOCKED",result["capture_status"])
            self.assertIn("digest mismatch",str(result["failures"]))

    def test_wrong_executable_digest_blocks_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            app,out=self.fixture(d)
            (out/"report.json").write_text(json.dumps(inspect_capture(app,out)))
            (app/"Contents/MacOS/Workshop").write_bytes(b"replaced executable")
            result=verify_existing_report(app,out)
            self.assertEqual("BLOCKED",result["capture_status"])


if __name__=="__main__":
    unittest.main()
