"""Reviewed V3 retention maintenance command. Preview is non-mutating."""
from __future__ import annotations
import argparse
import os
import re
from datetime import datetime,timezone,timedelta
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v3_atomic import GitAtomicStore
from scripts.actu_foot_v3_archive import partition, compact_month
from scripts.actu_foot_v3_migrate import migration_preview

SAFE_FIELDS={"matches":"kickoff_utc","live_events":"last_seen_at",
             "news":"published_at","statistics":"created_at"}
DEFAULT_DAYS={"matches":90,"live_events":30,"news":60,"statistics":120}

def maintenance(store, collection: str, *, retention_days: int,
                execute: bool=False, confirmation: str="") -> dict:
    if collection not in SAFE_FIELDS:
        raise VaultError("Retention of publications, audit or settings forbidden")
    if type(retention_days) is not int or not 30<=retention_days<=3650:
        raise VaultError("Invalid retention period")
    cutoff=datetime.now(timezone.utc)-timedelta(days=retention_days)
    parent,_=store.head()
    state=store.load_collection(collection,parent)
    if not state.exists:
        return {"collection":collection,"eligible":0,"committed":False,"reason":"missing_collection"}
    _,grouped=partition(state.data,date_field=SAFE_FIELDS[collection],
                        cutoff=cutoff,collection=collection)
    selected=sum(len(v) for v in grouped.values())
    if not execute:
        return {"collection":collection,"eligible":selected,"committed":False,
                "partitions":len(grouped)}
    if confirmation!="APPROVE_V3_ENCRYPTED_COMPACTION":
        raise VaultError("Explicit confirmation required")
    result=compact_month(store,collection,field=SAFE_FIELDS[collection],cutoff=cutoff)
    return {"collection":collection,"eligible":selected,
            "committed":bool(result["commit"]),"moved":result["moved"]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--collection",choices=tuple(SAFE_FIELDS),required=True)
    parser.add_argument("--retention-days",type=int,default=0)
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--confirmation",default="")
    args=parser.parse_args()
    repo=os.getenv("GITHUB_REPOSITORY","")
    token=os.getenv("GITHUB_TOKEN","")
    store=GitAtomicStore(repo=repo,branch="main",token=token)
    days=args.retention_days or DEFAULT_DAYS[args.collection]
    result=maintenance(store,args.collection,retention_days=days,execute=args.execute,
                       confirmation=args.confirmation)
    print("V3_RETENTION_SUMMARY",result)

if __name__=="__main__":
    main()
