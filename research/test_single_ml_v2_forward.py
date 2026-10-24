import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
import single_ml_v2_forward as fw
from single_ml_v2 import FormState

UTC=timezone.utc

class FakePredictor:
    def predict(self,X):
        return np.full(len(X),1.25)

def fixture(kickoff,*,finished=False):
    x={"id":1234,"sportId":1,"startTime":int(kickoff.timestamp()),
       "statusGroup":4 if finished else 1,
       "competitionDisplayName":"League","competitionId":55,
       "homeCompetitor":{"id":77,"name":"Home United"},
       "awayCompetitor":{"id":88,"name":"Away FC"}}
    if finished:
        x["homeCompetitor"]["score"]=2
        x["awayCompetitor"]["score"]=1
    return x

class Feed:
    def __init__(self,rows):
        self.rows=rows
        self.calls=[]
    def __call__(self,first,last,**kwargs):
        from types import SimpleNamespace
        self.calls.append((first,last))
        return SimpleNamespace(ok=True,games=self.rows)

class ForwardTests(unittest.TestCase):
    def setUp(self):
        self.environment=patch.dict(os.environ,{"GITHUB_ACTIONS":"false"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.key=b"X"*32
        self.issued=datetime(2026,10,24,7,0,tzinfo=UTC)
        self.start=datetime(2026,10,25,12,0,tzinfo=UTC)

    def dummy_training(self):
        trained={m:None for m in fw.MODELS}
        trained["machine_learning"]=(FakePredictor(),FakePredictor())
        return FormState(),trained,-.04,self.issued.date()-timedelta(days=1),500

    def test_future_only_football(self):
        good=fixture(self.start)
        rejected=dict(good,sportId=3)
        self.assertIsNone(fw.verified_source_target(rejected,self.issued,self.start+timedelta(hours=2)))
        self.assertIsNone(fw.verified_source_target(fixture(self.start,finished=True),self.issued,self.start+timedelta(hours=2)))
        bad=fixture(self.start)
        bad["homeCompetitor"]["score"]=1
        self.assertIsNone(fw.verified_source_target(bad,self.issued,self.start+timedelta(hours=2)))
        default_zero=fixture(self.start)
        default_zero["homeCompetitor"]["score"]=0
        default_zero["awayCompetitor"]["score"]=0
        self.assertIsNotNone(fw.verified_source_target(default_zero,self.issued,self.start+timedelta(hours=2)))
        self.assertEqual(fw.verified_source_target(good,self.issued,self.start+timedelta(hours=2))["id"],"1234")

    def test_encrypted_commit_settle_and_report(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root=Path(tmp)/"research"/"encrypted_football"
            hist=Path(tmp)/"complete_history.json"
            hist.write_text("[]")
            feed=Feed([fixture(self.start)])
            with patch.object(fw,"frozen_training",return_value=self.dummy_training()):
                issued=fw.stage(hist,key=self.key,now=self.issued,fetcher=feed,root=root)
            self.assertEqual(issued["created"],1)
            snapshots=list(root.glob("forward/issued/*/*/*/*.enc"))
            self.assertEqual(len(snapshots),1)
            encrypted=snapshots[0].read_bytes()
            self.assertNotIn(b"Home United",encrypted)
            self.assertNotIn(b"machine_learning",encrypted)
            with patch.object(fw,"frozen_training",return_value=self.dummy_training()):
                again=fw.stage(hist,key=self.key,now=self.issued,
                               fetcher=feed,root=root)
            self.assertEqual(again["created"],0)
            source=Feed([fixture(self.start,finished=True)])
            later=self.start+timedelta(hours=5)
            with patch.object(fw,"git_commit_time",return_value=self.issued+timedelta(minutes=2)):
                settled=fw.settle(key=self.key,now=later,root=root,fetcher=source)
                report=fw.forward_report(key=self.key,now=later,root=root)
            self.assertEqual(settled["settled_matches"],1)
            self.assertEqual(report["status"],"LOCAL_GIT_ONLY_UNVERIFIED")
            self.assertEqual(report["models"]["machine_learning"]["n"],1)
            self.assertEqual(report["models"]["machine_learning"]["exact_hits"],0)
            self.assertIsNone(report["models"]["machine_learning"]["flat_stake_roi_pct"])
            self.assertEqual(len(list(root.glob("forward/settled/*/*.enc"))),1)
            # A settlement never changes the earlier encrypted prediction.
            self.assertEqual(snapshots[0].read_bytes(),encrypted)
            # Reject a modified encrypted commit.
            snapshots[0].write_bytes(encrypted[:-1]+bytes([encrypted[-1]^1]))
            with self.assertRaises(Exception):
                fw.forward_report(key=self.key,now=later,root=root)

    def test_invalid_commit_refused(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root=Path(tmp)/"research"/"encrypted_football"
            hist=Path(tmp)/"history.json"
            hist.write_text("[]")
            with patch.object(fw,"frozen_training",return_value=self.dummy_training()):
                fw.stage(hist,key=self.key,now=self.issued,
                         fetcher=Feed([fixture(self.start)]),root=root)
            with patch.object(fw,"git_commit_time",return_value=self.start-timedelta(minutes=10)):
                with self.assertRaisesRegex(ValueError,"not committed"):
                    fw.settle(key=self.key,now=self.start+timedelta(hours=5),
                              root=root,fetcher=Feed([fixture(self.start,finished=True)]))

    def test_authentic_first_git_blob_and_tamper_detection(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            project=Path(folder)
            subprocess.run(["git","init","-q"],cwd=folder,check=True)
            subprocess.run(["git","config","user.name","ML Research"],cwd=folder,check=True)
            subprocess.run(["git","config","user.email","research@example.invalid"],cwd=folder,check=True)
            target=project/"research/encrypted_football/forward/issued/2026/10/24/a.enc"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"encrypted first prediction")
            subprocess.run(["git","add","."],cwd=folder,check=True)
            subprocess.run(["git","commit","-qm","Lock first encrypted prediction"],cwd=folder,check=True)
            committed=fw.git_commit_time(target,repo_root=folder)
            self.assertIsNotNone(committed)
            target.write_bytes(b"encrypted ATTACK postevent replacement")
            with self.assertRaisesRegex(ValueError,"TAMPERED"):
                fw.git_commit_time(target,repo_root=folder)

    def test_real_github_hosted_run_proof(self):
        issued={"github_workflow_run":"789","issued_at":self.issued.isoformat()}
        good={"id":789,"status":"completed","conclusion":"success",
              "name":"ML V2 - blind prekickoff football research",
              "created_at":"2026-10-24T06:45:00Z",
              "updated_at":"2026-10-24T07:16:00Z"}
        with patch.dict(os.environ,{"GITHUB_ACTIONS":"true",
                                     "GITHUB_REPOSITORY":"MrXPRONOS/MrXPRONOS_App"}):
            with patch.object(fw,"github_server_run",return_value=good):
                self.assertTrue(fw.verify_server_pre_kickoff(issued,self.start))
            too_late=dict(good,updated_at="2026-10-25T11:40:00Z")
            with patch.object(fw,"github_server_run",return_value=too_late):
                with self.assertRaisesRegex(ValueError,"did not complete"):
                    fw.verify_server_pre_kickoff(issued,self.start)

    def test_unconfirmed_result_stays_pending(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root=Path(tmp)/"research"/"encrypted_football"
            hist=Path(tmp)/"history.json";hist.write_text("[]")
            with patch.object(fw,"frozen_training",return_value=self.dummy_training()):
                fw.stage(hist,key=self.key,now=self.issued,
                         fetcher=Feed([fixture(self.start)]),root=root)
            with patch.object(fw,"git_commit_time",return_value=self.issued):
                result=fw.settle(key=self.key,now=self.start+timedelta(hours=5),
                                 root=root,fetcher=Feed([]))
            self.assertEqual(result["pending_provider_result"],1)
            self.assertEqual(len(list(root.glob("forward/settled/*/*.enc"))),0)

if __name__=="__main__": unittest.main()
