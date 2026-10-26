"""V3 single-collection atomic batches, TTL cache and archival utilities.

Transactions use V2 GitHub SHA compare-and-swap; cross-collection atomicity
and realtime Telegram outbox semantics are expressly NOT claimed.
"""
from __future__ import annotations
import copy
import hashlib
import json
import time
from datetime import datetime,timezone,timedelta
from typing import Any
from scripts.actu_foot_v2_store import CollectionVault, VaultError, validate_records,canonical,encrypt,decrypt


def apply_batch(collection: str, previous: dict, operations: list[dict]) -> dict:
    if not isinstance(operations,list) or not 1<=len(operations)<=250:
        raise VaultError("Batch must contain 1..250 operations")
    result=copy.deepcopy(previous)
    for op in operations:
        if not isinstance(op,dict) or set(op)-{"action","id","value"}:
            raise VaultError("Invalid operation")
        action=op.get("action")
        key=op.get("id")
        if action not in {"insert","upsert","delete"} or not isinstance(key,str):
            raise VaultError("Invalid batch action/identifier")
        if action=="delete":
            if "value" in op or key not in result:
                raise VaultError("Missing record for delete")
            del result[key]
        else:
            val=op.get("value")
            if not isinstance(val,dict) or not val:
                raise VaultError("Record value must be a nonempty object")
            if action=="insert" and key in result:
                raise VaultError("Duplicate insert")
            result[key]=copy.deepcopy(val)
    validate_records(collection,result)
    return result


def commit_batch(vault: CollectionVault, operations: list[dict],
                 *, attempts: int=3, allow_new: bool=False):
    # The callback has no external side effects; retries are safe.
    return vault.update(lambda snapshot:apply_batch(vault.collection,snapshot,operations),
                        max_attempts=attempts,allow_new=allow_new)


class TTLCache:
    def __init__(self, capacity: int=128, *, clock=time.monotonic):
        if type(capacity) is not int or not 1<=capacity<=5000:
            raise VaultError("Invalid cache capacity")
        self.capacity=capacity
        self.clock=clock
        self.data={}
    def put(self,key: str,value: Any,ttl: float, *, generation: int):
        if not isinstance(key,str) or type(generation) is not int or generation<0:
            raise VaultError("Invalid cache key/generation")
        if type(ttl) not in (int,float) or not 0<ttl<=86400:
            raise VaultError("Invalid cache TTL")
        self.expire()
        if len(self.data)>=self.capacity and key not in self.data:
            self.data.pop(min(self.data,key=lambda k:self.data[k][0]))
        self.data[key]=(self.clock()+ttl,generation,copy.deepcopy(value))
    def get(self,key, *, generation: int):
        entry=self.data.get(key)
        if entry is None:
            return None
        expiry,ver,val=entry
        if self.clock()>=expiry or generation!=ver:
            self.data.pop(key,None)
            return None
        return copy.deepcopy(val)
    def expire(self):
        now=self.clock()
        for key,(expiry,_,_) in list(self.data.items()):
            if now>=expiry:
                del self.data[key]
    def invalidate(self,key=None):
        if key is None:
            self.data.clear()
        else:
            self.data.pop(key,None)


def archive_expired(collection: str, records: dict, *, timestamp_field: str,
                    cutoff: datetime, max_batch: int=1000) -> tuple[dict,dict]:
    """Prepare archival slice; caller must verify archive persisted before deletion.

    Returns (retained, archived). This does not mutate the live database.
    """
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise VaultError("Cutoff must have a timezone")
    if timestamp_field not in {"event_date","kickoff_utc","sent_at","published_at",
                               "updated_at","last_seen_at","created_at"}:
        raise VaultError("Unsupported retention field")
    validate_records(collection,records)
    archived={}
    retained=copy.deepcopy(records)
    for key,record in records.items():
        if len(archived)>=max_batch:
            break
        raw=record.get(timestamp_field)
        if not isinstance(raw,str):
            continue
        try:
            stamp=datetime.fromisoformat(raw.replace("Z","+00:00"))
        except ValueError:
            continue
        if stamp.tzinfo is None:
            continue
        if stamp<cutoff:
            archived[key]=copy.deepcopy(record)
            del retained[key]
    validate_records(collection,archived)
    validate_records(collection,retained)
    return retained,archived


def export_encrypted(collection: str, records: dict, *, generation: int=1,key_version: int=1) -> str:
    return encrypt(collection,records,generation=generation,key_version=key_version)


def import_encrypted(collection: str, ciphertext: str) -> tuple[dict,dict]:
    # AEAD + domain validation prevents untrusted JSON imports.
    return decrypt(collection,ciphertext)
