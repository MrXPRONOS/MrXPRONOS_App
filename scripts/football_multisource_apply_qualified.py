#!/usr/bin/env python3
"""Apply only fully qualified multisource rows to the BSD public feed.

The upstream gate must already have:
- independently corroborated the schedule,
- replaced research identity with an official native BSD event ID,
- frozen the BSD V2-selected market,
- attached a fresh real BSD consensus price for that exact market,
- passed the existing V2.1/value guard,
- created the row through bsd_v2_publish.assemble() itself.

This module does not score, price, lower thresholds, send Telegram, or invent IDs.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT,ROOT/"bsd"):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from bsd_v2_estimated_odds import valid_standalone_prediction
from scripts.football_match_source_router import aware_time
from scripts.football_multisource_market_gate import _official_row_event_id
from bsd_v2_publish import historical_publication_ids

REQUIRED_PROOF=(
    "schedule_corroborated",
    "native_bsd_event_verified",
    "selected_market_real_consensus_price",
    "v21_and_value_guard_passed",
    "production_assembler_created_row",
)


def _selection_signature(row):
    picks=row.get("predictions") or [row.get("prediction")]
    return tuple(str(p.get("selection_key")) for p in picks if isinstance(p,dict))


def _validate_qualified_row(row, *, now):
    if not isinstance(row,dict) or row.get("source")!="bsd":
        raise ValueError("Qualified candidate must retain BSD source")
    ident=_official_row_event_id(row)
    if ident is None:
        raise ValueError("Qualified candidate lacks official BSD event ID")
    if row.get("id")!=f"bsd:{ident}" or str(row.get("source_event_id"))!=str(ident):
        raise ValueError("Qualified candidate has conflicting BSD identity fields")
    kickoff=aware_time(row.get("event_date"))
    if kickoff is None or not (now < kickoff <= now+timedelta(days=2)):
        raise ValueError("Qualified candidate is outside native 48h publication window")
    proof=row.get("multisource_verification")
    if not isinstance(proof,dict) or proof.get("mode")!="qualified_external_candidate":
        raise ValueError("Qualified candidate provenance missing")
    if any(proof.get(key) is not True for key in REQUIRED_PROOF):
        raise ValueError("Qualified candidate proof is incomplete")
    picks=row.get("predictions") or [row.get("prediction")]
    if not 1<=len(picks)<=2:
        raise ValueError("Qualified candidate prediction count invalid")
    keys=set()
    markets=set()
    for pick in picks:
        if not isinstance(pick,dict) or not valid_standalone_prediction(pick,row.get("combo_only",False)):
            raise ValueError("Qualified candidate contains invalid prediction")
        if pick.get("odds_source")!="bsd_consensus" or pick.get("estimated_odds") is not False:
            raise ValueError("Qualified candidate requires real BSD consensus pricing")
        key=pick.get("selection_key")
        market=pick.get("market")
        if not key or not market or key in keys or market in markets:
            raise ValueError("Qualified candidate contains duplicate market/selection")
        keys.add(key); markets.add(market)
    if picks[0].get("selection_key")!=(row.get("prediction") or {}).get("selection_key"):
        raise ValueError("Primary prediction differs from predictions[0]")
    return ident


def _safe_pipeline_coverage(aggregate, staged):
    """Only aggregate integer counters; never leak event, club or quote data."""
    if aggregate is None:
        return None
    if not isinstance(aggregate,dict):
        raise ValueError("Malformed multisource aggregate report")

    def metric(obj,name):
        val=obj.get(name) if isinstance(obj,dict) else None
        if type(val) is not int or not 0<=val<=1_000_000:
            raise ValueError("Missing or invalid multisource coverage counter: "+name)
        return val

    price=aggregate.get("read_only_native_consensus_price_audit")
    model=aggregate.get("full_model_selected_market_consensus_audit")
    market=model.get("aggregate") if isinstance(model,dict) else None
    canary=model.get("native_full_assembler_canary") if isinstance(model,dict) else None
    result={
        "public_fixtures_found":metric(aggregate,"external_total"),
        "independent_calendar_confirmed":metric(aggregate,"independent_cc0_calendar_confirmed"),
        "official_bsd_event_links":metric(aggregate,"one_to_one_native_event_links"),
        "historical_events_excluded_from_price_probes":
            metric(price,"historically_published_native_links_excluded"),
        "unpublished_events_within_48h":metric(price,"unpublished_native_links_in_48h_window"),
        "quote_probe_attempts":metric(price,"official_native_events_quoted_attempts"),
        "quote_attempts_within_48h":metric(price,"actual_48h_publication_window_quote_attempts"),
        "fresh_consensus_market_prices":metric(price,"fresh_consensus_market_prices"),
        "football_model_market_candidates":metric(market,"frozen_bsd_v2_model_market_candidates"),
        "selected_markets_with_fresh_consensus_price":
            metric(market,"frozen_markets_with_exact_fresh_bsd_consensus_quote"),
        "v21_or_value_guard_rejected":metric(market,"v21_or_value_guard_veto"),
        "v21_insufficient_real_price_edge":
            metric(market,"v21_reason:v21_insufficient_real_price_edge") if
            "v21_reason:v21_insufficient_real_price_edge" in (market or {}) else 0,
        "v21_over15_conservative_too_low":
            metric(market,"v21_reason:v21_over15_conservative_too_low") if
            "v21_reason:v21_over15_conservative_too_low" in (market or {}) else 0,
        "native_assembler_events_within_48h":
            metric(canary,"events_within_native_48h_window"),
        "qualified_candidates":metric(aggregate,"qualified_candidate_rows_staged"),
    }
    if (result["qualified_candidates"]!=staged
        or result["independent_calendar_confirmed"]>result["public_fixtures_found"]
        or result["official_bsd_event_links"]>result["independent_calendar_confirmed"]
        or result["quote_attempts_within_48h"]>result["quote_probe_attempts"]
        or result["quote_probe_attempts"]>8
        or result["selected_markets_with_fresh_consensus_price"]>
            result["football_model_market_candidates"]
        or result["v21_insufficient_real_price_edge"]+
            result["v21_over15_conservative_too_low"]>
            result["v21_or_value_guard_rejected"]):
        raise ValueError("Multisource aggregate counters are inconsistent")
    return result


def apply(feed, accepted, *, now, publication_ledger, aggregate_report=None):
    if now.tzinfo is None:
        raise ValueError("Timezone-aware now required")
    now=now.astimezone(timezone.utc)
    if not isinstance(feed,dict) or feed.get("source")!="bsd" or not isinstance(feed.get("matches"),list):
        raise ValueError("Invalid BSD production feed")
    if not isinstance(accepted,list) or len(accepted)>8:
        raise ValueError("Qualified candidate staging must contain at most 8 rows")
    # The public feed is a display window. A retired event may already be
    # recorded in the append-only ledger despite being absent from data.json.
    historical_ids=historical_publication_ids(publication_ledger,feed)

    existing={}
    for row in feed["matches"]:
        ident=_official_row_event_id(row)
        if ident is not None:
            if ident in existing:
                raise ValueError("Existing BSD feed contains duplicate native event ID")
            existing[ident]=row

    additions=[]
    added=[]
    duplicates=0
    staged_ids=set()
    for candidate in accepted:
        ident=_validate_qualified_row(candidate,now=now)
        if ident in staged_ids:
            raise ValueError("Duplicate qualified event in staging")
        staged_ids.add(ident)
        if ident in existing:
            if _selection_signature(existing[ident])!=_selection_signature(candidate):
                raise ValueError("Qualified candidate attempts to alter an existing published selection")
            duplicates+=1
            continue
        if str(ident) in historical_ids:
            raise ValueError("Qualified candidate would re-publish an event retired from the public feed")
        clone=deepcopy(candidate)
        additions.append(clone)
        existing[ident]=clone
        added.append(ident)

    # Validate every candidate before making ANY in-memory feed modification.
    diagnostics=feed.get("diagnostics",{})
    if not isinstance(diagnostics,dict):
        raise ValueError("Malformed production diagnostics")
    diagnostics=deepcopy(diagnostics)
    coverage=_safe_pipeline_coverage(aggregate_report,len(accepted))
    diagnostics["multisource_generation"]={
        "enabled":True,
        "mode":"qualified_external_candidates_through_native_bsd_v2",
        "staged_rows":len(accepted),
        "added_rows":len(added),
        "already_present_same_selection":duplicates,
        "max_staged_rows":8,
        "requires_official_bsd_event_id":True,
        "requires_real_bsd_consensus_selected_market_price":True,
        "requires_v21_and_value_guard":True,
        "uses_native_bsd_v2_assembler":True,
        "thresholds_lowered":False,
        "telegram_sent_by_this_step":False,
    }
    if coverage is not None:
        diagnostics["multisource_generation"]["coverage"]=coverage
    feed["matches"].extend(additions)
    feed["diagnostics"]=diagnostics
    return {"staged":len(accepted),"added":len(added),"duplicates":duplicates}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--feed",required=True)
    p.add_argument("--accepted",required=True)
    p.add_argument("--ledger",required=True,help="Immutable BSD publication ledger")
    p.add_argument("--aggregate",required=True,help="Aggregate-only identity and market audit")
    p.add_argument("--now")
    a=p.parse_args()
    path=Path(a.feed)
    feed=json.loads(path.read_text(encoding="utf-8"))
    accepted=json.loads(Path(a.accepted).read_text(encoding="utf-8"))
    ledger=json.loads(Path(a.ledger).read_text(encoding="utf-8"))
    aggregate=json.loads(Path(a.aggregate).read_text(encoding="utf-8"))
    now=aware_time(a.now) if a.now else datetime.now(timezone.utc)
    if now is None:
        p.error("Invalid --now")
    report=apply(feed,accepted,now=now,publication_ledger=ledger,aggregate_report=aggregate)
    temp=path.with_name(path.name+".multisource-staged")
    temp.write_text(json.dumps(feed,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    os.replace(temp,path)
    print("BSD_MULTISOURCE_QUALIFIED_APPLY",json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
