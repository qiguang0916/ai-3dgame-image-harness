"""Offline bridge regression: does NOT certify an actual Unity Player build."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from artifact_integrity import sha256_file
from unity_release_bridge import REQUIRED_CATEGORIES, verify_test_harness_release
from commercial_art_gate import _unity_evidence


class TestUnityEvidenceBridge(unittest.TestCase):
    COMMIT='a'*40

    def fixture(self, root:Path) -> dict:
        source={
            'unity-editor':'live-unity-mcp',
            'game-physics':'live-unity-mcp',
            'player-visual':'real-macos-unity-player',
            'os-input':'native-macos-input',
            'paper-cut':'real-macos-unity-player',
            'performance':'real-macos-unity-player',
            'nondev-build':'real-macos-unity-player',
        }
        evidence=[]
        for idx,category in enumerate(REQUIRED_CATEGORIES):
            if category=='player-visual':
                p=root/'player-capture.png'
                Image.new('RGB',(1024,576),'white').save(p)
            else:
                p=root/(category+'.txt')
                p.write_text('Synthetic fixture for '+category)
            evidence.append({
                'category':category,
                'passed':True,
                'verified':True,
                'sha256':sha256_file(p),
                'commitSha':self.COMMIT,
                'source':source[category],
                'capturedAt':datetime.now(timezone.utc).isoformat(),
                'artifactUri':p.as_uri(),
                **({'developmentBuild':False} if category=='nondev-build' else {})
            })
        return {'expectedCommit':self.COMMIT,'evidence':evidence}

    def test_complete_same_commit_7_categories(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);report=verify_test_harness_release(self.fixture(root),expected_commit=self.COMMIT)
            self.assertEqual('PASS',report['status'])
            self.assertEqual(7,len(report['verified_categories']))
            self.assertEqual(sha256_file(root/'player-capture.png'),report['player_capture']['sha256'])
            self.assertFalse(report['steam_approved'])

    def test_mismatch_failed_or_missing_any_category_blocks(self):
        for mode in ('missing','failed','wrong_commit','wrong_sha','wrong_source',
                     'dev_build','unverified','wrong_time','not_image','http_uri'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as raw:
                root=Path(raw);doc=self.fixture(root)
                if mode=='missing':doc['evidence'].pop()
                elif mode=='failed':doc['evidence'][0]['passed']=False
                elif mode=='wrong_commit':doc['evidence'][0]['commitSha']='b'*40
                elif mode=='wrong_sha':doc['evidence'][0]['sha256']='0'*64
                elif mode=='wrong_source':doc['evidence'][0]['source']='simulation'
                elif mode=='dev_build':doc['evidence'][-1]['developmentBuild']=True
                elif mode=='unverified':doc['evidence'][0]['verified']=False
                elif mode=='wrong_time':doc['evidence'][0]['capturedAt']='not-a-time'
                elif mode=='not_image':
                    p=root/'player-fake.txt';p.write_text('not a player screenshot')
                    doc['evidence'][2]['artifactUri']=p.as_uri()
                    doc['evidence'][2]['sha256']=sha256_file(p)
                else:doc['evidence'][0]['artifactUri']='https://attacker.invalid/forged.json'
                result=verify_test_harness_release(doc,expected_commit=self.COMMIT)
                self.assertEqual('BLOCKED',result['status'])
                self.assertTrue(result['failures'])

    def test_commercial_unity_gate_requires_original_release_manifest_and_capture_match(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);data=self.fixture(root)
            proof=root/'release.json';proof.write_text(json.dumps(data))
            note=root/'review.txt';note.write_text('Synthetic test review, not actual user consent')
            integration={
                'status':'PASS','reviewer':'test_fixture',
                'path':note.name,'sha256':sha256_file(note),
                'engine':'Unity','capture_origin':'unity_player','build_id':self.COMMIT,
                'player_capture':{
                    'path':'player-capture.png','sha256':sha256_file(root/'player-capture.png')},
                'test_harness_release':{'path':proof.name,'sha256':sha256_file(proof)},
            }
            blockers=[]
            _unity_evidence(root,integration,blockers)
            self.assertEqual([],blockers)
            # A forged status without the independently checked manifest fails.
            integration.pop('test_harness_release')
            blockers=[]
            _unity_evidence(root,integration,blockers)
            self.assertTrue(any('release manifest' in x for x in blockers))
            integration['test_harness_release']={'path':proof.name,'sha256':sha256_file(proof)}
            Image.new('RGB',(1024,576),'black').save(root/'player-capture.png')
            blockers=[]
            _unity_evidence(root,integration,blockers)
            self.assertTrue(any('mismatch' in x for x in blockers))


if __name__=='__main__':
    unittest.main()
