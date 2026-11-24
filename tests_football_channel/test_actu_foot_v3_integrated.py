import base64,hashlib,os,time,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_store import decrypt
from scripts.actu_foot_v3_archive import archive_path,make_archive,verify_archive_path,compact_month
from scripts.actu_foot_v3_service import SnapshotReader,production_check,audit_receipts,inventory
from scripts.actu_foot_v3_cloud_archive import recover_inventory
import tempfile
from pathlib import Path
from scripts.actu_foot_v3_migrate import migration_preview,upgrade
from tests_football_channel.test_actu_foot_v3_complete import MemoryAtomic,fixture

class IntegratedTests(unittest.TestCase):
    def setUp(self):
        p=patch.dict(os.environ,{"ACTU_FOOT_V2_KEY_B64_V1":base64.b64encode(bytes(range(32))).decode()})
        p.start();self.addCleanup(p.stop)
    def test_context_cannot_be_relabelled(self):
        path=archive_path("matches","2026-01")
        blob=make_archive("matches","2026-01",{"a":fixture(1)})
        self.assertEqual(len(verify_archive_path(path,blob)[0]),1)
        with self.assertRaises(VaultError):decrypt("matches",blob)
        with self.assertRaises(VaultError):verify_archive_path(archive_path("matches","2026-01","a"*24),blob)
    def test_failure_before_prune_and_repeated_shards(self):
        store=MemoryAtomic()
        store.transact({"matches":[{"action":"insert","id":"a","value":fixture(1)}]})
        before=dict(store.files)
        cutoff=datetime(2026,4,1,tzinfo=timezone.utc)
        with self.assertRaises(VaultError):compact_month(store,"matches",field="kickoff_utc",cutoff=cutoff,durable_copy=lambda p,b:"wrong")
        self.assertEqual(before,store.files)
        copy=lambda p,b:hashlib.sha256(b.encode()).hexdigest()
        self.assertEqual(compact_month(store,"matches",field="kickoff_utc",cutoff=cutoff,durable_copy=copy)["moved"],1)
        store.transact({"matches":[{"action":"insert","id":"b","value":fixture(2)}]})
        self.assertEqual(compact_month(store,"matches",field="kickoff_utc",cutoff=cutoff,durable_copy=copy)["moved"],1)
        self.assertEqual(len([p for p in store.files if "/archive/" in p]),2)
        self.assertEqual(len(store.load_collection("audit",store.head()[0]).data),4)
    def test_cache_index_and_snapshot_cursor(self):
        store=MemoryAtomic()
        store.transact({"matches":[{"action":"insert","id":str(i),"value":fixture(i)} for i in range(5)]})
        reader=SnapshotReader(store)
        first=reader.query("matches",limit=2)
        self.assertEqual(reader.query("matches",limit=2),first)
        self.assertEqual(reader.hits,1)
        store.transact({"matches":[{"action":"insert","id":"new","value":fixture(7)}]})
        reader.refresh()
        with self.assertRaises(VaultError):reader.query("matches",limit=2,cursor=first["next_cursor"])
        self.assertEqual(reader.query("matches")["count"],6)
    def test_archive_recovery_from_authenticated_receipts(self):
        store=MemoryAtomic();store.transact({"matches":[{"action":"insert","id":"a","value":fixture(1)}]})
        copies={}
        def copy(path,blob):
            digest=hashlib.sha256(blob.encode()).hexdigest();copies[(path,digest)]=blob;return digest
        compact_month(store,"matches",field="kickoff_utc",cutoff=datetime(2026,4,1,tzinfo=timezone.utc),durable_copy=copy)
        head=store.head()[0]
        store.list_archives=lambda name,head:[p for p in store.files if "/archive/"+name+"/" in p]
        receipts=inventory(store,head)
        class Cloud:
            def recover(self,path,digest):return copies[(path,digest)]
        with tempfile.TemporaryDirectory() as temp:
            report=recover_inventory(receipts,Path(temp)/"recovery",Cloud())
            self.assertEqual(report,{"verified":1,"total":1,"remaining":0,"next_after":None})
            self.assertEqual(len(list((Path(temp)/"recovery").rglob("*.aes.json"))),1)
        store.list_archives=lambda name,head:[]
        with self.assertRaises(VaultError):inventory(store,head)
    def test_idempotent_migration(self):
        rows={"a":fixture(1)}
        migrated=upgrade("matches",rows)
        self.assertEqual(upgrade("matches",migrated),migrated)
        self.assertTrue(migration_preview("matches",migrated)["reversible"])
    def test_large_ciphertext_blob_fallback(self):
        import random
        from scripts.actu_foot_v2_store import encrypt,read_github_ciphertext,decrypt
        rng=random.Random(37)
        rows={str(i):{"payload":base64.b64encode(rng.randbytes(9000)).decode()} for i in range(120)}
        blob=encrypt("settings",rows).encode()
        self.assertGreater(len(blob),1_000_000)
        sha=hashlib.sha1(b"blob "+str(len(blob)).encode()+b"\0"+blob).hexdigest()
        metadata={"type":"file","encoding":"none","sha":sha}
        result={"sha":sha,"encoding":"base64","content":base64.b64encode(blob).decode()}
        self.assertEqual(decrypt("settings",read_github_ciphertext(metadata,lambda _:result).decode())[0],rows)
        result["content"]=base64.b64encode(b"corrupt").decode()
        with self.assertRaises(VaultError):read_github_ciphertext(metadata,lambda _:result)
    def test_full_capacity_index_pagination(self):
        from scripts.actu_foot_v3_query import PreparedQuery
        from scripts.actu_foot_v2_store import encrypt,decrypt
        rows={str(i):fixture(i,(i%12)+1) for i in range(5000)}
        start=time.monotonic()
        prepared=PreparedQuery("matches",rows)
        ids=set();cursor=None;pages=0
        while True:
            result=prepared.query(filters={"home_team":"Madrid"},limit=100,cursor=cursor,generation=1)
            ids.update(x["id"] for x in result["items"]);pages+=1
            cursor=result["next_cursor"]
            if not cursor:break
        self.assertEqual(len(ids),5000)
        blob=encrypt("matches",rows)
        self.assertEqual(decrypt("matches",blob)[0],rows)
        self.assertLess(time.monotonic()-start,30)
        print("V3_STRESS",5000,pages,round(time.monotonic()-start,3),len(blob))

class AutomaticPolicyTests(unittest.TestCase):
    def test_policy_must_match_all_approved_fields(self):
        from scripts.actu_foot_v3_maintenance import policy,policy_active
        self.assertTrue(policy_active({**policy(),"_schema_version":3}))
        for k in ("days","archive","type","schema"):
            self.assertFalse(policy_active({**policy(),k:None}))


class FullCycleOfflineTest(unittest.TestCase):
    def test_complete_rehearsal_without_network_or_production_writes(self):
        from scripts.actu_foot_v3_e2e_rehearsal import rehearsal
        objects={}
        class Cloud:
            def __init__(self,*,rehearsal=False,**kwargs):
                self.rehearsal=rehearsal
            def persist(self,path,blob):
                digest=hashlib.sha256(blob.encode()).hexdigest()
                objects[(path,digest)]=blob
                return digest
            def recover(self,path,digest):
                return objects[(path,digest)]
        with patch.dict(os.environ,{"GITHUB_EVENT_NAME":"push","GITHUB_REF":"refs/heads/main"}):
            with patch("scripts.actu_foot_v3_e2e_rehearsal.CloudArchive",Cloud):
                result=rehearsal()
        self.assertEqual(result["synthetic_records_archived"],1)
        self.assertEqual(result["synthetic_active_records_preserved"],2)
        self.assertTrue(result["refused_backup_did_not_prune"])
        self.assertEqual(result["audit_receipts"],1)
        self.assertEqual(result["git_production_mutations"],0)
        self.assertEqual(len(objects),1)
