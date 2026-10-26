"""Offline V3 acceptance, with synthetic data and no Telegram sends."""
import base64
import os
import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_store import CollectionVault
from scripts.actu_foot_v3_query import query,build_indexes
from scripts.actu_foot_v3_engine import apply_batch,commit_batch,TTLCache,archive_expired,export_encrypted,import_encrypted
from tests_football_channel.test_actu_foot_v2_store import MemoryGitHub

SECRET=base64.b64encode(bytes(range(32))).decode()

def fixture(i,team="Arsenal"):
    return {"home_team":team,"away_team":"Chelsea","league":"Premier League",
            "state":"finished","home_score":i%4,"away_score":1,
            "kickoff_utc":f"2026-10-{(i%25)+1:02d}T18:00:00Z"}


class TestV3(unittest.TestCase):
    def setUp(self):
        p=patch.dict(os.environ,{"ACTU_FOOT_V2_KEY_B64_V1":SECRET})
        p.start()
        self.addCleanup(p.stop)

    def test_query_filter_sort_paging(self):
        records={f"match:{i}":fixture(i) for i in range(30)}
        records["match:29"]["home_team"]="Barcelona"
        found=query("matches",records,filters={"league":"Premier League"},
                    sort_by="kickoff_utc",limit=7,generation=2)
        self.assertEqual(found["count"],30)
        seen={row["id"] for row in found["items"]}
        while found["next_cursor"]:
            found=query("matches",records,filters={"league":"Premier League"},
                        sort_by="kickoff_utc",limit=7,generation=2,cursor=found["next_cursor"])
            seen.update(item["id"] for item in found["items"])
        self.assertEqual(len(seen),30)
        self.assertEqual(query("matches",records,text="Barcelona")["count"],1)

    def test_reject_unknown_filter_stale_cursor(self):
        data={f"m:{i}":fixture(i) for i in range(10)}
        one=query("matches",data,limit=3,generation=1)
        with self.assertRaises(VaultError):
            query("matches",data,limit=3,generation=2,cursor=one["next_cursor"])
        with self.assertRaises(VaultError):
            query("matches",data,filters={"password":"x"})

    def test_atomic_batch_and_conflicts(self):
        start={"m:1":fixture(1)}
        with self.assertRaises(VaultError):
            apply_batch("matches",start,[{"action":"insert","id":"m:2","value":fixture(2)},
                                        {"action":"insert","id":"m:2","value":fixture(3)}])
        self.assertEqual(len(start),1)
        api=MemoryGitHub()
        v=CollectionVault("matches",repo="MrXPRONOS/MrXPRONOS_App",branch="main",token="fake",session=api)
        commit_batch(v,[{"action":"upsert","id":"m:1","value":fixture(1)}],allow_new=True)
        api.conflict_once=True
        commit_batch(v,[{"action":"insert","id":"m:2","value":fixture(2)}])
        self.assertEqual(len(v.read()[0]),2)

    def test_cache_expiry_and_revision(self):
        t=[0.]
        cache=TTLCache(2,clock=lambda:t[0])
        cache.put("a",{"value":1},10,generation=1)
        self.assertIsNone(cache.get("a",generation=2))
        cache.put("b",[1,2],5,generation=1)
        t[0]=7
        self.assertIsNone(cache.get("b",generation=1))

    def test_archive_and_encrypted_roundtrip(self):
        rows={"old":fixture(1),"new":fixture(24)}
        kept,archived=archive_expired("matches",rows,timestamp_field="kickoff_utc",
                        cutoff=datetime(2026,10,10,tzinfo=timezone.utc))
        self.assertEqual(set(archived),{"old"})
        self.assertEqual(set(kept),{"new"})
        ciphertext=export_encrypted("matches",archived)
        back,meta=import_encrypted("matches",ciphertext)
        self.assertEqual(back,archived)
        with self.assertRaises(VaultError):
            import_encrypted("news",ciphertext)


if __name__=="__main__":
    unittest.main()
