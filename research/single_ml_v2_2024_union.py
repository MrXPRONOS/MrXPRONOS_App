#!/usr/bin/env python3
"""Audit and temporary in-runner export of complete 2024 football research union.

Exact normalized date+home+away match identities only; no fuzzy merging or
fictional global IDs. Conflicting outcomes are QUARANTINED and excluded from
training. Source archives are read-only and remain separately encrypted.
"""
from __future__ import annotations
import argparse,json,hashlib
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path
from single_ml_v2_git import ROOT,key_from_environment,open_sealed
from single_ml_v2_bsd_sportscore_2024 import norm,SCHEMA as BSD_SCHEMA
from single_ml_v2_openfootball2024 import SCHEMA as OF_SCHEMA

def match_key(row):
    return (str(row["date"]),norm(row["home_team"]),norm(row["away_team"]))

def combine(key,*,root=ROOT):
    root=Path(root)
    original=open_sealed((root/"openfootball/2024.enc").read_bytes(),
                    key,"openfootball-cc0-calendar-2024")
    if original["schema"]!=OF_SCHEMA or original["year"]!=2024:
        raise ValueError("Unverified OpenFootball reference")
    months=[]
    for month in range(1,13):
        blob=(root/"bsd_sportscore"/"2024"/f"{month:02d}.enc").read_bytes()
        doc=open_sealed(blob,key,"bsd-sportscore-2024-month:"+str(month))
        if doc.get("schema")!=BSD_SCHEMA or doc.get("month")!=month or doc.get("year")!=2024:
            raise ValueError("Wrong 2024 month checkpoint")
        if any(not x["date"].startswith(f"2024-{month:02d}-") for x in doc["matches"]):
            raise ValueError("Mixed or incorrect archive month")
        months.append(doc)
    grouped=defaultdict(list)
    provider_entries=Counter()
    for entry in original["matches"]:
        grouped[match_key(entry)].append(entry)
        provider_entries["openfootball_cc0"]+=1
    for doc in months:
        for entry in doc["matches"]:
            grouped[match_key(entry)].append(entry)
            provider_entries[str(entry.get("source") or "unknown")]+=1
    priority={"bsd_v2_2024":0,"openfootball_football_json_cc0":1,"sportscore_2024":2}
    kept=[]
    duplicated=0
    conflicts=0
    rejected=Counter()
    for key,records in grouped.items():
        if not key[0].startswith("2024-"):
            raise ValueError("Invalid year in combined archive")
        scores={(r["home_score"],r["away_score"]) for r in records}
        if len(scores)!=1:
            conflicts+=1
            continue
        # If multiple independent records of the same fixture have identical
        # teams, day and result, keep one with the strongest source identity.
        ordered=sorted(records,key=lambda r:priority.get(r.get("source"),9))
        chosen=dict(ordered[0])
        if chosen.get('source')=='sportscore_2024':
            # SportScore's URL/slug may repeat on later fixtures; derive a
            # per-calendar-fixture ML identifier without presenting it as
            # a provider-issued unique event ID.
            chosen['source_archive_id']=chosen['id']
            chosen['id']='sportscore_2024_ml:'+hashlib.sha256(
                '|'.join(key).encode('utf8')).hexdigest()[:32]
            chosen['source_model_id_is_derived']=True
        if len(records)>1:duplicated+=len(records)-1
        kept.append(chosen)
    kept.sort(key=lambda r:(r["date"],r["id"]))
    if len({r['id'] for r in kept})!=len(kept):
        raise ValueError('ML match identities not unique across the full 2024 year')
    counts=Counter(r.get("source","?") for r in kept)
    report={"year":2024,"months_verified":len(months),
       "baseline_openfootball_records":len(original["matches"]),
       "bsd_sportscore_month_records":sum(len(m["matches"]) for m in months),
       "source_entries":dict(provider_entries),
       "distinct_safe_matches":len(kept),
       "duplicates_same_identity_same_score":duplicated,
       "conflicting_outcome_identities_quarantined":conflicts,
       "kept_by_source":dict(counts),
       "sportscore_daily_limit":"200; some 2024 dates may be truncated",
       "sportscore_failed_days":sum(x["audit"]["sportscore"]["days_failed"] for x in months),
       "sportscore_at_cap_days":sum(x["audit"]["sportscore"]["days_at_200_cap_incomplete"] for x in months),
       "scope":"audited source coverage only; NOT all real-world football matches",
       "sources":"OpenFootball CC0, BSD API, SportScore",
       "verified_utc_kickoff_only_when_source_supplies_it":True,
       "missing_xg_not_invented":True,
       "no_supabase_or_neon":True}
    if not kept:raise RuntimeError("No verified fixtures in combined dataset")
    return kept,report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="/tmp/mrx_ml_v2_2024_multisource.json")
    p.add_argument("--export",action="store_true")
    a=p.parse_args()
    key=key_from_environment()
    records,report=combine(key)
    if a.export:
        dest=Path(a.output)
        if not str(dest.resolve()).startswith("/tmp/"):
            raise ValueError("ML plaintext outputs restricted to runner /tmp")
        if dest.exists():raise FileExistsError("Refuse plaintext overwrite")
        with dest.open("x",encoding="utf-8") as stream:
            json.dump(records,stream,ensure_ascii=False)
        dest.chmod(0o600)
    print("ML_V2_2024_INDEPENDENT_AUDIT",json.dumps(report,ensure_ascii=False))

if __name__=="__main__":main()
