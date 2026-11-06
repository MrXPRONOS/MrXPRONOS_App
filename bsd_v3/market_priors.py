"""Market base-rate priors for neutral cross-market ranking.

A broad market such as 1X or Under 3.5 naturally wins more often than a
narrower market. Comparing their raw probabilities directly therefore biases
the featured pick. Priors are fitted only on historical outcomes available
before the 2025 validation period and are used for ranking, never to fabricate
odds or rewrite calibrated probabilities.
"""
from __future__ import annotations
from math import sqrt
from .legacy import fixture_datetime, outcome_scores, markets_from_matrix, score_matrix, realized

_PRIOR_CANDIDATES=markets_from_matrix(score_matrix(1.4,1.2))


def fit_market_priors(index, *, max_events=30000):
    events=[]
    for _,event in index.global_games:
        try:
            dt=fixture_datetime(event)
        except (ValueError,TypeError,OverflowError):
            continue
        if dt.year < 2024 or dt.year > 2025 or (dt.year==2025 and dt.month>8):
            continue
        scores=outcome_scores(event)
        if scores is None:
            continue
        events.append(event)
    if len(events)>max_events:
        events=[events[int(i*len(events)/max_events)] for i in range(max_events)]
    totals={c.key:[0,0] for c in _PRIOR_CANDIDATES}
    for event in events:
        scores=outcome_scores(event)
        for candidate in _PRIOR_CANDIDATES:
            row=totals[candidate.key]
            row[0]+=int(realized(candidate,*scores))
            row[1]+=1
    # Weak beta smoothing prevents 0/1 edge cases without flattening broad
    # structural differences between market types.
    result={}
    for key,(wins,n) in totals.items():
        rate=(wins+2.)/(n+4.) if n else .5
        result[key]={"rate":round(rate,7),"n":n}
    return {"period":"2024-01 through 2025-08",
            "events":len(events),"markets":result}


def neutral_signal(probability, prior):
    """Standardized uplift over the market's own unconditional hit rate."""
    p=float(probability)
    base=float(prior)
    denom=sqrt(max(.01,base*(1-base)))
    return (p-base)/denom


def attach_market_merit(row, priors):
    info=((priors or {}).get("markets") or {}).get(row["key"]) or {"rate":.5,"n":0}
    prior=float(info.get("rate",.5))
    signal=neutral_signal(row["conservative_probability"],prior)
    enriched=dict(row)
    enriched["market_prior_probability"]=round(prior,7)
    enriched["market_prior_samples"]=int(info.get("n",0) or 0)
    enriched["market_probability_lift"]=round(row["conservative_probability"]-prior,7)
    enriched["market_signal_score"]=round(signal,7)
    return enriched
