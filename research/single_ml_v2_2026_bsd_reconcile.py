#!/usr/bin/env python3
"""Reconcile 2026 BSD source-ID coverage against source-certified encrypted months.

Some provider IDs can share the same calendar day and normalized club names.
The 2026 initial combined-day archive is not equivalent to full BSD event-ID
coverage. This command *seals the omitted BSD observations separately* and
never inflates ML sample size before an identity-quality review.
"""
from collections import Counter,defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
import json,os,requests
from single_ml_v2_git import ROOT,key_from_environment,open_sealed,seal,atomic_bytes
from single_ml_v2_bsd_sportscore_2024 import bsd_month,identity
AAD="bsd-2026-source-id-reconciliation-v1"
CUTOFF=date(2026,10,24)
def reconcile(*,root=ROOT,key=None,token=None,fetcher=bsd_month):
    root=Path(root);key=key or key_from_environment()
    token=token or os.environ.get("BSD_API_KEY")
    if not token:raise RuntimeError("Missing historical BSD token")
    if CUTOFF>=datetime.now(timezone.utc).date():
        raise ValueError("Historical cutoff not completed in UTC")
    dest=root/"bsd_sportscore"/"2026_bsd_reconcile.enc"
    if dest.exists():
        value=open_sealed(dest.read_bytes(),key,AAD)
        if value.get("schema")!=AAD or value.get("through")!=str(CUTOFF):
            raise RuntimeError("Wrong existing BSD reconciliation archive")
        return value["audit"],False
    counter=Counter()
    missing=[]
    stats=[]
    with requests.Session() as session:
        for month in range(1,11):
            path=root/"bsd_sportscore"/"2026"/f"{month:02d}.enc"
            snap=open_sealed(path.read_bytes(),key,f"bsd-sportscore-2026-month:{month}")
            if (snap.get("schema")!="bsd_sportscore_2026_private_verified_v1"
                    or snap.get("year")!=2026 or snap.get("month")!=month
                    or snap.get("cutoff_date")!=str(CUTOFF)):
                raise RuntimeError("Unexpected archived BSD monthly checkpoint")
            stored=[r for r in snap["matches"] if r.get("source")=="bsd_v2_2026"]
            stored_ids={r["id"] for r in stored}
            if len(stored_ids)!=len(stored):
                raise RuntimeError("Archived BSD event ids not unique")
            fresh,source=fetcher(session,month,token,counter,year=2026,through=CUTOFF)
            current_ids={r["id"] for r in fresh}
            if len(current_ids)!=len(fresh):
                raise RuntimeError("New BSD fixture IDs not unique")
            key_index=defaultdict(list)
            for row in stored:
                key_index[identity(row)].append(row)
            omitted=[r for r in fresh if r["id"] not in stored_ids]
            changed=[r for r in stored if r["id"] not in current_ids]
            equal_score=0;score_disagree=0;unmatched=0
            for row in omitted:
                peers=key_index.get(identity(row),[])
                if not peers:unmatched+=1
                elif any((p["home_score"],p["away_score"])==(row["home_score"],row["away_score"]) for p in peers):
                    equal_score+=1
                else:score_disagree+=1
            missing+=omitted
            report={"month":month,"first_pass_bsd_reported":snap["audit"]["bsd"]["parsed"],
                "archived_bsd_ids":len(stored),"rechecked_bsd_source_ids":len(fresh),
                "omitted_ids":len(omitted),"historical_ids_no_longer_in_api":len(changed),
                "omitted_with_same_teams_date_same_score":equal_score,
                "omitted_with_same_teams_date_different_score":score_disagree,
                "omitted_not_matched_to_existing_bsd_team_date":unmatched,
                "provider_pages":source["pages"]}
            stats.append(report)
            print("2026_BSD_SOURCE_ID_COVERAGE",json.dumps(report),flush=True)
    audit={"year":2026,"through":str(CUTOFF),"months":10,
           "omitted_distinct_bsd_source_ids":len(missing),
           "monthly":stats,"provider_requests":counter["total"],
           "same_day_team_names_may_hide_distinct_competitions":True,
           "not_automatically_added_to_ml_training":True,
           "no_sportscore_global_completeness_claim":True}
    envelope={"schema":AAD,"year":2026,"through":str(CUTOFF),
              "audit":audit,"omitted_bsd_source_records":missing}
    atomic_bytes(dest,seal(envelope,key,AAD))
    verification=open_sealed(dest.read_bytes(),key,AAD)
    if verification["audit"]!=audit or len(verification["omitted_bsd_source_records"])!=len(missing):
        raise RuntimeError("AES-GCM source-ID reconciliation verification failed")
    return audit,True

if __name__=="__main__":
    report,stored=reconcile()
    print("2026_BSD_SOURCE_ID_RECONCILIATION",json.dumps({
        "omitted_bsd_source_ids":report["omitted_distinct_bsd_source_ids"],
        "provider_requests":report["provider_requests"],
        "all_months_checked":report["months"],
        "ciphertext_saved":stored,
    }))
