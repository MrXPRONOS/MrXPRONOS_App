"""Two-match combined coupons using genuine, low BSD pre-match odds.

- Every leg has 1.01 <= odds < 1.50 (never 1.50 or above).
- The best eligible market from a fixture's first or second prediction can be used.
- Both legs always belong to different fixtures.
- The generated coupon never claims a bookmaker accepted a real wager.
"""
from __future__ import annotations
from hashlib import sha256
from math import isfinite
from bsd_h2h import _utc

COMBO_MIN_ODDS=1.01
COMBO_MAX_ODDS=1.50
SOURCES=frozenset(("bsd_consensus","bsd_bookmaker"))

def priced_prediction(p):
    if not isinstance(p,dict):return False
    price=p.get("odds")
    return (type(price) in (int,float) and isfinite(price)
            and COMBO_MIN_ODDS <= price < COMBO_MAX_ODDS
            and p.get("selection_key") not in ("UNDER_45",None,"")
            and p.get("odds_source") in SOURCES)

def match_selections(match):
    primary=match.get("prediction") or {}
    all_picks=match.get("predictions") or [primary]
    if not isinstance(all_picks,list):all_picks=[primary]
    unique={}
    for pick in [match.get("combo_prediction"),primary,*all_picks]:
        if isinstance(pick,dict) and pick.get("selection_key"):
            unique.setdefault(pick["selection_key"],pick)
    return list(unique.values())

def choose_leg(match):
    if not isinstance(match,dict) or match.get("source")!="bsd":return None
    if match.get("status") not in ("notstarted","upcoming"):return None
    picks=[p for p in match_selections(match) if priced_prediction(p)]
    if not picks:return None
    # Highest calibrated confidence wins; price only breaks confidence ties.
    pick=max(picks,key=lambda p:(float(p.get("confidence") or 0),float(p["odds"]),
                                 str(p["selection_key"])))
    return {**match,"prediction":pick}

def eligible(match):
    # Supports both original feed fixtures and frozen combo leg snapshots.
    return choose_leg(match) is not None

def build_combos(matches,*,max_kickoff_gap_hours=24):
    valid=[]
    seen=set()
    for match in matches:
        leg=choose_leg(match)
        if leg is None:continue
        identity=str(leg.get("source_event_id") or leg["id"])
        if identity in seen:continue
        seen.add(identity)
        valid.append(leg)
    valid.sort(key=lambda m:(_utc(m["event_date"]),str(m["id"])))
    combos=[]
    used=set()
    for i,a in enumerate(valid):
        aid=str(a.get("source_event_id") or a["id"])
        if aid in used:continue
        for b in valid[i+1:]:
            bid=str(b.get("source_event_id") or b["id"])
            if bid==aid or bid in used:continue
            delta=(_utc(b["event_date"])-_utc(a["event_date"])).total_seconds()
            if delta>max_kickoff_gap_hours*3600:break
            k1,k2=a["prediction"]["selection_key"],b["prediction"]["selection_key"]
            identity="|".join((str(a["id"]),k1,str(b["id"]),k2))
            tag=sha256(identity.encode("utf-8")).hexdigest()[:18]
            odd1,odd2=float(a["prediction"]["odds"]),float(b["prediction"]["odds"])
            combos.append({
                "id":"combo:"+tag,"type":"combiné","status":"upcoming",
                "event_date":a["event_date"],"date":_utc(a["event_date"]).date().isoformat(),
                "legs":[a,b],"combined_odds":round(odd1*odd2,5),
                "stake":500000,"potential_gain":round(500000*odd1*odd2,2),
            })
            used.update((aid,bid))
            break
    return combos

def due_combos(combos,now,*,min_minutes=45,max_minutes=65):
    result=[]
    for combo in combos:
        legs=combo.get("legs") or []
        if len(legs)!=2:continue
        delta=(_utc(combo["event_date"])-now).total_seconds()/60
        if min_minutes<=delta<max_minutes and all(priced_prediction(l.get("prediction")) for l in legs):
            first=str(legs[0].get("source_event_id") or legs[0]["id"])
            second=str(legs[1].get("source_event_id") or legs[1]["id"])
            if first!=second:result.append(combo)
    return result
