#!/usr/bin/env python3
"""Encrypted football-only research history in Git itself. No external database.

The ONLY committed data are independently AES-256-GCM encrypted daily checkpoints
and an encrypted coverage manifest. The encryption key MUST be an Actions secret.
All cleartext exists only in Actions runner memory or /tmp, never in git.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from single_ml_v2_data import day_snapshot, dates
from sportdata_api import fetch_games, get_api_keys

MAGIC = b"MRXGIT01"
ROOT = Path("research/encrypted_football")
MANIFEST = ROOT / "manifest.enc"
MAX_PLAINTEXT = 12 * 1024 * 1024
MAX_FILE = 16 * 1024 * 1024


def key_from_environment():
    raw = os.getenv("ML_V2_HISTORY_KEY_B64", "").strip()
    if not raw:
        raise RuntimeError("ML_V2_HISTORY_KEY_B64 missing: add 32-byte random key as GitHub Actions secret")
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("ML_V2_HISTORY_KEY_B64 must be valid base64") from exc
    if len(key) != 32:
        raise ValueError("ML_V2_HISTORY_KEY_B64 must decode to exactly 32 bytes")
    return key


def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf8")


def seal(obj, key, logical_name):
    content = json_bytes(obj)
    if len(content) > MAX_PLAINTEXT:
        raise ValueError("Daily record exceeds maximum allowed size")
    packed = gzip.compress(content, compresslevel=6, mtime=0)
    nonce = os.urandom(12)  # fresh, unpredictable nonce for each write
    ciphertext = AESGCM(key).encrypt(nonce, packed, logical_name.encode("utf8"))
    return MAGIC + nonce + ciphertext


def open_sealed(blob, key, logical_name):
    if not isinstance(blob, bytes) or not blob.startswith(MAGIC):
        raise ValueError("Not a valid encrypted MrXPRONOS archive")
    if len(blob) > MAX_FILE:
        raise ValueError("Encrypted file too large")
    packed = AESGCM(key).decrypt(blob[len(MAGIC):len(MAGIC)+12],
                                 blob[len(MAGIC)+12:],logical_name.encode("utf8"))
    # Limit decompression to resist malformed/untrusted large payloads.
    import zlib
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    raw = d.decompress(packed, MAX_PLAINTEXT + 1)
    if not d.eof or len(raw) > MAX_PLAINTEXT or d.unconsumed_tail:
        raise ValueError("Invalid/oversized gzip record")
    raw += d.flush()
    if len(raw) > MAX_PLAINTEXT:
        raise ValueError("Uncompressed record too large")
    return json.loads(raw)


def path_for(day, root=ROOT):
    if isinstance(day, str):day=date.fromisoformat(day)
    return Path(root) / "days" / f"{day.year:04d}" / f"{day.month:02d}" / (day.isoformat()+".enc")


def logical_for_day(day):
    return "football-day:"+str(day)


def day_data(path, key, day):
    # Independently validate the contents of any old encrypted checkpoint.
    value=open_sealed(Path(path).read_bytes(), key, logical_for_day(day))
    if value.get("day")!=str(day) or value.get("verified") is not True:
        raise ValueError("Incorrect day or uncertified existing checkpoint "+str(day))
    matches=value.get("matches")
    if not isinstance(matches,list) or value.get("certified_football_count")!=len(matches):
        raise ValueError("Invalid checkpoint match count "+str(day))
    seen=set()
    for game in matches:
        if (game.get("sportId")!=1 or game.get("start_time","")[:10]!=str(day)
            or game.get("is_finished") is not True or game.get("status_group")!=4):
            raise ValueError("Mixed/unverified match in checkpoint "+str(day))
        identity=str(game.get("id") or "")
        if not identity or identity in seen:
            raise ValueError("Duplicate/empty match ID "+identity)
        seen.add(identity)
    return value


def atomic_bytes(path, raw):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():
        raise FileExistsError("Refusing overwrite of immutable daily snapshot: "+str(path))
    temp=path.with_name(path.name+".tmp")
    try:
        with open(temp,"xb") as stream:stream.write(raw)
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()


def load_days(start, end, *,key,root=ROOT,allow_missing=False):
    fixtures={}
    missing=[]
    hashes={}
    for d in dates(start,end):
        path=path_for(d,root)
        if not path.is_file():
            missing.append(str(d))
            continue
        snapshot=day_data(path,key,d)
        hashes[str(d)]=hashlib.sha256(path.read_bytes()).hexdigest()
        for row in snapshot["matches"]:
            ident=str(row["id"])
            old=fixtures.get(ident)
            if old is not None and old!=row:
                raise ValueError("Conflicting game ID between days: "+ident)
            fixtures[ident]=row
    if missing and not allow_missing:
        raise RuntimeError("Archive incomplete: "+str(len(missing))+" missing certified days")
    records=sorted(fixtures.values(), key=lambda r:(r["start_time"],str(r["id"])))
    return records,missing,hashes


def rebuild_manifest(start,end,*,key,root=ROOT):
    records,missing,hashes=load_days(start,end,key=key,root=root,allow_missing=True)
    manifest={
        "schema":1,"start":str(start),"end":str(end),"days":len(hashes),
        "total_requested_days":len(dates(start,end)),"complete":not missing,
        "missing_days":missing,"match_count":len(records),
        "daily_cipher_sha256":hashes,
        "source":"SportsAPIPro-verified-sportId-1",
        "legacy_mixed_cache_used":False,
    }
    # manifest itself encrypted, including match counts, failures, audit.
    target=Path(root)/"manifest.enc"
    target.parent.mkdir(parents=True,exist_ok=True)
    blob=seal(manifest,key,"football-manifest")
    tmp=target.with_name("manifest.enc.tmp")
    try:
        tmp.write_bytes(blob)
        os.replace(tmp,target)
    finally:
        if tmp.exists():tmp.unlink()
    return manifest


def load_manifest(key, root=ROOT):
    blob=(Path(root)/"manifest.enc").read_bytes()
    return open_sealed(blob,key,"football-manifest")


def collect(start,end,*,key,root=ROOT,limit=40,fail_limit=5,fetcher=fetch_games):
    if not get_api_keys() and fetcher is fetch_games:
        raise RuntimeError("SPORTDATA_API_KEY is missing")
    if end<start or end>=datetime.now(timezone.utc).date():
        raise ValueError("Invalid collection period")
    root=Path(root)
    pending=[d for d in dates(start,end) if not path_for(d,root).exists()]
    # Validate existing encrypted days BEFORE any new API calls. Wrong keys
    # and corrupted checkpoints must fail, not silently discard progress.
    for d in dates(start,end):
        p=path_for(d,root)
        if p.exists():day_data(p,key,d)
    attempted=0;completed=0;failures=[]
    for d in pending:
        if limit and attempted>=limit:break
        if len(failures)>=fail_limit:break
        attempted+=1
        try:
            fetched=fetcher(d,d,timeout=45,show_odds=False)
            if not fetched.ok:
                raise RuntimeError("Football provider unavailable on "+str(d))
            snapshot=day_snapshot(d,fetched)
            # Empty answer can mean missing provider coverage. Never call it a
            # certified zero-fixture day without corroboration.
            if not snapshot["matches"]:
                raise RuntimeError("Zero certified football fixtures, day not validated")
            p=path_for(d,root)
            atomic_bytes(p,seal(snapshot,key,logical_for_day(d)))
            completed+=1
            print("FOOTBALL_ENCRYPTED_CHECKPOINT",str(d),flush=True)
        except Exception as exc:
            failures.append({"day":str(d),"reason":str(exc)[:140]})
            print("FOOTBALL_DAY_INCOMPLETE",str(d),flush=True)
    manifest=rebuild_manifest(start,end,key=key,root=root)
    return {
        "complete":manifest["complete"],"requested_days":manifest["total_requested_days"],
        "certified_days":manifest["days"],"remaining_days":len(manifest["missing_days"]),
        "attempted":attempted,"persisted_new":completed,"failed_days":failures,
    }


def export(start,end,target,*,key,root=ROOT):
    root=Path(root)
    manifest=load_manifest(key,root)
    if not manifest.get("complete") or manifest.get("source")!="SportsAPIPro-verified-sportId-1":
        raise RuntimeError("Encrypted manifest is incomplete or uncertified")
    if manifest.get("legacy_mixed_cache_used") is not False:
        raise RuntimeError("Archive provenance invalid")
    if str(start)<manifest["start"] or str(end)>manifest["end"]:
        raise RuntimeError("Requested date range is outside certified manifest")
    records,missing,hashes=load_days(start,end,key=key,root=root)
    for d,h in hashes.items():
        if manifest["daily_cipher_sha256"].get(d)!=h:
            raise RuntimeError("Encrypted day modified since manifest: "+d)
    target=Path(target)
    if not str(target.resolve()).startswith(("/tmp/","/run/user/")):
        raise ValueError("Decrypted output is permitted ONLY under /tmp or /run/user")
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+".tmp")
    try:
        with open(temp,"x",encoding="utf8") as fh:
            json.dump(records,fh,ensure_ascii=False)
        os.chmod(temp,0o600)
        os.replace(temp,target)
    finally:
        if temp.exists():temp.unlink()
    return len(records)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("collect","export","audit"))
    p.add_argument("--start",default="2024-01-01")
    p.add_argument("--end",default=None)
    p.add_argument("--root",default=str(ROOT))
    p.add_argument("--limit",type=int,default=40)
    p.add_argument("--output",default="/tmp/mrx_football_history.json")
    a=p.parse_args()
    key=key_from_environment()
    start=date.fromisoformat(a.start)
    end=date.fromisoformat(a.end) if a.end else datetime.now(timezone.utc).date()-timedelta(days=1)
    if a.action=="collect":
        status=collect(start,end,key=key,root=a.root,limit=a.limit)
        print("FOOTBALL_GIT_COLLECTION_STATUS",json.dumps(status,ensure_ascii=False))
        # incomplete is expected during multi-run backfill; exit with
        # distinct code so the GitHub workflow can commit progress.
        return 0 if status["complete"] else 2
    if a.action=="audit":
        manifest=load_manifest(key,a.root)
        records,missing,hashes=load_days(start,end,key=key,root=a.root,allow_missing=True)
        print("FOOTBALL_GIT_AUDIT",json.dumps({
            "days":len(hashes),"missing":len(missing),"matches":len(records),
            "complete":not missing,"manifest_complete":manifest.get("complete")}))
        return 0 if not missing else 2
    n=export(start,end,a.output,key=key,root=a.root)
    print("DECRYPTED_FOOTBALL_FOR_ML",n)
    return 0


if __name__=="__main__":sys.exit(main())
