"""Experimental single-score diagnostics; no changes to production or existing ledger."""
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from math import ceil, erfc, sqrt

VARIANTS=("original","under25_fusion","debiased_11","optional_dc_fusion","conditional_dc","advanced_2024")
COVERAGES=(.02,.05,.10,.20,.50,1.0)
BINS=(0.,.08,.10,.12,.14,.16,.18,.20,.25,.35,1.01)

def wilson(k,n):
    if not n:return None
    z=1.96;p=k/n;d=1+z*z/n
    c=(p+z*z/(2*n))/d
    r=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(max(0.,c-r),6),round(min(1.,c+r),6)]

def choice(row,variant):
    options=row["variants"]
    under=options["under25_fusion"]
    if variant!="conditional_dc":return options.get(variant)
    dc=options.get("optional_dc_fusion")
    if (dc and dc["score"]!=under["score"] and
        dc["probability"]>=under["probability"]+.015 and
        dc["margin"]>=under["margin"]*1.10):return dc
    return under

RANK_VERSION="mrx-single-top3-v3-common-probability-margin"

def rank(row,variant="under25_fusion"):
    """Never consult outcome/actual for selection."""
    p=choice(row,variant)
    if p is None:return -1.
    # Shared features available in both old and new immutable first-seen
    # records. Mixing incomparable ranking scales biased Top3 selection.
    return float(p["probability"])+min(.20,max(0.,p["margin"]))* .08

def hit(row,variant):
    p=choice(row,variant)
    return bool(p and tuple(p["score"])==tuple(row["actual"]))

def summary(rows,variant):
    n=len(rows);wins=sum(hit(r,variant) for r in rows)
    return {"matches":n,"wins":wins,"top1_rate":round(wins/n,6) if n else None,
            "wilson95":wilson(wins,n)}

def per_score(rows,variant):
    buckets=defaultdict(list);actual=Counter()
    for r in rows:
        p=choice(r,variant)
        if not p:continue
        key="-".join(map(str,p["score"]))
        buckets[key].append(r)
        actual["-".join(map(str,r["actual"]))]+=1
    return {"predicted":{k:summary(v,variant) for k,v in
              sorted(buckets.items(),key=lambda pair:(-len(pair[1]),pair[0]))},
            "actual_score_frequency":dict(actual.most_common(25))}

def calibration(rows,variant):
    buckets=defaultdict(list)
    for r in rows:
        p=choice(r,variant)
        if p:
            prob=p["probability"]
            for i in range(len(BINS)-1):
                if BINS[i]<=prob<BINS[i+1]:
                    buckets[i].append(r);break
    result={};ece=0.;n=0
    for i,items in sorted(buckets.items()):
        mean=sum(choice(r,variant)["probability"] for r in items)/len(items)
        accuracy=sum(hit(r,variant) for r in items)/len(items)
        ece+=len(items)*abs(mean-accuracy);n+=len(items)
        result[f"{BINS[i]:.2f}-{BINS[i+1]:.2f}"]={
            "matches":len(items),"mean_probability":round(mean,6),
            "observed_top1":round(accuracy,6)}
    return {"bins":result,"ece":round(ece/n,6) if n else None}

def paired(rows,a,b):
    ao=bo=both=neither=0
    for r in rows:
        x=hit(r,a);y=hit(r,b)
        if x and y:both+=1
        elif x:ao+=1
        elif y:bo+=1
        else:neither+=1
    n=ao+bo
    p=erfc(max(0,abs(ao-bo)-1)/sqrt(2*n)) if n else 1.
    return {"a_only":ao,"b_only":bo,"both_correct":both,"both_wrong":neither,
            "net_b_minus_a":bo-ao,"mcnemar_approx_p":round(p,6)}

def select(rows,variant):
    ranked=sorted(rows,key=lambda r:(-rank(r,variant),r["kickoff"],str(r["id"])))
    sweep={}
    for share in COVERAGES:
        n=max(1,ceil(share*len(rows))) if rows else 0
        sweep[str(round(100*share))+"pct"]=summary(ranked[:n],variant)
    days=defaultdict(list)
    for row in rows:days[row["kickoff"][:10]].append(row)
    winning=baskets=selected=0;few=0
    for day,candidates in days.items():
        if len(candidates)<3:few+=1;continue
        selected_rows=sorted(candidates,key=lambda r:(-rank(r,variant),r["kickoff"],str(r["id"])))[:3]
        baskets+=1;selected+=3
        winning+=int(any(hit(r,variant) for r in selected_rows))
    return {"research_only":True,"coverage_sweep":sweep,
            "daily_top_three":{"baskets":baskets,"winning_baskets":winning,
            "basket_hit_rate":round(winning/baskets,6) if baskets else None,
            "wilson95":wilson(winning,baskets),"selected_matches":selected,
            "days_under_three_candidates":few},
            "limitation":"Historical kickoff-time predictions are not simultaneous pre-day snapshots."}

def goal_bands(rows,variant):
    g={"under_2_expected":[],"between_2_and_3_expected":[],"3_plus_expected":[]}
    for r in rows:
        t=r["total_expected_goals"]
        k="under_2_expected" if t<2 else "3_plus_expected" if t>=3 else "between_2_and_3_expected"
        g[k].append(r)
    return {k:summary(items,variant) for k,items in g.items()}

def prematch_context(fixture,now,kickoff):
    data=fixture.get("prematch_context")
    if not isinstance(data,dict):return {"available":False,"reason":"missing"}
    stamp=data.get("observed_at_utc")
    if not isinstance(stamp,str):return {"available":False,"reason":"missing_timestamp"}
    try:
        at=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        if at.tzinfo is None:return {"available":False,"reason":"naive_timestamp"}
        at=at.astimezone(timezone.utc)
    except (ValueError,OverflowError):
        return {"available":False,"reason":"invalid_timestamp"}
    if at>now or at>kickoff-timedelta(minutes=30):
        return {"available":False,"reason":"future_or_too_late"}
    values={}
    for k in ("home_absences","away_absences","home_rest_days","away_rest_days"):
        v=data.get(k)
        if type(v) in (int,float) and 0<=v<=30:values[k]=v
    status=data.get("lineup_status")
    if status in ("predicted","confirmed"):values["lineup_status"]=status
    if not values:return {"available":False,"reason":"no_verified_fields"}
    return {"available":True,"observed_at_utc":at.isoformat(),
            "source":str(data.get("source") or "unspecified")[:80],
            "values":values,"score_altered":False}

def audit(rows):
    reports={}
    leagues=defaultdict(list)
    for r in rows:leagues[str(r.get("league") or "unknown")].append(r)
    for v in VARIANTS:
        reports[v]={"summary":summary(rows,v),"scores":per_score(rows,v),
                    "calibration":calibration(rows,v),"selection":select(rows,v),
                    "goals":goal_bands(rows,v),
                    "leagues":{k:summary(vals,v) for k,vals in
                     sorted(leagues.items(),key=lambda pair:-len(pair[1]))[:25]}}
    return {"research_diagnostics":{
        "format":"mrx-single-exact-research-v2","label_blind_ranking":True,
        "models":reports,
        "paired":{"base_vs_under":paired(rows,"original","under25_fusion"),
                  "under_vs_dc":paired(rows,"under25_fusion","optional_dc_fusion"),
                  "under_vs_conditional_dc":paired(rows,"under25_fusion","conditional_dc")},
        "context_counts":dict(Counter(("available" if r.get("context",{}).get("available")
                                      else r.get("context",{}).get("reason","missing"))
                                    for r in rows)),
        "notes":"2024-frozen advanced score+reliability; 2025/26 retrospective exploration, not guaranteed."}}
