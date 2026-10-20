"""Prospective-only pre-match absences correction.

Train ONLY on settled, historically captured pre-match BSD lineups. Enabling
requires a chronological validation improvement over no context correction.
No historical backfill, fabricated absences, or retroactive score rewriting.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from math import exp,log,isfinite
from hashlib import sha256
import json

MIN_ROWS=240
REVISION="mrx-absence-gated-v1"

def utc(value):
    at=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if at.tzinfo is None:raise ValueError("Expected offset-aware timestamp")
    return at.astimezone(timezone.utc)

def source_features(context):
    if not isinstance(context,dict) or not context.get("available"):
        return None
    if context.get("source")!="bsd-v2-events-lineups":
        return None
    values=context.get("values") or {}
    if not isinstance(values,dict):return None
    if values.get("lineup_status") not in ("predicted","confirmed"):
        return None
    h=values.get("home_absences");a=values.get("away_absences")
    if type(h) not in (int,float) or type(a) not in (int,float):
        return None
    if not (isfinite(h) and isfinite(a) and 0<=h<=30 and 0<=a<=30):
        return None
    return (h/10.,a/10.)

def _loss(rows,weights):
    if not rows:return None
    score=0.
    for x,base,actual in rows:
        for side in range(2):
            mu=max(.1,min(5.,base[side]*exp(sum(
                w*f for w,f in zip(weights[side],x)))))
            score+=mu-actual[side]*log(mu)
    return score/len(rows)

def _fit(rows):
    weights=[[0.,0.],[0.,0.]]
    for epoch in range(280):
        grad=[[0.,0.],[0.,0.]]
        for x,base,actual in rows:
            for side in range(2):
                mu=max(.1,min(5.,base[side]*exp(
                    sum(a*b for a,b in zip(weights[side],x)))))
                for i in range(2):grad[side][i]+=(mu-actual[side])*x[i]
        eta=.12/(1+epoch/110.)
        for side in range(2):
            for i in range(2):
                regularizer=.10*weights[side][i]
                weights[side][i]=max(-.5,min(.5,weights[side][i]-
                    eta*(grad[side][i]/len(rows)+regularizer)))
    return tuple(tuple(w) for w in weights)

def learn(ledger,now,observations=None):
    rows=[]
    for record in (ledger.get("records") or {}).values():
        if record.get("status")!="settled":continue
        advanced=record.get("advanced_research") or {}
        context=advanced.get("context") or {}
        sidecar=False
        if source_features(context) is None and observations is not None:
            evidence=(observations.get("records") or {}).get(str(record.get("id")))
            if evidence and evidence.get("forecast_digest")==record.get("forecast_sha256"):
                # Separate immutable source collection after the score was
                # recorded. Validate its own capture time and integrity first.
                from single_exact_score_context_observations import valid as verified
                if (verified(evidence) and
                    evidence.get("forecast_captured_at_utc")==record.get("captured_at") and
                    evidence.get("kickoff_utc")==record.get("kickoff")):
                    context=evidence["context"]
                    sidecar=True
        x=source_features(context)
        if x is None:continue
        # Predicted XI are provider guesses: never use as labelled training
        # evidence or mix with verified confirmed lineups.
        if (context.get("values") or {}).get("lineup_status")!="confirmed":
            continue
        try:
            captured=utc(record["captured_at"])
            kickoff=utc(record["kickoff"])
            observed=utc(context["observed_at_utc"])
            settled=utc(record["settled_at"])
            if ((observed>captured and not sidecar) or observed>now or
                observed>kickoff-timedelta(minutes=30) or
                captured>kickoff-timedelta(minutes=30) or settled>now or
                kickoff>now-timedelta(hours=4)):
                continue
            p=(advanced.get("rest_and_xg") or {}).get("context_free_expected_goals")
            if p is None:
                # Legacy first-seen forecasts before the context learner
                # existed have context_model_applied=False and are safe.
                # Forbid rows where the stored expected goals include our own
                # learned absence adjustment: feedback would compound itself.
                if advanced.get("context_model_applied"):
                    continue
                p=advanced["expected_goals"]
            base=(float(p["home"]),float(p["away"]))
            actual=tuple(record["actual_score"])
            if (len(actual)!=2 or any(type(y)!=int or y<0 for y in actual)
                or any(not isfinite(v) or v<=0 for v in base)):
                continue
            rows.append((captured,x,base,actual))
        except (KeyError,TypeError,ValueError,OverflowError):
            continue
    rows.sort(key=lambda row:row[0])
    diag={"eligible":len(rows),"min_required":MIN_ROWS,
          "source":"immutable prospective settled rows only",
          "validation_baseline":None,"validation_candidate":None}
    if len(rows)<MIN_ROWS:
        return {"active":False,"weights":((0.,0.),(0.,0.)),
                "diagnostic":{**diag,"reason":"insufficient_verified_prematch_absences"}}
    cut=int(len(rows)*.75)
    tr=[(x,base,actual) for _,x,base,actual in rows[:cut]]
    val=[(x,base,actual) for _,x,base,actual in rows[cut:]]
    if len(val)<60 or len(tr)<180:
        return {"active":False,"weights":((0.,0.),(0.,0.)),
                "diagnostic":{**diag,"reason":"insufficient_validation"}}
    trained=_fit(tr)
    loss0=_loss(val,((0.,0.),(0.,0.)))
    loss1=_loss(val,trained)
    active=(loss0-loss1)>.005
    return {"active":active,"weights":trained if active else ((0.,0.),(0.,0.)),
            "diagnostic":{**diag,"validation_baseline":round(loss0,6),
                "validation_candidate":round(loss1,6),
                "reason":"validated" if active else "no_verified_gain"}}

def fingerprint(model):
    data={"revision":REVISION,"active":bool(model.get("active")),
          "weights":model.get("weights"),"diagnostic":model.get("diagnostic")}
    return sha256(json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def adjust(home,away,context,model):
    """No valid context or no validation: EXACT mathematical no-op."""
    if not model or not model.get("active"):return home,away,False
    x=source_features(context)
    if x is None or (context.get("values") or {}).get("lineup_status")!="confirmed":
        return home,away,False
    weights=model["weights"]
    mu=[home,away]
    values=tuple(max(.1,min(5.,mu[i]*exp(sum(
        w*v for w,v in zip(weights[i],x))))) for i in range(2))
    return values[0],values[1],True
