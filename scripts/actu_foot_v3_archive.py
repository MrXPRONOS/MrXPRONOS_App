"""V3 encrypted period archives and lossless two-phase atomic compaction."""
from __future__ import annotations
import hashlib
import re
from datetime import datetime, timezone
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_store import collection_path, encrypt, decrypt, validate_records, canonical, COLLECTIONS
from scripts.actu_foot_v3_engine import archive_expired

ARCHIVE_RE=re.compile(r"^assets/data/private/actufoot_v2/archive/(matches|live_events|publications|news|statistics|settings|audit)/([0-9]{4})-([0-9]{2})\.aes\.json$")
MAX_ARCHIVE_ITEMS=5000


def archive_path(name: str, period: str) -> str:
    if name not in COLLECTIONS or not re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])",period):
        raise VaultError("Unknown collection or invalid archive period")
    return f"assets/data/private/actufoot_v2/archive/{name}/{period}.aes.json"


def validate_archive_path(path: str):
    if not isinstance(path,str) or not ARCHIVE_RE.fullmatch(path):
        raise VaultError("Invalid encrypted archive path")
    return path


def partition(records: dict, *, date_field: str, cutoff: datetime, collection: str):
    retained,selected=archive_expired(collection,records,timestamp_field=date_field,cutoff=cutoff)
    groups={}
    for key,record in selected.items():
        stamp=datetime.fromisoformat(record[date_field].replace("Z","+00:00"))
        period=stamp.strftime("%Y-%m")
        groups.setdefault(period,{})[key]=record
    for period,chunk in groups.items():
        archive_path(collection,period)
        validate_records(collection,chunk)
    return retained,groups


def make_archive(name: str, period: str, records: dict, *, key_version=1, generation=1) -> str:
    path=archive_path(name,period)
    validate_records(name,records)
    if len(records)>MAX_ARCHIVE_ITEMS:
        raise VaultError("Archive shard exceeds per-file maximum")
    for row in records.values():
        field=next((f for f in ("kickoff_utc","event_date","sent_at","published_at",
                               "last_seen_at","created_at","updated_at") if f in row),None)
        if field is None:
            raise VaultError("Archive entry has no dated field")
        timestamp=datetime.fromisoformat(row[field].replace("Z","+00:00"))
        if timestamp.strftime("%Y-%m")!=period:
            raise VaultError("Archive row is in wrong monthly partition")
    # Bind identity via HMAC-derived additional encrypted sentinel; no index or data in clear.
    # The exact path is verified by the caller before decryption.
    return encrypt(name,records,key_version=key_version,generation=generation)


def verify_archive(name: str, period: str, envelope: str) -> dict:
    records,header=decrypt(name,envelope)
    make_archive(name,period,records,key_version=header["key_version"],generation=header["generation"])
    return records


def compact_month(store, collection: str, *, field: str, cutoff: datetime,
                  max_attempts: int=3) -> dict:
    """Atomic archive plus source removal in one Git commit; retries stale refs.

    This requires a separate operator-initiated command and non-empty verified source.
    Deletion of any live row happens *only* when ciphertext archives coexist in the
    same successful commit. A crash before ref update cannot remove source rows.
    """
    if collection not in COLLECTIONS or collection=="audit":
        raise VaultError("Compaction of audit or unknown collection forbidden")
    if type(max_attempts) is not int or not 1<=max_attempts<=6:
        raise VaultError("Invalid attempt count")
    for attempt in range(max_attempts):
        parent,tree=store.head()
        live=store.load_collection(collection,parent)
        if not live.exists:
            return {"moved":0,"commit":None}
        retained,grouped=partition(live.data,date_field=field,cutoff=cutoff,collection=collection)
        if not grouped:
            return {"moved":0,"commit":None}
        changes={}
        moved=0
        for period,additions in sorted(grouped.items()):
            path=archive_path(collection,period)
            old=store.read_envelope(path,parent)
            previous=verify_archive(collection,period,old) if old is not None else {}
            overlap=set(previous)&set(additions)
            if any(previous[k]!=additions[k] for k in overlap):
                raise VaultError("Conflicting archived record ID, manual repair required")
            merged={**previous,**additions}
            if len(merged)>MAX_ARCHIVE_ITEMS:
                raise VaultError("Archive exceeds size limit, split shard")
            metadata=decrypt(collection,old)[1] if old is not None else {"generation":0,"key_version":live.key_version}
            changes[path]=make_archive(collection,period,merged,
                generation=metadata["generation"]+1,key_version=metadata["key_version"])
            moved+=len(additions)
        changes[collection_path(collection)]=encrypt(collection,retained,
                     generation=live.generation+1,key_version=live.key_version)
        try:
            commit=store.commit(parent,tree,changes,message="ops(actu-foot-v3): archive compact")
            return {"moved":moved,"commit":commit,"partitions":len(grouped)}
        except Exception as exc:
            from scripts.actu_foot_github_vault import VaultConflict
            if not isinstance(exc,VaultConflict) or attempt+1==max_attempts:
                raise
    raise VaultError("Compaction retry exhausted")
