"""V3 synthetic performance and fault-injection suite. No production mutation."""
import base64
import os
import time
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from scripts.actu_foot_github_vault import VaultError,VaultConflict
from scripts.actu_foot_v2_store import encrypt,decrypt
from scripts.actu_foot_v3_atomic import GitAtomicStore
from scripts.actu_foot_v3_archive import archive_path,partition,verify_archive,make_archive,compact_month
from scripts.actu_foot_v3_engine import apply_batch
from scripts.actu_foot_v3_query import query

SECRET=base64.b64encode(bytes(range(32))).decode()


class MemoryAtomic:
    def __init__(self):
        self.files={}
        self.revision=0
        self.conflict=False
    def head(self):
        return f"{self.revision:040x}",f"{self.revision:040x}"
    def load_collection(self,name,parent):
        from scripts.actu_foot_v3_atomic import FileState
        from scripts.actu_foot_v2_store import collection_path
        old=self.files.get(collection_path(name))
        if old:
            rows,h=decrypt(name,old)
            return FileState(rows,h["generation"],h["key_version"],True)
        return FileState({},0,1,False)
    def read_envelope(self,path,parent):
        return self.files.get(path)
    def commit(self,parent,tree,changes,*,message):
        if self.conflict:
            self.conflict=False
            raise VaultConflict("concurrent ref")
        if parent!=self.head()[0]:
            raise VaultConflict("stale commit")
        self.files.update(changes)
        self.revision+=1
        return self.head()[0]
    transact=GitAtomicStore.transact


def fixture(index,month=1):
    return {"home_team":"Madrid","away_team":"Barcelona",
            "kickoff_utc":f"2026-{month:02d}-{(index%27)+1:02d}T18:00:00Z",
            "state":"finished","home_score":index%4,"away_score":1}


class V3CompleteTests(unittest.TestCase):
    def setUp(self):
        pp=patch.dict(os.environ,{"ACTU_FOOT_V2_KEY_B64_V1":SECRET})
        pp.start()
        self.addCleanup(pp.stop)

    def test_atomic_collections_and_audit(self):
        fake=MemoryAtomic()
        fake.conflict=True
        commit=fake.transact({"matches":[{"action":"insert","id":"fixture:1","value":fixture(1)}],
            "publications":[{"action":"insert","id":"post:1","value":{"status":"sent"}}]})
        self.assertTrue(commit)
        self.assertEqual(fake.load_collection("matches",fake.head()[0]).generation,1)
        self.assertEqual(fake.load_collection("publications",fake.head()[0]).generation,1)
        self.assertEqual(len(fake.load_collection("audit",fake.head()[0]).data),1)

    def test_failing_transaction_never_mutates(self):
        fake=MemoryAtomic()
        with self.assertRaises(VaultError):
            fake.transact({"matches":[{"action":"upsert","id":"x","value":fixture(1)}],
                           "publications":[{"action":"insert","id":"bad","value":{"status":"invalid"}}]})
        self.assertEqual(fake.files,{})

    def test_compaction_and_crash_consistency(self):
        fake=MemoryAtomic()
        fake.transact({"matches":[
            {"action":"insert","id":"old","value":fixture(1,1)},
            {"action":"insert","id":"new","value":fixture(1,10)}]})
        fake.conflict=True
        result=compact_month(fake,"matches",field="kickoff_utc",
                         cutoff=datetime(2026,4,1,tzinfo=timezone.utc))
        self.assertEqual(result["moved"],1)
        self.assertIn("old",verify_archive("matches","2026-01",
                      fake.files[archive_path("matches","2026-01")]))
        self.assertEqual(set(fake.load_collection("matches",fake.head()[0]).data),{"new"})
        self.assertEqual(compact_month(fake,"matches",field="kickoff_utc",
                  cutoff=datetime(2026,4,1,tzinfo=timezone.utc))["moved"],0)

    def test_archive_cross_period_rejected(self):
        with self.assertRaises(VaultError):
            make_archive("matches","2026-02",{"a":fixture(1,1)})

    def test_performance_4000_fixture_records(self):
        rows={f"fixture:{n:05d}":fixture(n,(n%12)+1) for n in range(4000)}
        begin=time.monotonic()
        answer=query("matches",rows,filters={"home_team":"Madrid"},
                     limit=100,generation=1)
        self.assertEqual(answer["count"],4000)
        self.assertLess(time.monotonic()-begin,15)
        blob=encrypt("matches",rows)
        restored,_=decrypt("matches",blob)
        self.assertEqual(len(restored),4000)


if __name__=="__main__":
    unittest.main()
