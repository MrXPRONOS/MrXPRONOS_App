"""BSD V3 research engine: existing free BSD data, never public publishing."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from .legacy import (V2History, estimate_goals, fixture_datetime, fit_rho_2024,
                     markets_from_matrix, score_matrix)
from .calibration import fit_calibration
from .probabilities import prove_coherence
from .policy import V3Policy, classify_fixture, utc_datetime
from .quotes import validate_market_quotes
from .selection import serialize_candidates, select_candidates

VERSION = "bsd-v3-shadow-0.1"

def train_runtime(history, *, calibration=True, challenger=False):
    index=V2History(history)
    rho,rho_report=fit_rho_2024(index)
    cal=fit_calibration(index,rho) if calibration else None
    challenger_models={}
    challenger_info={}
    if challenger:
        from bsd_v2_over_under import fit_total_model
        from bsd_v2_double_chance import fit_model as fit_result_model
        from bsd_v2_btts import fit_btts_model
        for name,fn in (("goals",fit_total_model),("result",fit_result_model),
                        ("btts",fit_btts_model)):
            model,diagnostics=fn(index,rho=rho)
            challenger_models[name]=model
            challenger_info[name]=diagnostics
    return {"index":index,"rho":rho,"rho_validation":rho_report,
            "calibration":cal,"challengers":challenger_models,
            "challenger_training":challenger_info}

def challenger_shadow(event,index,matrix,runtime):
    models=runtime.get("challengers") or {}
    if not models:
        return {}
    baseline=markets_from_matrix(matrix)
    output={}
    for name in ("goals","result","btts"):
        model=models.get(name)
        if model is None:
            continue
        try:
            if name=="goals":
                from bsd_v2_over_under import adjust_candidates
                changed=adjust_candidates(event,index,baseline,model)
            elif name=="result":
                from bsd_v2_double_chance import adjust_candidates
                changed=adjust_candidates(event,index,baseline,model)
            else:
                from bsd_v2_btts import btts_candidates
                changed=btts_candidates(event,index,baseline,model)
            valid_families=("result","double_chance") if name=="result" else (name,)
            output[name]={c.key:round(c.probability,6) for c in changed if c.family in valid_families}
        except (ValueError,TypeError,KeyError,ArithmeticError) as e:
            output[name+"_error"]=type(e).__name__
    return output

def evaluate_fixture(event,runtime,*,now,raw_quotes=None,quote_meta=None,policy=V3Policy()):
    now=utc_datetime(now)
    if not isinstance(event,dict) or event.get("id") is None:
        return {"reason":"missing_id","status":"rejected"}
    try:
        kickoff=fixture_datetime(event)
    except (TypeError,ValueError,OverflowError):
        return {"event_id":str(event["id"]),"status":"rejected","reason":"invalid_kickoff"}
    if str(event.get("status") or "").lower() not in ("notstarted","upcoming") or kickoff<=now:
        return {"event_id":str(event["id"]),"status":"rejected","reason":"not_upcoming"}
    expected,reason=estimate_goals(event,runtime["index"])
    if expected is None:
        return {"event_id":str(event["id"]),"status":"rejected","reason":reason}
    quality=classify_fixture(expected,policy)
    if quality["level"]=="rejected":
        return {"event_id":str(event["id"]),"status":"rejected",
                "reason":quality["reason"],"fixture_quality":quality}
    base=score_matrix(expected["home"],expected["away"],runtime["rho"])
    cal=runtime.get("calibration")
    score=cal.apply(base) if cal is not None else base
    candidates=markets_from_matrix(score)
    prove_coherence(candidates)
    verified,rejected=validate_market_quotes(raw_quotes or {},candidates,
                                             now=now,kickoff=kickoff,policy=policy)
    rows=serialize_candidates(candidates,expected,quality,verified,policy=policy,
                              calibrator=cal,calibration_active=bool(cal and cal.active))
    decisions=select_candidates(rows,score,policy)
    return {"event_id":str(event["id"]),"kickoff_utc":kickoff.isoformat(),
            "generated_at_utc":now.isoformat(),"status":"analyzed",
            "fixture_quality":quality,"estimated_goals":expected,
            "model":VERSION,"calibration_active":bool(cal and cal.active),
            "candidates":rows,"selections":decisions,
            "quote_diagnostics":{"provided":len(raw_quotes or {}),"accepted":len(verified),
                                 "rejected":rejected,"source":quote_meta or {}},
            "challengers":challenger_shadow(event,runtime["index"],base,runtime),
            "published":False,"experimental":True}

def run_shadow(fixtures,history,*,now,quote_fetcher=None,
               policy=V3Policy(),max_odds_events=None,
               enable_challengers=False):
    now=utc_datetime(now)
    runtime=train_runtime(history,challenger=enable_challengers)
    used=0
    results=[]
    reasons=Counter()
    max_events=policy.max_odds_events if max_odds_events is None else max_odds_events
    if not 0<=max_events<=100:
        raise ValueError("Invalid odds request cap")
    for event in fixtures:
        quotes={}
        quote_meta={}
        provisional=evaluate_fixture(event,runtime,now=now,policy=policy)
        if provisional["status"]!="analyzed":
            reasons[provisional["reason"]]+=1
            results.append(provisional)
            continue
        if quote_fetcher and used<max_events:
            used+=1
            try:
                quotes,quote_meta=quote_fetcher(event,now)
            except (ValueError,RuntimeError,KeyError,TypeError) as exc:
                quote_meta={"error":type(exc).__name__}
                reasons["quote_fetch_error"]+=1
        analyzed=evaluate_fixture(event,runtime,now=now,raw_quotes=quotes,
                                 quote_meta=quote_meta,policy=policy)
        results.append(analyzed)
        reasons["analyzed"]+=1
    document={"format":"bsd-v3-shadow-v1","version":VERSION,
              "generated_at_utc":now.isoformat(),"experimental":True,
              "published":False,"no_site_write":True,"no_telegram":True,
              "model_status":"observation_unapproved",
              "calibration":runtime["calibration"].metadata() if runtime["calibration"] else None,
              "rho":runtime["rho"],"challenger_training":runtime["challenger_training"],
              "diagnostics":{"fixtures":len(fixtures),"analyzed":reasons["analyzed"],
                             "odds_events_queried":used,"outcomes":dict(reasons)},
              "matches":results}
    document["fingerprint_sha256"]=hashlib.sha256(
        json.dumps(document,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()
    return document
