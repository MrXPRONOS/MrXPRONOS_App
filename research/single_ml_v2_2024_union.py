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

def combine(key,*,root=ROOT,year=2024,through=None):
    if year not in (2024,2025,2026):
        raise ValueError("Only the 2024-2026 research cohorts are supported")
    if isinstance(through,str):through=date.fromisoformat(through)
    if year==2026:
        if through is None or through.year!=2026 or through>=date.today():
            raise ValueError("2026 union requires an explicit UTC completed-day cutoff")
    requested_months=through.month if year==2026 else 12
    root=Path(root)
    if year==2024:
        original=open_sealed((root/"openfootball/2024.enc").read_bytes(),
                            key,"openfootball-cc0-calendar-2024")
        if original["schema"]!=OF_SCHEMA or original["year"]!=2024:
            raise ValueError("Unverified OpenFootball reference")
    else:
        original={"matches":[]}
    months=[]
    for month in range(1,requested_months+1):
        blob=(root/"bsd_sportscore"/str(year)/f"{month:02d}.enc").read_bytes()
        doc=open_sealed(blob,key,"bsd-sportscore-"+str(year)+"-month:"+str(month))
        if doc.get("schema")!=f"bsd_sportscore_{year}_private_verified_v1" or doc.get("month")!=month or doc.get("year")!=year:
            raise ValueError("Wrong encrypted year/month checkpoint")
        if year==2026 and doc.get("cutoff_date")!=str(through):
            raise ValueError("Unexpected 2026 UTC archive cutoff")
        if any(not x["date"].startswith(f"{year}-{month:02d}-") or (through is not None and x["date"]>str(through)) for x in doc["matches"]):
            raise ValueError("Mixed or incorrect archive month")
        months.append(doc)
    repairs=None
    repair_path=root/"bsd_sportscore"/f"{year}_repair.enc"
    if repair_path.exists():
        from single_ml_v2_2024_repair import aad_for_year
        REPAIR_AAD=aad_for_year(year)
        repairs=open_sealed(repair_path.read_bytes(),key,REPAIR_AAD)
        if repairs.get("schema")!=REPAIR_AAD or repairs.get("year")!=year:
            raise ValueError("Unverified encrypted yearly repair archive")
        expected_failures={
            x["date"] for doc in months
            for x in doc["audit"]["sportscore"].get("failed_dates",[])
        }
        if set(repairs.get("original_failed_dates",[]))!=expected_failures:
            raise ValueError("2024 repair date list differs from archived failures")
        if any(x.get("date") not in expected_failures for x in repairs.get("matches",[])):
            raise ValueError("2024 repair contains unrequested calendar day")
    grouped=defaultdict(list)
    provider_entries=Counter()
    for entry in original["matches"]:
        grouped[match_key(entry)].append(entry)
        provider_entries["openfootball_cc0"]+=1
    for doc in months:
        for entry in doc["matches"]:
            grouped[match_key(entry)].append(entry)
            provider_entries[str(entry.get("source") or "unknown")]+=1
    if repairs:
        for entry in repairs["matches"]:
            grouped[match_key(entry)].append(entry)
            provider_entries[f"sportscore_{year}_repaired"]+=1
    priority={f"bsd_v2_{year}":0,"openfootball_football_json_cc0":1,f"sportscore_{year}":2}
    kept=[]
    duplicated=0
    conflicts=0
    rejected=Counter()
    for key,records in grouped.items():
        if not key[0].startswith(f"{year}-"):
            raise ValueError("Invalid year in combined archive")
        scores={(r["home_score"],r["away_score"]) for r in records}
        if len(scores)!=1:
            conflicts+=1
            continue
        # If multiple independent records of the same fixture have identical
        # teams, day and result, keep one with the strongest source identity.
        ordered=sorted(records,key=lambda r:priority.get(r.get("source"),9))
        chosen=dict(ordered[0])
        if chosen.get('source')==f'sportscore_{year}':
            # SportScore's URL/slug may repeat on later fixtures; derive a
            # per-calendar-fixture ML identifier without presenting it as
            # a provider-issued unique event ID.
            chosen['source_archive_id']=chosen['id']
            chosen['id']=f'sportscore_{year}_ml:'+hashlib.sha256(
                '|'.join(key).encode('utf8')).hexdigest()[:32]
            chosen['source_model_id_is_derived']=True
        if len(records)>1:duplicated+=len(records)-1
        kept.append(chosen)
    kept.sort(key=lambda r:(r["date"],r["id"]))
    if len({r['id'] for r in kept})!=len(kept):
        raise ValueError('ML match identities not unique across the full 2024 year')
    counts=Counter(r.get("source","?") for r in kept)
    last_allowed_day=through if year==2026 else date(year,12,31)
    expected_days=(last_allowed_day-date(year,1,1)).days+1
    days_with_fixture=len({r["date"] for r in kept})
    report={"year":year,"months_verified":len(months),
       "calendar_days_requested":expected_days,
       "calendar_days_with_certified_fixture":days_with_fixture,
       "calendar_days_without_certified_fixture":expected_days-days_with_fixture,
       "cutoff_utc_day":str(through) if year==2026 else f"{year}-12-31",
       "months_requested":requested_months,
       "baseline_openfootball_records":len(original["matches"]),
       "bsd_sportscore_month_records":sum(len(m["matches"]) for m in months),
       "source_entries":dict(provider_entries),
       "recovered_provider_failed_dates":repairs["audit"]["recovered_dates"] if repairs else 0,
       "remaining_provider_failed_dates":repairs["audit"]["unresolved_dates"] if repairs else [],
       "sportscore_repair_extra_records":len(repairs["matches"]) if repairs else 0,
       "sportscore_failed_days_remaining":len(repairs["audit"]["unresolved_dates"]) if repairs else sum(x["audit"]["sportscore"]["days_failed"] for x in months),
       "sportscore_repaired_days_at_200_cap":repairs["audit"]["recovered_at_200_cap"] if repairs else 0,
       "distinct_safe_matches":len(kept),
       "duplicates_same_identity_same_score":duplicated,
       "conflicting_outcome_identities_quarantined":conflicts,
       "kept_by_source":dict(counts),
       "sportscore_daily_limit":"200; some dates may be truncated",
       "sportscore_original_failed_days":sum(x["audit"]["sportscore"]["days_failed"] for x in months),
       "sportscore_at_cap_days":sum(x["audit"]["sportscore"]["days_at_200_cap_incomplete"] for x in months),
       "scope":"audited source coverage only; NOT all real-world football matches",
       "sources":"OpenFootball CC0, BSD API, SportScore" if year==2024 else "BSD API, SportScore",
       "verified_utc_kickoff_only_when_source_supplies_it":True,
       "missing_xg_not_invented":True,
       "no_supabase_or_neon":True}
    if not kept:raise RuntimeError("No verified fixtures in combined dataset")
    return kept,report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="/tmp/mrx_ml_v2_2024_multisource.json")
    p.add_argument("--export",action="store_true")
    p.add_argument("--year",type=int,choices=(2024,2025,2026),default=2024)
    p.add_argument("--through",default=None)
    a=p.parse_args()
    key=key_from_environment()
    records,report=combine(key,year=a.year,through=a.through)
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
