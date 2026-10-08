"""Select two distinct football fixtures for a hypothetical double coupon.

All legs must be qualified BSD V2 markets with authentic quoted odds >=1.20.
No fixed synthetic bookmaker odds. One leg per game, no same-event parlay.
"""
from __future__ import annotations
from datetime import datetime
from hashlib import sha256
from bsd_h2h import _utc

def eligible(match):
    if not isinstance(match,dict) or match.get("source")!="bsd":return False
    if match.get("status") not in ("notstarted","upcoming"):return False
    p=match.get("prediction") or {}
    price=p.get("odds")
    return (type(price) in (int,float) and 1.20<=price<=100 and
            p.get("selection_key") and p["selection_key"]!="UNDER_45"
            and p.get("odds_source") in ("bsd_consensus","bsd_bookmaker"))

def build_combos(matches,*,max_kickoff_gap_hours=24):
    """Stable, disjoint pairing by kickoff; only two different event IDs."""
    valid=sorted((m for m in matches if eligible(m)),
                 key=lambda m:(_utc(m["event_date"]),str(m["id"])))
    # Match selection remains immutable for this feed version. No duplicate leg.
    grouped=[];used=set()
    for i,a in enumerate(valid):
        if a["id"] in used:continue
        for b in valid[i+1:]:
            if b["id"] in used or str(a.get("source_event_id"))==str(b.get("source_event_id")):continue
            if (_utc(b["event_date"])-_utc(a["event_date"])).total_seconds()>max_kickoff_gap_hours*3600:break
            k1,k2=(a["prediction"]["selection_key"],b["prediction"]["selection_key"])
            identity="|".join((str(a["id"]),k1,str(b["id"]),k2))
            tag=sha256(identity.encode()).hexdigest()[:18]
            odd1,odd2=float(a["prediction"]["odds"]),float(b["prediction"]["odds"])
            grouped.append({
                "id":"combo:"+tag,"type":"combiné","status":"upcoming",
                "event_date":a["event_date"],"date":_utc(a["event_date"]).date().isoformat(),
                "legs":[a,b],"combined_odds":round(odd1*odd2,5),
                "stake":500000,"potential_gain":round(500000*odd1*odd2,2),
            })
            used.update((a["id"],b["id"]))
            break
    return grouped

def due_combos(combos,now,*,min_minutes=0,max_minutes=60):
    selected=[]
    for c in combos:
        if len(c.get("legs",[]))!=2:continue
        delta=(_utc(c["event_date"])-now).total_seconds()/60
        if min_minutes<=delta<max_minutes and all(eligible(m) for m in c["legs"]):
            selected.append(c)
    return selected
