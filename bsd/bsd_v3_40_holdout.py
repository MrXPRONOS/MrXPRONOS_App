#!/usr/bin/env python3
"""2025 reference / 2026 held-out evaluation of ALL 40 BSD V3 markets.

No bookmaker odds invented, no historical fixtures republished, no Supabase.
Crucially each historical prediction uses V2History's 4-hour delayed as-of index.
2024 alone selects Poisson-vs-Dixon-Coles rho. Evaluation uses 2025 only to
estimate a *climatological baseline* and 2026 as a strict later holdout.
"""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from math import isfinite

from bsd_archive import MATCHES_FILE, _read_json
from bsd_v2_core import V2History, fixture_datetime, estimate_goals, outcome_scores, score_matrix, fit_rho_2024
from bsd_v3_40_markets import SPECS, probabilities, result as settle
from bsd_v3_40_calibration import fit_goal_calibration

REPORT_FILE=Path("bsd/v3_market_validation.json")

def thin(events, limit):
    if limit<=0: raise ValueError("sample limit must be positive")
    return events if len(events)<=limit else [events[i*len(events)//limit] for i in range(limit)]

def chronological_rows(index, start, end, limit, rho, calibration=None):
    eligible=[]
    for _available, event in index.global_games:
        try:
            at=fixture_datetime(event)
            if start<=at<end and outcome_scores(event) is not None:
                eligible.append((at,event))
        except (ValueError, TypeError, OverflowError):
            continue
    eligible.sort(key=lambda pair: (pair[0],str(pair[1].get("id"))))
    sample=thin(eligible,limit)
    counts=defaultdict(lambda: {"n":0,"wins":0,"push":0,"brier_sum":0.,
                                "pred_sum":0.,"bins":[[0,0,0.] for _ in range(10)]})
    valid=0
    for at,event in sample:
        estimates,reason=estimate_goals(event,index)
        if estimates is None:
            continue
        score=outcome_scores(event)
        if score is None:continue
        home,away=(calibration.apply(estimates["home"],estimates["away"])
                   if calibration is not None else (estimates["home"],estimates["away"]))
        options=probabilities(score_matrix(home,away,rho))
        if len(options)!=40: raise AssertionError("Invalid 40 market coverage")
        valid+=1
        for opt in options:
            actual=settle(opt["key"],*score)
            row=counts[opt["key"]]
            p=opt["probability"]
            y=int(actual=="win")
            row["n"]+=1
            row["wins"]+=y
            row["push"]+=int(actual=="push")
            row["brier_sum"]+=(p-y)**2
            row["pred_sum"]+=p
            bucket=min(9,max(0,int(p*10)))
            b=row["bins"][bucket];b[0]+=1;b[1]+=y;b[2]+=p
    return counts,{"eligible_games":len(eligible),"sampled":len(sample),
                   "with_pre_match_history":valid,"skipped":len(sample)-valid}

def summarize(train,test):
    summary={}
    for spec in SPECS:
        a,b=train.get(spec.key,{}),test.get(spec.key,{})
        n=int(b.get("n",0));ref_n=int(a.get("n",0))
        baseline_p=a["wins"]/ref_n if ref_n else None
        if n:
            brier=b["brier_sum"]/n
            holdout_rate=b["wins"]/n
            ece=sum(abs(w-s)/n for count,w,s in b["bins"] if count)
            baseline=((b["wins"]*(1-baseline_p)**2 +
                       (n-b["wins"])*baseline_p**2)/n) if baseline_p is not None else None
            sample_bins=[{"bin":j,"count":int(cnt),"observed_win_rate":round(w/cnt,6),
                          "predicted_win_rate":round(p/cnt,6)}
                         for j,(cnt,w,p) in enumerate(b["bins"]) if cnt]
        else:
            brier=holdout_rate=ece=baseline=None
            sample_bins=[]
        validated=(n>=100 and ref_n>=100 and baseline is not None and
                   brier<=baseline and ece<=0.1)
        summary[spec.key]={
            "number":spec.number,"family":spec.group,"samples":n,
            "reference_samples_2025":ref_n,
            "wins":int(b.get("wins",0)),"pushes":int(b.get("push",0)),
            "mean_forecast_probability":round(b["pred_sum"]/n,6) if n else None,
            "observed_win_rate":round(holdout_rate,6) if n else None,
            "test_brier":round(brier,6) if n else None,
            "baseline_brier":round(baseline,6) if baseline is not None else None,
            "ece_10_bins":round(ece,6) if ece is not None else None,
            "reliability_bins":sample_bins,
            "chronological_holdout":True,
            "model_skill_validated":bool(validated),
            "validation_level":"holdout_pass" if validated else "insufficient_or_unvalidated",
            "roi":None,"odds_available":False,
        }
    return summary

def build_report(history, *, clock=None, max_reference=700, max_holdout=700):
    clock=clock or datetime.now(timezone.utc)
    if clock.tzinfo is None:raise ValueError("Timezone-aware clock required")
    index=V2History(history)
    rho,rho_info=fit_rho_2024(index,max_training=400,max_validation=200)
    ref,ref_info=chronological_rows(index,datetime(2025,1,1,tzinfo=timezone.utc),
                         datetime(2026,1,1,tzinfo=timezone.utc),max_reference,rho)
    holdout_end=min(datetime(2027,1,1,tzinfo=timezone.utc),clock-timedelta(days=2))
    test,test_info=chronological_rows(index,datetime(2026,1,1,tzinfo=timezone.utc),
                         holdout_end,max_holdout,rho) if holdout_end>datetime(2026,1,1,tzinfo=timezone.utc) else ({},{})
    cal,cal_info=fit_goal_calibration(index,max_training=max_reference)
    recal_test,recal_info=chronological_rows(index,datetime(2026,1,1,tzinfo=timezone.utc),
                         holdout_end,max_holdout,rho,calibration=cal) if holdout_end>datetime(2026,1,1,tzinfo=timezone.utc) else ({},{})
    markets=summarize(ref,test)
    calibrated=summarize(ref,recal_test)
    for key, row in markets.items():
        alt=calibrated[key]
        row["calibrated_test_brier"]=alt["test_brier"]
        row["calibrated_ece_10_bins"]=alt["ece_10_bins"]
        row["calibrated_model_skill_validated"]=alt["model_skill_validated"]
        row["calibration_brier_improvement"]=(round(row["test_brier"]-alt["test_brier"],6)
             if row["test_brier"] is not None and alt["test_brier"] is not None else None)
    return {
        "format":"bsd-v3-validation-holdout-v1",
        "model":"bsd-v3-40-poisson-dixon-coles-shared-score-model",
        "created_at_utc":clock.isoformat(),
        "reference_period":"2025-01-01/2025-12-31",
        "holdout_period":"2026-01-01/"+holdout_end.date().isoformat(),
        "strict_temporal_order":True,
        "no_future_results_in_features":True,
        "historical_price_snapshots_used":False,
        "profitability_assessed":False,
        "rho_fitted_only_on_2024":True,
        "rho":rho,"rho_diagnostics":rho_info,
        "goal_calibration":cal.to_dict(),"calibration_training":cal_info,
        "calibrated_holdout":recal_info,
        "calibrated_passed_markets":sum(int(v["calibrated_model_skill_validated"]) for v in markets.values()),
        "reference":ref_info,"holdout":test_info,
        "passed_markets":sum(int(v["model_skill_validated"]) for v in markets.values()),
        "total_markets":40,
        "markets":markets
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default=str(REPORT_FILE))
    parser.add_argument("--reference-cap",type=int,default=700)
    parser.add_argument("--holdout-cap",type=int,default=700)
    args=parser.parse_args()
    path=Path(args.output)
    if path.name!="v3_market_validation.json":parser.error("Only V3 validation report allowed")
    history=_read_json(MATCHES_FILE,None)
    if not isinstance(history,list) or not history:parser.error("Restore private BSD licensed history first")
    doc=build_report(history,max_reference=args.reference_cap,max_holdout=args.holdout_cap)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding="utf-8")
    print("V3_HOLDOUT",json.dumps({"reference":doc["reference"],"holdout":doc["holdout"],
        "passed_markets":doc["passed_markets"],"markets":len(doc["markets"]),
        "rho":doc["rho"],"output":str(path)}))
if __name__=="__main__":main()
