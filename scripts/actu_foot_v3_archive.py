"""V3 authenticated immutable monthly shards, with independent verified copy before atomic prune."""
from __future__ import annotations
import hashlib
import re
import secrets
from datetime import datetime, timezone
from scripts.actu_foot_github_vault import VaultError,VaultConflict
from scripts.actu_foot_v2_store import collection_path, encrypt, decrypt, validate_records, append_audit, COLLECTIONS
from scripts.actu_foot_v3_engine import archive_expired

SAFE_FIELDS={"matches":"kickoff_utc","live_events":"last_seen_at","news":"published_at","statistics":"created_at"}
ARCHIVE_RE=re.compile(r"^assets/data/private/actufoot_v2/archive/(matches|live_events|news|statistics)/(20[0-9]{2}-(?:0[1-9]|1[0-2]))(?:-([a-f0-9]{24}))?\.aes\.json$")
MAX_ARCHIVE_ITEMS=5000

def archive_path(name,period,shard=None):
    path=f"assets/data/private/actufoot_v2/archive/{name}/{period}"+("-"+shard if shard else "")+".aes.json"
    return validate_archive_path(path)

def validate_archive_path(path):
    if not isinstance(path,str) or not ARCHIVE_RE.fullmatch(path):
        raise VaultError("Invalid encrypted archive path")
    return path

def stamp_period(row,field):
    try:
        t=datetime.fromisoformat(row[field].replace("Z","+00:00"))
        if t.tzinfo is None:raise ValueError()
        return t.astimezone(timezone.utc).strftime("%Y-%m")
    except (KeyError,ValueError,TypeError,AttributeError) as exc:
        raise VaultError("Archive entry lacks a valid UTC date") from exc

def partition(records,*,date_field,cutoff,collection,max_batch=1000):
    if SAFE_FIELDS.get(collection)!=date_field:raise VaultError("Unsupported archive collection/field")
    retained,selected=archive_expired(collection,records,timestamp_field=date_field,cutoff=cutoff,max_batch=max_batch)
    groups={}
    for key,record in selected.items():
        period=stamp_period(record,date_field)
        # Keep the work per run bounded even on highly fragmented data.
        if period not in groups and len(groups)>=24:
            retained[key]=record
            continue
        groups.setdefault(period,{})[key]=record
    return retained,groups

def _validate(name,period,records):
    validate_records(name,records)
    if not records or len(records)>MAX_ARCHIVE_ITEMS:raise VaultError("Invalid archive size")
    for row in records.values():
        if stamp_period(row,SAFE_FIELDS[name])!=period:
            raise VaultError("Archive row is in wrong monthly partition")

def make_archive(name,period,records,*,key_version=1,generation=1,shard=None):
    path=archive_path(name,period,shard)
    _validate(name,period,records)
    return encrypt(name,records,key_version=key_version,generation=generation,archive_context=path)

def verify_archive_path(path,envelope):
    match=ARCHIVE_RE.fullmatch(validate_archive_path(path))
    name,period,_=match.groups()
    records,header=decrypt(name,envelope,archive_context=path)
    _validate(name,period,records)
    return records,header

def verify_archive(name,period,envelope,*,shard=None):
    return verify_archive_path(archive_path(name,period,shard),envelope)[0]

def compact_month(store,collection,*,field,cutoff,durable_copy=None,max_attempts=3):
    if SAFE_FIELDS.get(collection)!=field:raise VaultError("Unsafe compaction collection")
    if not callable(durable_copy):raise VaultError("Independent verified archive copy required")
    if type(max_attempts) is not int or not 1<=max_attempts<=6:raise VaultError("Invalid retry budget")
    for attempt in range(max_attempts):
        parent,tree=store.head()
        live=store.load_collection(collection,parent)
        if not live.exists:raise VaultError("Missing initialized collection")
        retained,groups=partition(live.data,date_field=field,cutoff=cutoff,collection=collection)
        if not groups:return {"moved":0,"commit":None,"partitions":0}
        changes={}
        receipts=[]
        for period,rows in sorted(groups.items()):
            shard=None
            path=archive_path(collection,period)
            if store.read_envelope(path,parent) is not None:
                shard=secrets.token_hex(12)
                path=archive_path(collection,period,shard)
                if store.read_envelope(path,parent) is not None:raise VaultError("Archive shard collision")
            payload=make_archive(collection,period,rows,key_version=live.key_version,shard=shard)
            if verify_archive_path(path,payload)[0]!=rows:raise VaultError("Archive roundtrip mismatch")
            digest=hashlib.sha256(payload.encode()).hexdigest()
            if durable_copy(path,payload)!=digest:raise VaultError("Independent archive readback mismatch")
            changes[path]=payload
            receipts.append({"path":path,"sha256":digest,"count":len(rows)})
        moved=sum(x["count"] for x in receipts)
        changes[collection_path(collection)]=encrypt(collection,retained,generation=live.generation+1,key_version=live.key_version)
        audit=store.load_collection("audit",parent)
        if not audit.exists:raise VaultError("Missing initialized audit")
        entries=append_audit(audit.data,"v3_archive_compact",{"collection":collection,"moved":moved,"archives":receipts})
        changes[collection_path("audit")]=encrypt("audit",entries,generation=audit.generation+1,key_version=audit.key_version)
        try:
            commit=store.commit(parent,tree,changes,message="ops(actu-foot-v3): archive compact")
            return {"moved":moved,"commit":commit,"partitions":len(groups)}
        except VaultConflict:
            if attempt+1==max_attempts:raise
    raise VaultError("Compaction retry exhausted")
