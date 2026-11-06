"""Validate fully timestamped observed prices; no model-derived prices become quotes.

BSD consensus is an observed *benchmark*, not a bookmaker's executable offer.
"""
from __future__ import annotations
from datetime import timedelta
from math import isfinite
from .policy import V3Policy, utc_datetime

SUPPORTED_ORIGINS = frozenset({
    "bsd_bookmaker","bsd_consensus","pinnwire","oddslink",
    "oddslink_public","moviodds","oddsharvester",
})

def validate_quote(raw, *, now, kickoff, policy=V3Policy()):
    if not isinstance(raw, dict):
        return None, "missing_quote"
    if raw.get("estimated") is True or raw.get("origin") not in SUPPORTED_ORIGINS:
        return None, "unverified_origin"
    price=raw.get("odds")
    if (type(price) not in (int,float) or not isfinite(price)
            or not policy.min_odds <= price <= 100):
        return None, "invalid_price"
    try:
        now, kickoff=utc_datetime(now),utc_datetime(kickoff)
        captured=utc_datetime(raw["captured_at"])
        updated=utc_datetime(raw["updated_at"])
    except (KeyError,ValueError,TypeError):
        return None, "invalid_timestamps"
    if not updated <= captured <= now < kickoff:
        return None, "not_prematch_or_future"
    if (now - updated).total_seconds() > policy.max_quote_age_seconds:
        return None, "stale_quote"
    if raw.get("quote_timestamp_verified") is False:
        return None, "unverified_timestamp"
    bookmaker=str(raw.get("bookmaker") or "").strip()
    if not bookmaker:
        return None, "missing_provider"
    # Only a named bookmaker may eventually be used as evidence of a
    # bookmaker offer. Free BSD consensus remains a non-executable benchmark.
    executable=raw["origin"]=="bsd_bookmaker" and bookmaker.lower()!="consensus"
    return {"odds":float(price), "bookmaker":bookmaker,
            "origin":raw["origin"],"captured_at":captured.isoformat(),
            "updated_at":updated.isoformat(),"verified":True,
            "executable":executable,"benchmark_only":not executable}, "ok"

def validate_market_quotes(quotes, candidates, *, now, kickoff, policy=V3Policy()):
    codes={c.market_code for c in candidates}
    valid={}
    rejected={}
    if not isinstance(quotes,dict):
        return valid, {"payload":"invalid_quotes"}
    for code,raw in quotes.items():
        if code not in codes:
            rejected[code]="unrecognized_market"
            continue
        result,reason=validate_quote(raw,now=now,kickoff=kickoff,policy=policy)
        if result is None:
            rejected[code]=reason
        else:
            valid[code]=result
    return valid,rejected
