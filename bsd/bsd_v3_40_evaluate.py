"""Out-of-time evaluation and per-market settlement metrics for V3 shadow.
Never claims historical betting ROI if no actual verified odds snapshots are available.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from math import isfinite
from bsd_v3_40_markets import settle_market

def evaluate(forecasts, results):
    """forecasts: pre-match shadow snapshots; results: provider results indexed by source event id.
    Results must include status/score and an event date. Only forecasts strictly earlier
    than kickoff can be evaluated. quote if present must have verified true + odds.
    """
    by_key=defaultdict(lambda:{"samples":0,"wins":0,"losses":0,"pushes":0,
                               "brier_total":0.,"net_units":0.,"priced":0})
    for event in forecasts:
        kickoff=datetime.fromisoformat(event["event_date"].replace("Z","+00:00"))
        generated=datetime.fromisoformat(event["generated_at_utc"].replace("Z","+00:00"))
        if generated >= kickoff or generated.tzinfo is None or kickoff.tzinfo is None:
            continue
        actual=results.get(str(event["source_event_id"]))
        if not actual:continue
        for row in event.get("markets",[]):
            verdict=settle_market(row["key"],status=actual.get("status"),
                                  home_score=actual.get("home_score"),
                                  away_score=actual.get("away_score"))
            if verdict not in ("win","lose","push"):continue
            m=by_key[row["key"]]
            m["samples"]+=1
            m["wins"]+=int(verdict=="win")
            m["losses"]+=int(verdict=="lose")
            m["pushes"]+=int(verdict=="push")
            # Brier loss for win probability: outcome includes pushes as non-wins.
            y=int(verdict=="win")
            m["brier_total"]+=(float(row["probability"])-y)**2
            quote=(event.get("quotes") or {}).get(row["key"])
            if (isinstance(quote,dict) and quote.get("verified") is True
                and quote.get("estimated") is not True):
                try:odds=float(quote["odds"])
                except (TypeError,ValueError):continue
                if not(isfinite(odds) and odds>1):continue
                m["priced"]+=1
                m["net_units"]+=(odds-1 if verdict=="win" else 0 if verdict=="push" else -1)
    summary={}
    for key,m in sorted(by_key.items()):
        n=m["samples"]
        summary[key]={
            "samples":n,"wins":m["wins"],"losses":m["losses"],"pushes":m["pushes"],
            "hit_rate_excluding_pushes":round(m["wins"]/max(1,m["wins"]+m["losses"]),6),
            "brier":round(m["brier_total"]/n,6),
            "priced_samples":m["priced"],
            "roi_verified_quotes":round(m["net_units"]/m["priced"],6) if m["priced"] else None,
            "valuation_status":"unverified_no_odds" if not m["priced"] else "observed_not_proven",
        }
    return {"format":"bsd-v3-market-evaluation-v1","markets":summary,
            "historical_profitability_guaranteed":False}
