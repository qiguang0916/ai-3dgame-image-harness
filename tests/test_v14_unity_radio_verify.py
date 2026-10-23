"""Offline-only v0.14 Unity Editor RADIO contract tests; no real Unity or Player in CI."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from validate_project import ValidationError
from v14_unity_radio_verify import compare_rendered_pixels,json_object,main
from v14_unity_radio_prepare import prepare


class UnityV14RadioTests(unittest.TestCase):
    def images(self,root:Path, variant:str="normal"):
        from PIL import Image
        import numpy as np
        w,h=300,200
        yy,xx=np.mgrid[0:h,0:w]
        arr=np.zeros((h,w,3),dtype=np.uint8)
        arr[:,:,0]=np.clip(100+xx*.47+((xx//15)%2)*13,0,255)
        arr[:,:,1]=np.clip(45+yy*.7+((yy//9)%2)*10,0,255)
        arr[:,:,2]=np.clip(52+xx*.33+yy*.12,0,255)
        sample=Image.fromarray(arr,"RGB")
        source=root/"source.png"
        sample.save(source)
        canvas=Image.new("RGB",(800,600),(17,21,24))
        render=sample.resize((600,400),Image.Resampling.BILINEAR)
        if variant=="mirror":
            render=render.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif variant=="vertical":
            render=render.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        elif variant=="other":
            opposite=np.copy(arr)
            opposite[:,:,0]=np.maximum(0,255-opposite[:,:,0])
            render=Image.fromarray(opposite,"RGB").resize((600,400))
        if variant!="blank":
            canvas.paste(render,(100,100))
        path=root/"unity_editor.png"
        canvas.save(path)
        return source,path

    def test_correctly_oriented_nonflat_editor_screenshot(self):
        with tempfile.TemporaryDirectory() as temp:
            source,screenshot=self.images(Path(temp))
            observed=compare_rendered_pixels(source,screenshot)
            self.assertEqual(observed["status"],"EDITOR_RENDER_SOURCE_ORIENTATION_AND_PIXELS_MATCH")
            self.assertEqual(observed["rendered_bbox_xyxy"],[100,100,700,500])
            self.assertLess(observed["rgb_mean_absolute_error_original"],2)
            self.assertGreater(observed["rgb_mean_absolute_error_mirror"],12)

    def test_black_background_screenshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            src,shot=self.images(Path(temp),variant="blank")
            with self.assertRaisesRegex(ValidationError,"no meaningful asset pixels"):
                compare_rendered_pixels(src,shot)

    def test_mirrored_editor_screenshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            src,shot=self.images(Path(temp),variant="mirror")
            with self.assertRaises(ValidationError):
                compare_rendered_pixels(src,shot)

    def test_upsidedown_editor_screenshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            src,shot=self.images(Path(temp),variant="vertical")
            with self.assertRaises(ValidationError):
                compare_rendered_pixels(src,shot)

    def test_unrelated_photo_screenshot_fails_even_with_valid_size(self):
        with tempfile.TemporaryDirectory() as temp:
            src,shot=self.images(Path(temp),variant="other")
            with self.assertRaisesRegex(ValidationError,"does not faithfully show source"):
                compare_rendered_pixels(src,shot)

    def test_missing_or_symlinked_report_not_trusted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValidationError):
                json_object(root/"missing.json")
            record=root/"record.json";record.write_text(json.dumps({"status":"PASS"}))
            alias=root/"alias.json";alias.symlink_to(record)
            with self.assertRaisesRegex(ValidationError,"missing, symlinked"):
                json_object(alias)
            record.write_text("[]")
            with self.assertRaises(ValidationError):
                json_object(record)

    def test_report_write_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            target=root/"existing.json"
            target.write_text("OWNER_EVIDENCE_DO_NOT_TOUCH")
            code=main(["--project",str(root),"--evidence",str(root),
                       "--run",str(root/"missing_run.json"),
                       "--expected-sha","0"*64,
                       "--editor-log",str(root/"missing.log"),
                       "--output",str(target)])
            self.assertEqual(code,2)
            self.assertEqual(target.read_text(),"OWNER_EVIDENCE_DO_NOT_TOUCH")

    def test_staging_refuses_any_nonisolated_project_before_private_io(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            project=root/"second-life-workshop"
            (project/"Assets").mkdir(parents=True)
            (project/"ProjectSettings").mkdir()
            (project/"ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.3f1\n")
            (project/"Assets/Existing.cs").write_text("user game code")
            with self.assertRaises(ValidationError):
                prepare(ROOT,project,root/"nonexistent-native-run.json","0"*64)
            self.assertEqual((project/"Assets/Existing.cs").read_text(),"user game code")

    def test_staging_refuses_dirty_isolated_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            project=root/"image-harness-unity-v14-radio-testfixture"
            (project/"Assets").mkdir(parents=True)
            (project/"ProjectSettings").mkdir()
            (project/"ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.3f1\n")
            (project/"Assets/Existing.cs").write_text("must not overwrite")
            with self.assertRaisesRegex(ValidationError,"Assets must be empty"):
                prepare(ROOT,project,root/"missing-run.json","0"*64)
            self.assertEqual((project/"Assets/Existing.cs").read_text(),"must not overwrite")

    def test_staging_rejects_unsupported_editor_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            project=root/"image-harness-unity-v14-radio-testfixture"
            (project/"Assets").mkdir(parents=True)
            (project/"ProjectSettings").mkdir()
            (project/"ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 2020.3.0f1\n")
            with self.assertRaises(ValidationError):
                prepare(ROOT,project,root/"missing-run.json","0"*64)

    def test_wrong_sha_is_rejected_without_touching_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            project=root/"image-harness-unity-v14-radio-testfixture"
            (project/"Assets").mkdir(parents=True)
            (project/"ProjectSettings").mkdir()
            (project/"ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.3f1\n")
            with self.assertRaisesRegex(ValidationError,"lowercase 64-character SHA"):
                prepare(ROOT,project,root/"missing-run.json","NOT_A_SHA")
            self.assertEqual(list((project/"Assets").iterdir()),[])


if __name__=="__main__":
    unittest.main()

