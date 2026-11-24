"""V3 operational query service: pinned Git snapshot, reusable indexes, TTL cache."""
from __future__ import annotations
import hashlib
import json
import os
import time
from scripts.actu_foot_v2_store import COLLECTIONS,canonical,VaultError
from scripts.actu_foot_v3_atomic import GitAtomicStore
from scripts.actu_foot_v3_engine import TTLCache
from scripts.actu_foot_v3_query import PreparedQuery
from scripts.actu_foot_v3_archive import verify_archive_path,validate_archive_path,SAFE_FIELDS
from scripts.actu_foot_v3_migrate import migration_preview

class SnapshotReader:
    def __init__(self,store,*,ttl=60,clock=time.monotonic):
        self.store=store
        self.ttl=ttl
        self.clock=clock
        self.cache=TTLCache(128,clock=clock)
        self.prepared={}
        self.hits=0
        self.commit=None
    def refresh(self):
        head,_=self.store.head()
        if head!=self.commit:
            self.commit=head
            self.cache.invalidate()
            self.prepared.clear()
        return head
    def _prepare(self,collection,path=None):
        if self.commit is None:self.refresh()
        key=(collection,path)
        cached=self.prepared.get(key)
        if cached and self.clock()<cached[0]:return cached[1:]
        if path:
            validate_archive_path(path)
            blob=self.store.read_envelope(path,self.commit)
            if blob is None:raise VaultError("Archive not found")
            rows,header=verify_archive_path(path,blob)
            if header["collection"]!=collection:raise VaultError("Wrong archive collection")
            generation=header["generation"]
        else:
            state=self.store.load_collection(collection,self.commit)
            if not state.exists:raise VaultError("Missing live collection")
            rows,generation=state.data,state.generation
        prepared=PreparedQuery(collection,rows)
        if len(self.prepared)>=32:self.prepared.pop(next(iter(self.prepared)))
        self.prepared[key]=(self.clock()+self.ttl,prepared,generation)
        return prepared,generation
    def query(self,collection,*,archive=None,**kwargs):
        prepared,generation=self._prepare(collection,archive)
        scope=self.commit+":"+(archive or collection)
        key=hashlib.sha256(canonical([scope,kwargs])).hexdigest()
        cached=self.cache.get(key,generation=generation)
        if cached is not None:
            self.hits+=1
            return cached
        result=prepared.query(generation=generation,snapshot=scope,**kwargs)
        self.cache.put(key,result,self.ttl,generation=generation)
        return result
    def archives(self,collection):
        if self.commit is None:self.refresh()
        return self.store.list_archives(collection,self.commit)

def audit_receipts(entries):
    from scripts.actu_foot_v2_store import verify_audit
    verify_audit(entries)
    receipts={}
    for row in entries.values():
        if row.get("operation")!="v3_archive_compact":continue
        details=row.get("details",{})
        for item in details.get("archives",[]):
            path=validate_archive_path(item["path"])
            digest=item["sha256"]
            if path in receipts or not isinstance(digest,str) or len(digest)!=64 or any(x not in "0123456789abcdef" for x in digest):
                raise VaultError("Invalid or duplicate archive receipt")
            if type(item.get("count")) is not int or item["count"]<1:
                raise VaultError("Invalid archive receipt count")
            receipts[path]=item
    return receipts

def inventory(store,head):
    receipts=audit_receipts(store.load_collection("audit",head).data)
    paths={p for name in SAFE_FIELDS for p in store.list_archives(name,head)}
    if paths!=set(receipts):
        raise VaultError("Archive inventory differs from authenticated audit receipts")
    return receipts

def production_check(store):
    reader=SnapshotReader(store)
    head=reader.refresh()
    report={}
    for name in COLLECTIONS:
        state=store.load_collection(name,head)
        if not state.exists:raise VaultError("Missing collection")
        first=reader.query(name,limit=10)
        second=reader.query(name,limit=10)
        if first!=second or first["count"]!=len(state.data):raise VaultError("Query/cache mismatch")
        report[name]={"count":first["count"],"generation":state.generation,"key_version":state.key_version,
                      "migration":migration_preview(name,state.data)["reversible"]}
    receipts=inventory(store,head)
    return {"commit":head,"collections":report,"cache_hits":reader.hits,"archive_shards":len(receipts)}

def main():
    store=GitAtomicStore(repo=os.environ["GITHUB_REPOSITORY"],token=os.environ["GITHUB_TOKEN"])
    print("V3_REAL_READ",json.dumps(production_check(store),sort_keys=True))
if __name__=="__main__":main()
