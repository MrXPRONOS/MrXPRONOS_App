"""Offline regression: an unsuccessful 2024 lookup may never lose a 2026 checkpoint."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_git import (seal,path_for,logical_for_day,atomic_bytes,
    rebuild_manifest,load_manifest,export,day_data)

def fixture(day,mid):
    return {"id":mid,"sportId":1,"start_time":str(day)+"T14:00:00Z",
        "is_finished":True,"status_group":4,
        "competition":"Test","home_team":"A","away_team":"B",
        "home_score":1,"away_score":0}

def saved(root,key,day,mid):
    entry=fixture(day,mid)
    snapshot={"day":str(day),"verified":True,
        "certified_football_count":1,"matches":[entry]}
    path=path_for(day,root)
    atomic_bytes(path,seal(snapshot,key,logical_for_day(day)))
    return entry

class ManifestTests(unittest.TestCase):
    def test_disjoint_window_does_not_destroy_verified_day(self):
        key=b"J"*32
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            late=date(2026,10,20);early=date(2024,1,1)
            entry=saved(root,key,late,"123")
            old=rebuild_manifest(late,late,key=key,root=root)
            self.assertTrue(old["complete"])
            # 2024 provider sends NO valid games, and an incomplete new
            # request cannot erase the Oct-2026 authenticated daily record.
            catalog=rebuild_manifest(early,date(2024,1,7),key=key,root=root)
            self.assertFalse(catalog["complete"])
            self.assertEqual(catalog["days"],1)
            self.assertEqual(catalog["start"],"2024-01-01")
            self.assertEqual(catalog["end"],"2026-10-20")
            output=Path(temp)/"outside_tmp.json"
            # Export plaintext is allowed only within /tmp.
            out=Path("/tmp")/("mrx_v2_manifest_test_"+next(tempfile._get_candidate_names())+".json")
            try:
                self.assertEqual(export(late,late,out,key=key,root=root),1)
                self.assertEqual(json.loads(out.read_text()),[entry])
                with self.assertRaises(RuntimeError):
                    export(early,late,out,key=key,root=root)
            finally:
                out.unlink(missing_ok=True)
    def test_catalog_will_include_new_saved_earlier_days(self):
        key=b"P"*32
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            recent=date(2026,10,20);old=date(2024,1,1)
            saved(root,key,recent,"456")
            saved(root,key,old,"123")
            manifest=rebuild_manifest(old,old,key=key,root=root)
            self.assertEqual(manifest["days"],2)
            self.assertFalse(manifest["complete"])
            self.assertEqual(set(manifest["daily_cipher_sha256"]),{str(old),str(recent)})
            self.assertEqual(load_manifest(key,root)["daily_cipher_sha256"],manifest["daily_cipher_sha256"])

if __name__=="__main__":unittest.main()
