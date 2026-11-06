"""Chronological V3 vs baseline test: no fictitious historical odds or ROI."""
from __future__ import annotations
from collections import defaultdict,Counter
from math import log
from .legacy import (V2History, estimate_goals, fixture_datetime, outcome_scores,
                     score_matrix, markets_from_matrix, realized, fit_rho_2024)
from .calibration import fit_calibration
from .probabilities import prove_coherence

def retrospective(history,*,year=2026,max_matches=1500):
    index=V2History(history)
    rho,_=fit_rho_2024(index)
    cal=fit_calibration(index,rho)
    events=sorted((m for _,m in index.global_games if fixture_datetime(m).year==year),
                  key=lambda e:(fixture_datetime(e),str(e.get("id"))))[:max_matches]
    by_key=defaultdict(lambda:{"n":0,"wins":0,"baseline_brier":0.,"v3_brier":0.,
                               "baseline_logloss":0.,"v3_logloss":0.})
    total=Counter()
    for e in events:
        features,reason=estimate_goals(e,index)
        if features is None:
            total["skipped"]+=1
            continue
        base=score_matrix(features["home"],features["away"],rho)
        original=markets_from_matrix(base)
        upgraded=markets_from_matrix(cal.apply(base))
        prove_coherence(upgraded)
        actual=outcome_scores(e)
        for a,b in zip(original,upgraded):
            if a.key!=b.key: raise AssertionError("Misaligned market keys")
            won=realized(a,*actual)
            row=by_key[a.key]
            row["n"]+=1
            row["wins"]+=won
            row["baseline_brier"]+=(a.probability-won)**2
            row["v3_brier"]+=(b.probability-won)**2
            row["baseline_logloss"]-=won*log(max(.00001,a.probability))+(1-won)*log(max(.00001,1-a.probability))
            row["v3_logloss"]-=won*log(max(.00001,b.probability))+(1-won)*log(max(.00001,1-b.probability))
        total["analyzed"]+=1
    markets={}
    for key,v in by_key.items():
        n=v["n"]
        markets[key]={"n":n,"hit_rate":round(v["wins"]/n,5),
                      "baseline_brier":round(v["baseline_brier"]/n,6),
                      "v3_brier":round(v["v3_brier"]/n,6),
                      "baseline_logloss":round(v["baseline_logloss"]/n,6),
                      "v3_logloss":round(v["v3_logloss"]/n,6)}
    return {"format":"bsd-v3-retrospective-v1","year":year,"checked":len(events),
            "analyzed":total["analyzed"],"skipped":total["skipped"],
            "v3_calibration":cal.metadata(),"markets":markets,"real_quote_roi":None,
            "warning":"Retrospective analysis, not independent prospective proof. "
                      "This year may already have influenced design decisions. "
                      "No historic bookmaker snapshots; ROI intentionally unavailable."}
