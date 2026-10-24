#!/usr/bin/env python3
"""Blind, PRE-KICKOFF football exact-score research: encrypted Git checkpoints.

This is NOT a replay. Forecasts are fitted only on previous completed UTC days,
encrypted BEFORE settlement and committed to Git BEFORE kickoff. Settlement
requires an already committed original snapshot. No database/Supabase/Neon.

CLI:
  stage  --history /tmp/certified_with_xg.json --lookahead-hours 30
  settle [--days 7]
  report [--test-start YYYY-MM-DD] [--out /tmp/forward_report.json]
Production requires GitHub Actions secret ML_V2_HISTORY_KEY_B64 and SportData
keys. If a run is delayed past kickoff it fails closed for that fixture.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import date,datetime,timedelta,timezone
from itertools import groupby
from pathlib import Path
from types import SimpleNamespace
import hashlib,hmac,json,math,os,secrets,subprocess,sys

import numpy as np

from sportdata_api import fetch_games,get_api_keys
from single_ml_v2_git import ROOT,key_from_environment,seal,open_sealed,atomic_bytes
from single_ml_v2_data import normalize,utc_dt
from single_ml_v2 import (FormState,load_matches,poisson_grid,dixon_coles,
                         estimate_dc_rho,FEATURE_NAMES)
from single_ml_v2_tune import BASELINE,fit_histgb
from single_ml_v2_direct import train_direct_score,direct_grid
from single_ml_v2_candidates import CANDIDATES,CANDIDATE_MODEL_NAMES,fit_pair,predict_grid
from single_ml_v2_validation import metrics,bootstrap_difference

FORECAST_DIR="forward/issued"
SETTLEMENT_DIR="forward/settled"
MODELS=("machine_learning","machine_learning_direct",
        "machine_learning_lightgbm","machine_learning_catboost")
VERSION="blind_prekickoff_git_aesgcm_20261024_v1"
TEST_START=date(2026,10,25)
MIN_LEAD_MINUTES=45
MIN_SETTLEMENT_HOURS=3


def utcnow():
    return datetime.now(timezone.utc)


def verified_source_target(raw, now, maximum):
    """Only V1 original sportId=1 scheduled football, no results or kickoff."""
    if not isinstance(raw,dict) or str(raw.get("sportId"))!="1":
        return None
    start=utc_dt(raw.get("startTime"))
    if start is None or start<=now+timedelta(minutes=MIN_LEAD_MINUTES) or start>maximum:
        return None
    if str(raw.get("statusGroup")) in ("2","3","4") or raw.get("isFinished") is True:
        return None
    home=raw.get("homeCompetitor") or {}
    away=raw.get("awayCompetitor") or {}
    if not isinstance(home,dict) or not isinstance(away,dict):
        return None
    # Reject any provider record containing a score: pregame proof cannot
    # be built from an already-playing or completed target.
    if home.get("score") is not None or away.get("score") is not None:
        return None
    mid=str(raw.get("id") or "").strip()
    league=str(raw.get("competitionDisplayName") or "").strip()
    hn=str(home.get("name") or "").strip()
    an=str(away.get("name") or "").strip()
    if not(mid and league and hn and an) or hn==an:
        return None
    return {"id":mid,"sportId":1,"kickoff":start.isoformat(),
            "date":start.date().isoformat(),"league":league,
            "home":hn,"away":an,
            "home_id":home.get("id"),"away_id":away.get("id"),
            "competition_id":raw.get("competitionId")}


def get_future_matches(now,*,hours=30,fetcher=fetch_games):
    if hours<1 or hours>72:raise ValueError("Invalid lookahead hours")
    end=now+timedelta(hours=hours)
    response=fetcher(now.date(),end.date(),timeout=45,show_odds=False)
    if not response.ok:
        raise RuntimeError("Source unavailable: no pregame forecasts will be forged")
    fixtures={}
    for raw in response.games:
        candidate=verified_source_target(raw,now,end)
        if candidate is None:continue
        key=candidate["id"]
        if key in fixtures and fixtures[key]!=candidate:
            raise ValueError("Conflicting same-ID future fixture")
        fixtures[key]=candidate
    return sorted(fixtures.values(),key=lambda f:(f["kickoff"],f["id"]))


def frozen_training(history_path,asof):
    """Build historical snapshots, then fit models with strictly prior results."""
    matches=load_matches(str(history_path),asof.date()-timedelta(days=1))
    if not matches:
        raise RuntimeError("No completed certified football history for ML")
    state=FormState()
    training=[];direct=[];past_low=[]
    pending_xg=defaultdict(list)
    for day, group in groupby(matches,lambda m:m.day):
        for active in sorted(k for k in pending_xg if k<=day):
            for old in pending_xg.pop(active):
                state.add_xg(old,active)
        games=list(group)
        frozen=[]
        for m in games:
            f=state.features(m)
            frozen.append((m,f))
        for m,f in frozen:
            training.append((f["vector"],m.hg,m.ag))
            direct.append((f["vector"],poisson_grid(f["h"],f["a"]),m.hg,m.ag))
            past_low.append((f["h"],f["a"],m.hg,m.ag))
            if m.xg_available is not None:
                activation=max(day+timedelta(days=1),
                               m.xg_available.date()+timedelta(days=1))
                pending_xg[activation].append(m)
        state.add_day(games)
    for active in sorted(k for k in pending_xg if k<=asof.date()):
        for old in pending_xg.pop(active):
            state.add_xg(old,active)
    # No hyperparameter or choice is made using any of the target fixtures.
    trained={}
    # fit_histgb needs dated, genuinely previous-day training snapshots
    # retaining exact source match dates (not inferred from vector contents).
    dated=[]
    idx=0
    for day, group in groupby(matches,lambda m:m.day):
        for m in group:
            v,h,a=training[idx]
            dated.append((v,h,a,day));idx+=1
    if idx!=len(training):
        raise ValueError("Feature/training chronology mismatch")
    trained["machine_learning"]=fit_histgb(
        dated,config=BASELINE,asof=asof.date(),feature_count=len(FEATURE_NAMES))
    trained["machine_learning_direct"]=train_direct_score(direct)
    for model_name in CANDIDATES:
        trained[CANDIDATE_MODEL_NAMES[model_name]]=fit_pair(
            model_name,training,feature_count=len(FEATURE_NAMES))
    rho=estimate_dc_rho(past_low[-9000:])
    last=matches[-1].day
    return state,trained,rho,last,len(matches)


def forecast_fixture(item,state,trained,rho,created_at,latest_day,history_digest):
    """No true match score is available or consumed by this method."""
    day=date.fromisoformat(item["date"])
    fixture=SimpleNamespace(day=day,league=item["league"],home=item["home"],
                            away=item["away"],home_id=item["home_id"],
                            away_id=item["away_id"],competition_id=item["competition_id"])
    f=state.features(fixture)
    base=poisson_grid(f["h"],f["a"])
    forecasts={}
    pair=trained["machine_learning"]
    if pair is not None:
        a=float(np.clip(pair[0].predict(f["vector"][None,:])[0],.12,5.))
        b=float(np.clip(pair[1].predict(f["vector"][None,:])[0],.12,5.))
        forecasts["machine_learning"]=poisson_grid(a,b)
    fitted=trained["machine_learning_direct"]
    if fitted is not None:
        forecasts["machine_learning_direct"]=direct_grid(fitted,f["vector"],base)
    for name in CANDIDATES:
        fitted=trained[CANDIDATE_MODEL_NAMES[name]]
        if fitted is not None:
            forecasts[CANDIDATE_MODEL_NAMES[name]]=predict_grid(
                fitted,f["vector"],poisson_grid)
    # Explicitly record nonavailability; never fill with fabricated picks.
    output={}
    for name in MODELS:
        grid=forecasts.get(name)
        if grid is None:
            output[name]={"status":"UNAVAILABLE","reason":"insufficient_past_training"}
            continue
        if grid.shape!=(11,11) or not np.isfinite(grid).all() or np.any(grid<0):
            raise ValueError("Invalid live probability grid")
        if not math.isclose(float(grid.sum()),1.,abs_tol=1e-6):
            raise ValueError("Prematch probability grid unnormalized")
        h,a=np.unravel_index(grid.argmax(),grid.shape)
        output[name]={"status":"FORECAST","score":f"{h}:{a}",
                      "top_probability":float(grid[h,a]),
                      "grid":[[round(float(p),12) for p in row] for row in grid]}
    return {"fixture":item,"models":output,"forecasted_at":created_at.isoformat(),
            "historical_latest_day":str(latest_day),
            "historical_plaintext_sha256":history_digest,
            "feature_schema":len(FEATURE_NAMES),
            "dc_rho":float(rho)}


def issue_path(key,issued_at,root=ROOT):
    # Unpredictable filename, no match IDs or score text in public Git path.
    nonce=hmac.new(key,(issued_at.isoformat()+":"+secrets.token_hex(20)).encode(),
                   hashlib.sha256).hexdigest()
    d=issued_at.date()
    return Path(root)/FORECAST_DIR/f"{d.year:04d}"/f"{d.month:02d}"/f"{d.day:02d}"/(nonce+".enc")


def encrypted_snapshots(root,key):
    for path in sorted((Path(root)/FORECAST_DIR).glob("*/*/*/*.enc")):
        doc=open_sealed(path.read_bytes(),key,"prospective:issued")
        if doc.get("version")!=VERSION or not isinstance(doc.get("forecasts"),list):
            raise ValueError("Unrecognized encrypted prematch snapshot")
        yield path,doc


def git_commit_time(path,*,repo_root="."):
    """Verify forecast was committed before kickoff, not merely time-stamped."""
    rel=str(Path(path))
    if Path(rel).is_absolute():
        rel=str(Path(rel).relative_to(Path(repo_root)))
    cmd=["git","log","--diff-filter=A","--format=%cI","--",rel]
    response=subprocess.run(cmd,cwd=repo_root,text=True,capture_output=True,check=True)
    times=[utc_dt(line) for line in response.stdout.splitlines() if line]
    if len(times)!=1 or times[0] is None:
        raise ValueError("Missing/ambiguous original Git commit for "+rel)
    return times[0]


def stage(history,*,key,now=None,fetcher=fetch_games,root=ROOT,hours=30,repo_root="."):
    timestamp=now or utcnow()
    history=Path(history)
    if not str(history.resolve()).startswith("/tmp/"):
        raise ValueError("Plaintext history permitted only in /tmp")
    if timestamp.tzinfo is None:raise ValueError("UTC aware clock required")
    fixtures=get_future_matches(timestamp,hours=hours,fetcher=fetcher)
    if not fixtures:
        return {"status":"NO_FUTURE_MATCHES","created":0}
    state,trained,rho,last,n=frozen_training(history,timestamp)
    if last>=timestamp.date():
        raise ValueError("History includes same-day or future results")
    digest=hashlib.sha256(history.read_bytes()).hexdigest()
    already=set()
    for path,doc in encrypted_snapshots(root,key):
        for old in doc["forecasts"]:
            already.add((old["fixture"]["id"],old["fixture"]["kickoff"]))
    new=[]
    for item in fixtures:
        if (item["id"],item["kickoff"]) in already:continue
        new.append(forecast_fixture(item,state,trained,rho,timestamp,last,digest))
    # Training may consume time; enforce lead-time again after fitting.
    # The git-commit timestamp is also checked independently at settlement.
    current=utcnow() if now is None else timestamp
    new=[forecast for forecast in new
         if utc_dt(forecast["fixture"]["kickoff"]) >
            current+timedelta(minutes=MIN_LEAD_MINUTES)]
    if not new:
        return {"status":"NO_ELIGIBLE_PREKICKOFF_MATCHES","created":0}
    if not any(any(x["status"]=="FORECAST" for x in row["models"].values()) for row in new):
        raise RuntimeError("No fitted research ML model available: refuse empty predictions")
    record={"version":VERSION,"issued_at":timestamp.isoformat(),
            "source":"original_sportsapipro_v1_scheduled_sportid1",
            "training_cutoff":last.isoformat(),
            "github_workflow_run":os.getenv("GITHUB_RUN_ID") or None,
            "github_sha":os.getenv("GITHUB_SHA") or None,
            "forecasts":new}
    destination=issue_path(key,timestamp,root)
    atomic_bytes(destination,seal(record,key,"prospective:issued"))
    return {"status":"ISSUED_NEEDS_GIT_COMMIT","created":len(new),
            "file":str(destination),"training_matches":n,
            "training_cutoff":str(last),"scheduled_candidates":len(fixtures)}


def settled_path(key,fixture,*,root=ROOT):
    digest=hmac.new(key,("prospective:settled:"+str(fixture["id"])+":"+
                           fixture["kickoff"]).encode(),hashlib.sha256).hexdigest()
    return Path(root)/SETTLEMENT_DIR/digest[:2]/(digest+".enc")


def verified_settlement(issued,source,*,now):
    fixture=issued["fixture"]
    kickoff=utc_dt(fixture["kickoff"])
    issued_at=utc_dt(issued["forecasted_at"])
    if not kickoff or not issued_at or issued_at+timedelta(minutes=MIN_LEAD_MINUTES)>kickoff:
        raise ValueError("Forecast created too close to kickoff")
    if now<=kickoff+timedelta(hours=MIN_SETTLEMENT_HOURS):
        return None
    records=[]
    for raw in source:
        normalized,reason=normalize(raw,kickoff.date())
        if normalized is None:continue
        if str(normalized["id"])!=str(fixture["id"]):continue
        if (normalized["home_team"]!=fixture["home"] or
            normalized["away_team"]!=fixture["away"] or
            normalized["competition"]!=fixture["league"] or
            normalized["start_time"][:16]!=kickoff.isoformat()[:16]):
            raise ValueError("Settlement provider identity differs from committed target")
        records.append(normalized)
    if not records:return None
    if len(records)!=1:raise ValueError("Ambiguous settled fixture")
    return {"home_goals":records[0]["home_score"],"away_goals":records[0]["away_score"],
            "source":"original_sportsapipro_v1_certified_football",
            "checked_at":now.isoformat(),"source_id":records[0]["id"]}


def settle(*,key,now=None,days=10,root=ROOT,fetcher=fetch_games,repo_root="."):
    now=now or utcnow()
    outstanding=[]
    for path,doc in encrypted_snapshots(root,key):
        for row in doc["forecasts"]:
            kickoff=utc_dt(row["fixture"]["kickoff"])
            if kickoff is None or kickoff.date()<now.date()-timedelta(days=days):
                continue
            if now<=kickoff+timedelta(hours=MIN_SETTLEMENT_HOURS):
                continue
            target=settled_path(key,row["fixture"],root=root)
            if target.exists():continue
            commit_at=git_commit_time(path,repo_root=repo_root)
            if commit_at+timedelta(minutes=MIN_LEAD_MINUTES)>=kickoff:
                raise ValueError("Rejected: encrypted forecast commit did not precede kickoff by required lead")
            if commit_at<utc_dt(doc["issued_at"])-timedelta(minutes=5):
                raise ValueError("Git commit time precedes forecasting event")
            outstanding.append((path,row,commit_at))
    source_cache={}
    stats=Counter()
    for path,row,commit_at in outstanding:
        fixture=row["fixture"]
        kickoff=utc_dt(fixture["kickoff"])
        if kickoff.date() not in source_cache:
            fetched=fetcher(kickoff.date(),kickoff.date(),timeout=45,show_odds=False)
            if not fetched.ok:raise RuntimeError("Result provider unavailable")
            source_cache[kickoff.date()]=fetched.games
        resolution=verified_settlement(row,source_cache[kickoff.date()],now=now)
        if resolution is None:
            stats["pending_provider_result"]+=1
            continue
        record={"version":VERSION,"original_forecast_sha256":
                hashlib.sha256(path.read_bytes()).hexdigest(),
                "forecast_file":str(path),"original_git_commit_at":commit_at.isoformat(),
                "fixture":fixture,"settlement":resolution}
        atomic_bytes(settled_path(key,fixture,root=root),
                     seal(record,key,"prospective:settled"))
        stats["settled_matches"]+=1
    stats["source_dates_queried"]=len(source_cache)
    return dict(stats)


def forward_report(*,key,now=None,root=ROOT,repo_root=".",test_start=TEST_START):
    now=now or utcnow()
    source_rows=defaultdict(list)
    pending=0;late_or_tampered=0;seen=set()
    for path,doc in encrypted_snapshots(root,key):
        for event in doc["forecasts"]:
            fixture=event["fixture"]
            ident=(fixture["id"],fixture["kickoff"])
            if ident in seen:raise ValueError("Duplicate issued forward fixture")
            seen.add(ident)
            kickoff=utc_dt(fixture["kickoff"])
            issued_at=utc_dt(event["forecasted_at"])
            if issued_at is None or kickoff is None or issued_at>=kickoff-timedelta(minutes=MIN_LEAD_MINUTES):
                raise ValueError("Invalid prekickoff snapshot timestamp")
            commit_at=git_commit_time(path,repo_root=repo_root)
            if commit_at+timedelta(minutes=MIN_LEAD_MINUTES)>=kickoff or commit_at<issued_at-timedelta(minutes=5):
                late_or_tampered+=1
                continue
            settled_file=settled_path(key,fixture,root=root)
            if not settled_file.exists():
                pending+=1
                continue
            settlement=open_sealed(settled_file.read_bytes(),key,"prospective:settled")
            if settlement["original_forecast_sha256"]!=hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError("Settlement does not match original immutable forecast")
            if settlement["fixture"]!=fixture:raise ValueError("Settlement fixture changed")
            h,a=(settlement["settlement"]["home_goals"],settlement["settlement"]["away_goals"])
            if kickoff.date()<test_start:continue
            for model,pred in event["models"].items():
                if pred["status"]!="FORECAST":continue
                probs=np.asarray(pred["grid"],float)
                if probs.shape!=(11,11) or np.any(probs<0) or not np.isfinite(probs).all() or not math.isclose(float(probs.sum()),1.,abs_tol=1e-6):
                    raise ValueError("Invalid immutable prematch probability matrix")
                ix,jx=np.unravel_index(probs.argmax(),probs.shape)
                if pred["score"]!=f"{ix}:{jx}":
                    raise ValueError("Forecast score differs from frozen grid")
                top3=np.argpartition(probs.ravel(),-3)[-3:]
                source_rows[model].append({
                    "model":model,"date":str(kickoff.date()),"id":str(fixture["id"]),
                    "predicted_score":pred["score"],"actual_score":f"{h}:{a}",
                    "top_probability":float(probs[ix,jx]),
                    "hit":int((ix,jx)==(h,a)),
                    "top3_hit":int(h*11+a in top3),
                    "log_loss":-math.log(max(float(probs[h,a]),1e-15)),
                    "quoted_odds":None,
                })
    outcomes={"version":VERSION,"status":"BLIND_PREKICKOFF_VERIFIED" if any(source_rows.values()) else "NOT_EVALUABLE",
              "start":str(test_start),"generated_at":now.isoformat(),
              "total_issued":len(seen),"awaiting_result":pending,
              "late_or_invalid_commit":late_or_tampered,
              "models":{name:metrics(source_rows[name]) for name in MODELS},
              "paired_models":{}}
    baseline={(r["date"],r["id"]):r for r in source_rows["machine_learning"]}
    for name in MODELS:
        if name=="machine_learning":continue
        challenger={(r["date"],r["id"]):r for r in source_rows[name]}
        common=sorted(set(baseline)&set(challenger))
        left=[baseline[k] for k in common];right=[challenger[k] for k in common]
        outcomes["paired_models"][name]={
            "same_fixtures":len(common),
            "reference":metrics(left),"challenger":metrics(right),
            "difference_95pct":bootstrap_difference(left,right) if common else None,
        }
    return outcomes


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("stage","settle","report"))
    p.add_argument("--history",default="/tmp/mrx_football_with_xg.json")
    p.add_argument("--lookahead-hours",type=int,default=30)
    p.add_argument("--days",type=int,default=10)
    p.add_argument("--root",default=str(ROOT))
    p.add_argument("--test-start",default=str(TEST_START))
    p.add_argument("--out",default="/tmp/ml-v2-prospective-audit.json")
    args=p.parse_args()
    key=key_from_environment()
    if args.action=="stage":
        output=stage(args.history,key=key,root=args.root,hours=args.lookahead_hours)
    elif args.action=="settle":
        output=settle(key=key,days=args.days,root=args.root)
    else:
        output=forward_report(key=key,root=args.root,test_start=date.fromisoformat(args.test_start))
        Path(args.out).write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf8")
    print("ML_V2_BLIND_FORWARD",json.dumps(output,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
