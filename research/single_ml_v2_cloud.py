#!/usr/bin/env python3
"""Private, resumable, end-to-end football-only SportData research backfill.

The mixed legacy all_matches.json is NEVER read, enriched, or used. Every day
is obtained from the original API, checked for sportId=1, and durably stored
as a private Supabase Storage checkpoint BEFORE proceeding. The archive is
published only when all requested UTC days are individually certified.
Requires SPORTDATA_API_KEY[_1..5], SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from single_ml_v2_data import day_snapshot, dates, atomic_json
from sportdata_api import fetch_games, get_api_keys

BUCKET = "mrxpronos-mlv2-football-history"
DAY_PREFIX = "days/"
ARCHIVE_KEY = "certified/football_history_latest.json.gz"
MANIFEST_KEY = "certified/football_history_manifest.json"
STATUS_KEY = "status/latest.json"
DAY_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json\.gz$")


def encoded(data):
    return json.dumps(data,ensure_ascii=False,sort_keys=True,
                      separators=(",",":")).encode("utf8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


class PrivateStorage:
    def __init__(self,base,key,bucket=BUCKET,session=None):
        if not base or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        if not base.startswith("https://"):
            raise ValueError("Supabase URL must be HTTPS")
        self.base=base.rstrip("/")+"/storage/v1"
        self.bucket=bucket
        self.http=session or requests.Session()
        self.headers={"apikey":key,"Authorization":"Bearer "+key}
        self.checked=False

    def check_private(self):
        r=self.http.get(self.base+"/bucket/"+quote(self.bucket,safe=""),
                        headers=self.headers,timeout=35)
        r.raise_for_status()
        body=r.json()
        if str(body.get("id"))!=self.bucket or body.get("public") is not False:
            raise RuntimeError("The dedicated storage bucket must exist and be PRIVATE")
        self.checked=True

    def _require(self):
        if not self.checked:
            self.check_private()

    def list_days(self):
        self._require()
        offset=0
        found=set()
        while True:
            r=self.http.post(self.base+"/object/list/"+quote(self.bucket,safe=""),
                             json={"prefix":DAY_PREFIX,"limit":1000,"offset":offset,
                                   "sortBy":{"column":"name","order":"asc"}},
                             headers=self.headers,timeout=45)
            r.raise_for_status()
            rows=r.json()
            if not isinstance(rows,list):
                raise ValueError("Unexpected Supabase Storage list schema")
            for x in rows:
                name=str(x.get("name") or "")
                # Provider may return name or prefixed name, never trust folders.
                name=name.removeprefix(DAY_PREFIX)
                m=DAY_NAME.fullmatch(name)
                if m:
                    date.fromisoformat(m.group(1))
                    if m.group(1) in found:
                        raise ValueError("Duplicate day in storage listing: "+name)
                    found.add(m.group(1))
            if len(rows)<1000:break
            offset+=len(rows)
            if offset>20000:
                raise RuntimeError("Storage listing limit reached: refuse partial coverage")
        return found

    def read(self,path,*,missing_ok=False):
        self._require()
        url=self.base+"/object/authenticated/"+quote(self.bucket,safe="")+"/"+quote(path,safe="/")
        r=self.http.get(url,headers=self.headers,timeout=70)
        if missing_ok and r.status_code==404:return None
        r.raise_for_status()
        return r.content

    def put(self,path,content,*,mime):
        self._require()
        url=self.base+"/object/"+quote(self.bucket,safe="")+"/"+quote(path,safe="/")
        r=self.http.post(url,data=content,timeout=80,
                         headers={**self.headers,"Content-Type":mime,
                                  "x-upsert":"true","cache-control":"no-store"})
        r.raise_for_status()


def gzip_bytes(src):
    return gzip.compress(src,compresslevel=6,mtime=0)


def json_gzip_decode(data):
    if data is None:
        raise RuntimeError("Missing remote checkpoint")
    return json.loads(gzip.decompress(data).decode("utf8"))


def certified_snapshot(content,day):
    snapshot=json_gzip_decode(content)
    if (snapshot.get("day")!=str(day) or snapshot.get("verified") is not True):
        raise ValueError("Unverified day checkpoint "+str(day))
    fixtures=snapshot.get("matches")
    if not isinstance(fixtures,list) or not fixtures:
        raise ValueError("Checkpoint contains no certified football fixtures "+str(day))
    if len(fixtures)!=snapshot.get("certified_football_count"):
        raise ValueError("Day count conflict "+str(day))
    unique={}
    for record in fixtures:
        if not isinstance(record,dict):
            raise ValueError("Non-object fixture in "+str(day))
        if record.get("sportId")!=1 or record.get("start_time","")[:10]!=str(day):
            raise ValueError("Non-football or wrong-day fixture "+str(day))
        if record.get("is_finished") is not True or record.get("status_group")!=4:
            raise ValueError("Unfinished fixture "+str(day))
        fixture_id=str(record.get("id") or "")
        if not fixture_id:
            raise ValueError("Missing fixture ID "+str(day))
        if fixture_id in unique and unique[fixture_id]!=record:
            raise ValueError("Contradictory fixture ID in same day "+fixture_id)
        unique[fixture_id]=record
    return list(unique.values())


def publish_when_complete(storage,start,end,output,*,days_seen=None):
    all_days=dates(start,end)
    seen=days_seen if days_seen is not None else storage.list_days()
    missing=[str(day) for day in all_days if str(day) not in seen]
    if missing:
        return {"complete":False,"missing_count":len(missing),
                "first_missing_dates":missing[:12],"days_certified":len(all_days)-len(missing)}
    merged={}
    day_digests={}
    for day in all_days:
        b=storage.read(DAY_PREFIX+str(day)+".json.gz")
        fixtures=certified_snapshot(b,day)
        day_digests[str(day)]=sha(b)
        for record in fixtures:
            key=str(record["id"])
            if key in merged and merged[key]!=record:
                raise ValueError("Conflicting fixture across certified days "+key)
            merged[key]=record
    records=sorted(merged.values(),key=lambda r:(r["start_time"],str(r["id"])))
    raw=encoded(records)
    compressed=gzip_bytes(raw)
    manifest={
        "status":"CERTIFIED_COMPLETE","source":"sportsapipro_v1_allscores",
        "sportId":1,"start":str(start),"end":str(end),"days_certified":len(all_days),
        "finished_football_matches":len(records),
        "sha256_uncompressed":sha(raw),"sha256_archive":sha(compressed),
        "checkpoint_sha256":day_digests,
        "published_at":datetime.now(timezone.utc).isoformat(),
        "private_bucket":storage.bucket,"archive_object":ARCHIVE_KEY,
        "legacy_mixed_cache_used":False
    }
    # Upload compressed dataset first and manifest LAST. Readers verify
    # both digests to avoid accepting stale/partially overwritten objects.
    storage.put(ARCHIVE_KEY,compressed,mime="application/gzip")
    storage.put(MANIFEST_KEY,encoded(manifest),mime="application/json")
    if output:
        atomic_json(output,records)
    return {"complete":True,"days_certified":len(all_days),
            "finished_football_matches":len(records),
            "sha256_uncompressed":sha(raw),
            "archive_object":ARCHIVE_KEY}


def verified_download(storage,target,*,minimum_end=None):
    storage.check_private()
    manifest_raw=storage.read(MANIFEST_KEY)
    if manifest_raw is None:
        raise RuntimeError("Certified manifest missing")
    manifest=json.loads(manifest_raw)
    if (manifest.get("status")!="CERTIFIED_COMPLETE"
        or manifest.get("source")!="sportsapipro_v1_allscores"
        or manifest.get("sportId")!=1
        or manifest.get("legacy_mixed_cache_used") is not False
        or manifest.get("archive_object")!=ARCHIVE_KEY):
        raise ValueError("Archive manifest is not certified")
    if minimum_end and date.fromisoformat(manifest["end"])<minimum_end:
        raise ValueError("Certified archive is too old for requested end date")
    zipped=storage.read(ARCHIVE_KEY)
    if sha(zipped)!=manifest["sha256_archive"]:
        raise ValueError("Archive SHA-256 differs from certified manifest")
    raw=gzip.decompress(zipped)
    if sha(raw)!=manifest["sha256_uncompressed"]:
        raise ValueError("Uncompressed archive SHA-256 differs from manifest")
    records=json.loads(raw)
    if len(records)!=manifest["finished_football_matches"]:
        raise ValueError("Certified fixture count mismatch")
    for row in records:
        if row.get("sportId")!=1 or row.get("is_finished") is not True:
            raise ValueError("Archive contains uncertified sport or fixture")
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix(target.suffix+".tmp")
    temp.write_bytes(raw)
    os.replace(temp,target)
    return manifest


def backfill(storage,start,end,*,limit,fail_limit=8,output=None):
    storage.check_private()
    all_days=dates(start,end)
    existing=storage.list_days()
    pending=[d for d in all_days if str(d) not in existing]
    attempts=0;success=0;failures=[]
    for day in pending:
        if limit>0 and attempts>=limit:break
        if len(failures)>=fail_limit:break
        attempts+=1
        try:
            fetched=fetch_games(day,day,timeout=45,show_odds=False)
            snapshot=day_snapshot(day,fetched)
            # Valid empty responses on football-named endpoint may be provider
            # coverage failures; refuse to mark day certified with zero matches.
            if not snapshot["matches"]:
                raise RuntimeError("API day has zero certified football games")
            certified_snapshot(gzip_bytes(encoded(snapshot)),day)
            storage.put(DAY_PREFIX+str(day)+".json.gz",
                        gzip_bytes(encoded(snapshot)),mime="application/gzip")
            existing.add(str(day))
            success+=1
            print("CERTIFIED_DAY",str(day),"football_games",len(snapshot["matches"]),flush=True)
        except Exception as exc:
            failures.append({"date":str(day),"reason":str(exc)[:170]})
            print("FAILED_DAY",str(day),str(exc)[:140],flush=True)
        # Requests are deliberately sequential: limited provider quota.
        time.sleep(.15)
    status={
        "start":str(start),"end":str(end),"pending_before":len(pending),
        "attempted":attempts,"persisted_new_days":success,
        "failures":failures,"last_checked":datetime.now(timezone.utc).isoformat()
    }
    progress=publish_when_complete(storage,start,end,output,days_seen=existing)
    status.update(progress)
    storage.put(STATUS_KEY,encoded(status),mime="application/json")
    return status


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2024-01-01")
    p.add_argument("--end",help="UTC end date, default previous UTC day")
    p.add_argument("--max-days",type=int,default=100)
    p.add_argument("--fail-limit",type=int,default=8)
    p.add_argument("--output",default="/tmp/mrxpronos_football_certified.json")
    p.add_argument("--audit",default="/tmp/mrxpronos_football_backfill_audit.json")
    p.add_argument("--download-certified",action="store_true",
                   help="Only fetch SHA-verified published private archive to local output")
    p.add_argument("--require-end",default=None)
    args=p.parse_args()
    end=date.fromisoformat(args.end) if args.end else datetime.now(timezone.utc).date()-timedelta(days=1)
    start=date.fromisoformat(args.start)
    if start>end or end>=datetime.now(timezone.utc).date():
        p.error("Require start <= end < today UTC")
    if args.max_days<0 or args.fail_limit<1:p.error("Invalid limits")
    storage=PrivateStorage(os.getenv("SUPABASE_URL",""),
                           os.getenv("SUPABASE_SERVICE_ROLE_KEY",""))
    if args.download_certified:
        manifest=verified_download(storage,args.output,
                 minimum_end=date.fromisoformat(args.require_end) if args.require_end else None)
        print("CERTIFIED_FOOTBALL_DOWNLOADED",
              json.dumps({k:manifest[k] for k in ("start","end","days_certified",
                      "finished_football_matches","sha256_uncompressed")}),flush=True)
        return 0
    if not get_api_keys():
        p.error("SPORTDATA_API_KEY[_1..5] is not configured")
    status=backfill(storage,start,end,limit=args.max_days,
                    fail_limit=args.fail_limit,output=args.output)
    atomic_json(args.audit,status)
    print("FOOTBALL_BACKFILL_STATUS",json.dumps(status,ensure_ascii=False),flush=True)
    return 0 if status["complete"] else 2


if __name__=="__main__":
    sys.exit(main())
