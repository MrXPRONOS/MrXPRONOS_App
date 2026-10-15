"""Additional diagnostics for authorized, offline bookmaker JSON exports."""
import datetime
import json
import math
import pathlib
import sys

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from diagnostic import analyze

def validate(payload, provider, mode="unknown"):
    findings=[]
    if mode not in ("prematch","live","unknown"):
        raise ValueError("mode must be prematch, live, or unknown")
    if not isinstance(payload,(dict,list)):
        return {"provider":provider,"mode":mode,"valid":False,"findings":["root_not_object_or_list"],"analysis":None}
    try:
        result=analyze(payload,provider)
    except (TypeError,ValueError,AttributeError,KeyError) as exc:
        return {"provider":provider,"mode":mode,"valid":False,"findings":["unexpected_structure:"+type(exc).__name__],"analysis":None}
    if result["events"]==0: findings.append("no_events")
    if result["markets_inspected"]==0: findings.append("no_markets")
    if result["unmapped_numeric_markets"]: findings.append("unmapped_numeric_market_codes")
    if not any(m["valid_odds"] for m in result["markets"]): findings.append("no_verified_target_odds")
    if mode=="live": findings.append("live_freshness_not_verified")
    return {"provider":provider,"mode":mode,"valid":bool(result["events"]) and bool(result["markets_inspected"]),"findings":findings,"analysis":result}

def compare_snapshots(before,after,provider,elapsed_seconds):
    a=validate(before,provider,"live")
    b=validate(after,provider,"live")
    return {"provider":provider,"interval_seconds":elapsed_seconds,
            "before_markets":a["analysis"]["markets_inspected"] if a["analysis"] else None,
            "after_markets":b["analysis"]["markets_inspected"] if b["analysis"] else None,
            "freshness_verified":False,
            "warning":"Two snapshots without authoritative source timestamps cannot prove live updates."}
