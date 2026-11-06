"""Append-only, per-run hash chained V3 records.

Never rewrites a recorded forecast or a settlement. Use one artifact per run;
GitHub Actions can persist these JSONL files as artifacts without any push.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

FORMAT="bsd-v3-ledger-1"

def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def _hash(prev, kind, identity, payload):
    return hashlib.sha256(_canonical({"previous":prev,"type":kind,
                                    "id":identity,"payload":payload}).encode("utf-8")).hexdigest()

def verify_registry(path):
    path=Path(path)
    rows=[]
    prev="0"*64
    seen=set()
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        row=json.loads(line)
        if row.get("format")!=FORMAT or row.get("previous")!=prev:
            raise ValueError("Malformed V3 chain or changed entry")
        key=(row.get("type"),row.get("id"))
        if key in seen:
            raise ValueError("Duplicate immutable record")
        expected=_hash(prev,row["type"],row["id"],row["payload"])
        if row.get("sha256")!=expected:
            raise ValueError("Immutable V3 registry checksum mismatch")
        seen.add(key)
        prev=expected
        rows.append(row)
    return rows

def append_once(path,kind,identity,payload):
    if kind not in ("forecast","settlement") or not isinstance(identity,str) or not identity:
        raise ValueError("Unsupported immutable record type or ID")
    path=Path(path)
    root=(Path.cwd()/"bsd_v3"/"artifacts").resolve()
    if root not in path.resolve().parents:
        raise ValueError("Registry may be written only inside V3 artifacts")
    rows=verify_registry(path)
    for existing in rows:
        if (existing["type"],existing["id"])==(kind,identity):
            if existing["payload"]==payload:
                return existing,False
            raise ValueError("Immutable record cannot be revised")
    previous=rows[-1]["sha256"] if rows else "0"*64
    entry={"format":FORMAT,"previous":previous,"type":kind,
           "id":identity,"payload":payload}
    entry["sha256"]=_hash(previous,kind,identity,payload)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f:
        f.write(_canonical(entry)+"\n")
    return entry,True

def record_snapshot(snapshot,path="bsd_v3/artifacts/prediction_log.jsonl"):
    if snapshot.get("format")!="bsd-v3-shadow-v1" or snapshot.get("published") is not False:
        raise ValueError("Only unpublished V3 shadow snapshots can be preserved")
    fingerprint=snapshot.get("fingerprint_sha256")
    contents={k:v for k,v in snapshot.items() if k!="fingerprint_sha256"}
    expected=hashlib.sha256(_canonical(contents).encode("utf-8")).hexdigest()
    if fingerprint!=expected:
        raise ValueError("Snapshot fingerprint mismatch; refuse immutable capture")
    count=0
    for entry in snapshot.get("matches",[]):
        if entry.get("status")!="analyzed":continue
        eid=str(entry["event_id"])
        identity=str(snapshot["generated_at_utc"])+":"+eid
        saved,added=append_once(path,"forecast",identity,{
            "snapshot_sha256":fingerprint,"event_id":eid,
            "kickoff_utc":entry["kickoff_utc"],
            "generated_at_utc":entry["generated_at_utc"],
            "model":entry["model"],"candidates":entry["candidates"],
            "selections":entry["selections"]})
        count+=int(added)
    return count
