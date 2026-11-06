"""Paired V2-vs-V3 retrospective model comparison without fabricated quotes.

This compares calibrated pre-price model predictions on IDENTICAL fixtures,
not actual past publications (which can depend on live bookmaker odds).
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import timedelta
from math import log,sqrt
from .legacy import (V2History,estimate_goals,fixture_datetime,outcome_scores,
                     score_matrix,markets_from_matrix,realized,fit_rho_2024)
from .calibration import fit_calibration
from .policy import V3Policy,classify_fixture,public_candidate,uncertainty_adjustment
from .probabilities import prove_coherence

def _clip(p):
    return max(1e-6,min(1-1e-6,p))

def _wilson(wins,total):
    if total==0:return None
    z=1.96
    p=wins/total
    center=(p+z*z/(2*total))/(1+z*z/total)
    half=z*sqrt((p*(1-p)+z*z/(4*total))/total)/(1+z*z/total)
    return [round(max(0,center-half),4),round(min(1,center+half),4)]

def _logloss(p,y):
    p=_clip(p)
    return -(y*log(p)+(1-y)*log(1-p))

def build_models(index,rho):
    from bsd_v2_over_under import fit_total_model
    from bsd_v2_double_chance import fit_model as fit_dc_model
    from bsd_v2_btts import fit_btts_model
    from bsd_v2_policies import fit_policy
    total,_=fit_total_model(index,rho=rho)
    dc,_=fit_dc_model(index,rho=rho)
    btts,_=fit_btts_model(index,rho=rho)
    cal,policy,diag=fit_policy(index,rho=rho,btts_model=btts,total_model=total,dc_model=dc)
    return {"goals":total,"result":dc,"btts":btts},cal,policy,diag

def v2_all_markets(event,index,rho,models,calibration):
    """Replicate V2's pre-price specialized and calibrated probabilities."""
    from bsd_v2_over_under import adjust_candidates as adjust_goals
    from bsd_v2_double_chance import adjust_candidates as adjust_result
    from bsd_v2_btts import btts_candidates as adjust_btts
    from bsd_v2_core import _calibrated
    expected,reason=estimate_goals(event,index)
    if expected is None:return None
    base=markets_from_matrix(score_matrix(expected["home"],expected["away"],rho))
    base=adjust_goals(event,index,base,models["goals"])
    base=adjust_btts(event,index,base,models["btts"])
    base=adjust_result(event,index,base,models["result"],
                       getattr(calibration,"outcome_calibration",None))
    return {c.key:_calibrated(c,calibration)[0] for c in base}

def compare_all_markets(history, *, year=2026,max_matches=700,
                        challengers=False,min_pair=50):
    if year<=2025:
        raise ValueError("Evaluation before calibration holdout is forbidden")
    index=V2History(history)
    rho,_=fit_rho_2024(index)
    models,v2_cal,v2_policy,v2_diag=build_models(index,rho)
    v3_cal=fit_calibration(index,rho)
    weights={}
    gates={}
    if challengers:
        from .ensemble import fit_gate
        weights,gates=fit_gate(index,rho,models)
    events=sorted((e for _,e in index.global_games if fixture_datetime(e).year==year),
                  key=lambda e:(fixture_datetime(e),str(e.get("id"))))
    if len(events)>max_matches:
        events=[events[int(i*len(events)/max_matches)] for i in range(max_matches)]
    from bsd_v2_core import predict_v2
    from bsd_v2_publication_policy import eligible_model_choice
    by_market=defaultdict(lambda:{"n":0,"wins":0,"v2_brier":0.,"v3_brier":0.,
                                  "v2_logloss":0.,"v3_logloss":0.,"diffs":[]})
    coverage=Counter()
    matched_picks=Counter()
    for event in events:
        expected,_=estimate_goals(event,index)
        if expected is None:
            coverage["no_history"]+=1
            continue
        kickoff=fixture_datetime(event)
        historical=dict(event,status="notstarted",home_score=None,away_score=None)
        base=score_matrix(expected["home"],expected["away"],rho)
        v3_matrix=v3_cal.apply(base)
        if any(weights.values()):
            from .ensemble import projected_matrix
            v3_matrix=projected_matrix(event,index,v3_matrix,models,weights)
        v3_rows=markets_from_matrix(v3_matrix)
        prove_coherence(v3_rows)
        raw_v2=v2_all_markets(event,index,rho,models,v2_cal)
        if raw_v2 is None:continue
        hs,aws=outcome_scores(event)
        for c in v3_rows:
            if c.key not in raw_v2:continue
            p2=_clip(raw_v2[c.key]);p3=_clip(c.probability)
            y=realized(c,hs,aws)
            row=by_market[c.key]
            row["n"]+=1
            row["wins"]+=y
            loss2=(p2-y)**2;loss3=(p3-y)**2
            row["v2_brier"]+=loss2;row["v3_brier"]+=loss3
            row["v2_logloss"]+=_logloss(p2,y)
            row["v3_logloss"]+=_logloss(p3,y)
            row["diffs"].append(loss3-loss2)
        coverage["paired_fixtures"]+=1
        # Pre-price selection comparison, NOT actual publication or ROI.
        v2_forecast,_=predict_v2(historical,index,calibration=v2_cal,
                                  quality_policy=v2_policy,rho=rho,
                                  clock=kickoff-timedelta(seconds=1),mode="reliability",
                                  btts_model=models["btts"],
                                  total_model=models["goals"],dc_model=models["result"])
        if v2_forecast is not None and eligible_model_choice(v2_forecast):
            coverage["v2_pro_vip_eligible_preprice"]+=1
            v2key=v2_forecast["prediction"]["key"]
            matched_picks[("v2",v2key)]+=1
        quality=classify_fixture(expected,V3Policy())
        v3qualified=[]
        if quality["level"]!="rejected":
            safety=uncertainty_adjustment(expected,quality,
                                          calibration_samples=v3_cal.trained if v3_cal.active else 0)
            for c in v3_rows:
                row={"key":c.key,"probability":c.probability,
                     "conservative_probability":max(0,c.probability-safety)}
                if public_candidate(row,quality):
                    v3qualified.append(row)
        if v3qualified:
            coverage["v3_pro_vip_eligible_preprice"]+=1
            winner=max(v3qualified,key=lambda x:x["conservative_probability"])
            matched_picks[("v3",winner["key"])]+=1
    markets={}
    for key,v in sorted(by_market.items()):
        n=v["n"]
        if n==0:continue
        diffs=v["diffs"];mean=sum(diffs)/n
        var=sum((x-mean)**2 for x in diffs)/(n-1) if n>1 else 0
        ci=[round(mean-1.96*sqrt(var/n),6),round(mean+1.96*sqrt(var/n),6)] if n>1 else None
        markets[key]={"n":n,"hits":v["wins"],"hit_rate":round(v["wins"]/n,5),
                      "wilson_95":_wilson(v["wins"],n),
                      "v2_brier":round(v["v2_brier"]/n,6),
                      "v3_brier":round(v["v3_brier"]/n,6),
                      "paired_v3_minus_v2_brier":round(mean,6),
                      "normal_approx_95_ci":ci,
                      "v2_logloss":round(v["v2_logloss"]/n,6),
                      "v3_logloss":round(v["v3_logloss"]/n,6),
                      "sufficient_sample":n>=min_pair}
    return {"format":"bsd-v3-paired-model-comparison-v1",
            "tested_year":year,"fixtures_examined":len(events),
            "coverage":dict(coverage),
            "preprice_market_counts":{
                "v2":{k[1]:n for k,n in matched_picks.items() if k[0]=="v2"},
                "v3":{k[1]:n for k,n in matched_picks.items() if k[0]=="v3"}},
            "v3_calibration":v3_cal.metadata(),
            "v3_challenger_weights":weights,
            "v3_challenger_gates":gates,
            "v2_calibration":v2_diag,
            "markets":markets,"real_bookmaker_roi":None,
            "warnings":[
                "Retrospective, not independent prospective validation.",
                "Original V2 pre-price models are compared; NOT historic live V2 publications.",
                "Paired normal intervals ignore some temporal/league correlations.",
                "Actual bookmaker quotes are unavailable historically: ROI not computed.",
                "A higher number of picks is NOT evidence of better predictive quality."
            ]}
