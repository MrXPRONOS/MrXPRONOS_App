#!/usr/bin/env python3
"""Proof that BSD V2's FROZEN selected market has a current *actual* BSD quote.

Not a publishing entry point. Consumes source identity/quotes only in process.
Only aggregate counts ever returned: no fixture IDs, club names or prices.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT,ROOT/"bsd"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from scripts.football_match_source_router import aware_time
from scripts.football_history_shadow import canonical_team
from scripts.football_external_bsd_v2_adapter import normalize_history,adapt_daily
from bsd_v2_core import V2History,fit_rho_2024,predict_v2
from bsd_v2_btts import fit_btts_model
from bsd_v2_over_under import fit_total_model
from bsd_v2_double_chance import fit_model as fit_dc_model
from bsd_v2_policies import fit_policy
from bsd_v2_estimated_odds import price_selected_market,ESTIMATED_SOURCE
from bsd_v2_guardrails import (v21_accept_priced,post_price_value_guard,
    tracker_penalties,update_performance_tracker)
from bsd_v2_publish import EXCLUDED_SELECTIONS,assemble as native_production_assemble

MAX_QUOTE_AGE_SECONDS=2*3600

def certified_native_shadow_fixture(discovered,adapted,native,*,at:datetime):
    """Retain historical synthetic team IDs but replace ONLY with proven BSD event ID.

    This helper is not a crosswalk discovery method. The upstream strict
    independent CC0/native 1:1 verification remains mandatory. A mismatch
    here fails closed even after the original verification.
    """
    if (not isinstance(discovered,dict) or
        discovered.get("_schedule_verified_by")!="openfootball_cc0" or
        discovered.get("league_verified") is not True or
        discovered.get("ambiguous_match") or discovered.get("league_conflict") or
        discovered.get("scores_conflict") or discovered.get("status")!="prematch"):
        raise ValueError("Unverified external source fixture")
    if not isinstance(adapted,dict) or adapted.get("_derived_research_id") is not True:
        raise ValueError("Invalid synthetic research model fixture")
    if not isinstance(native,dict) or str(native.get("status") or "").lower() not in ("notstarted","upcoming"):
        raise ValueError("No official native prematch event")
    real_id=native.get("id")
    if type(real_id) is not int or not 0<real_id<7_000_000_000_000_000:
        raise ValueError("Invalid native event identity")
    official_time=aware_time(native.get("event_date"))
    adapted_time=aware_time(adapted.get("event_date"))
    if (official_time is None or adapted_time is None or official_time<=at
        or abs((official_time-adapted_time).total_seconds())>900):
        raise ValueError("Official BSD/research kickoff mismatch")
    for side in ("home","away"):
        verified=canonical_team(str((adapted.get(side+"_team") or {}).get("name") or ""))
        supplied=native.get(side+"_team")
        native_name=supplied.get("name") if isinstance(supplied,dict) else supplied
        if not verified or verified!=canonical_team(str(native_name or "")):
            raise ValueError("Native event has a different football team")
    return {**adapted,"id":real_id,"event_date":official_time.isoformat(),
            "_native_bsd_id_verified_in_process":True}

def selected_quote(selection,quotes,*,at:datetime):
    """Never substitute another market or self-derived price."""
    if not isinstance(selection,dict) or not isinstance(quotes,dict) or at.tzinfo is None:
        return None,"invalid_input"
    code=selection.get("internal_market_code") or selection.get("market_code")
    if not isinstance(code,str) or not code:
        return None,"no_selected_market_code"
    quote=quotes.get(code)
    if not isinstance(quote,dict) or quote.get("origin")!="bsd_consensus" or quote.get("bookmaker")!="consensus":
        return None,"selected_market_not_quoted"
    updated=aware_time(quote.get("updated_at"))
    if updated is None or not 0 <= (at-updated).total_seconds() <= MAX_QUOTE_AGE_SECONDS:
        return None,"selected_market_quote_stale_or_untimed"
    chosen=price_selected_market(selection,{code:quote},now=at)
    if (not isinstance(chosen,dict) or chosen.get("odds_source")!="bsd_consensus"
        or chosen.get("estimated_odds") is not False
        or chosen.get("internal_market_code")!=code):
        return None,"quote_changed_market_or_estimated"
    return chosen,"verified_real_consensus_market"

def verify_selected_markets(
    rows:list[dict],pair_quotes:list[tuple[dict,dict,dict]],
    production_feed:dict,*,at:datetime)->dict:
    """Use unchanged full BSD V2 fit + policy with dated CC0 history.

    pair_quotes are externally corroborated fixture + authentic native BSD
    event + parse_odds result. Generated *only* by trusted same-process caller.
    None of the pair data or selected market codes is returned.
    """
    if (at.tzinfo is None or not isinstance(production_feed,dict)
        or production_feed.get("source")!="bsd"
        or not isinstance(production_feed.get("matches"),list)
        or not isinstance(production_feed.get("performance_tracker",{}),dict)):
        raise ValueError("Invalid trusted public production data/tracker")
    if len(pair_quotes)>8:
        raise ValueError("Eight-event read-only probe cap")
    archive,_=normalize_history(rows)
    available=[e for e in archive if
               (stamp:=aware_time(e.get("event_date"))) is not None and
               stamp+timedelta(hours=4)<at]
    index=V2History(available)
    rho,rho_info=fit_rho_2024(index)
    btts,btts_info=fit_btts_model(index,rho=rho)
    totals,total_info=fit_total_model(index,rho=rho)
    dc,dc_info=fit_dc_model(index,rho=rho)
    calibration,policy,cal_info=fit_policy(
        index,rho=rho,btts_model=btts,total_model=totals,dc_model=dc)
    sufficient=(rho_info.get("training",0)>=100 and rho_info.get("validation",0)>=50
                and btts_info.get("trained",0)>=100 and btts_info.get("validated",0)>=50
                and total_info.get("trained",0)>=100 and total_info.get("validated",0)>=50
                and dc_info.get("trained",0)>=100 and dc_info.get("validated",0)>=50
                and cal_info.get("training_eligible",0)>0 and cal_info.get("validation_eligible",0)>0)
    if not sufficient:
        raise RuntimeError("Research sample insufficient for genuine full BSD V2 calibration")
    tracker=update_performance_tracker(production_feed.get("performance_tracker"),
                                       production_feed["matches"],now=at)
    selection_penalties,family_penalties=tracker_penalties(tracker)
    league_performance=tracker.get("by_league_market",{})
    counts=Counter()
    publisher_fixtures=[]
    quote_by_native={}
    for fixture,native,quotes in pair_quotes:
        # Do NOT use the synthetic ID for odds calls; quotes were obtained using
        # the independently verified real BSD event in the trusted caller.
        if not isinstance(native,dict) or not isinstance(quotes,dict):
            raise ValueError("Invalid native quote witness")
        adapted,stats=adapt_daily([fixture],available,as_of=at)
        counts["events_examined"]+=1
        if len(adapted)!=1:
            counts["insufficient_historical_identity_or_form"]+=1
            continue
        event=adapted[0]
        # The historical team IDs remain stable across the real BSD event.
        # Event identity is replaced ONLY after strict external/native proof.
        event_for_publisher=certified_native_shadow_fixture(fixture,event,native,at=at)
        genuine_id=event_for_publisher["id"]
        if genuine_id in quote_by_native:
            raise ValueError("Duplicate official BSD event in trusted set")
        publisher_fixtures.append(event_for_publisher)
        quote_by_native[genuine_id]=quotes
        prediction,reason=predict_v2(
            event,index,calibration=calibration,quality_policy=policy,rho=rho,
            btts_model=btts,total_model=totals,dc_model=dc,
            clock=at,mode="reliability",odds_by_market={},require_odds=False,
            excluded_keys=EXCLUDED_SELECTIONS,
            selection_adjustments=selection_penalties,
            prospective_family_adjustments=family_penalties)
        if prediction is None:
            counts["full_model_abstained"]+=1
            continue
        counts["frozen_bsd_v2_model_market_candidates"]+=1
        chosen,why=selected_quote(prediction["prediction"],quotes,at=at)
        if chosen is None:
            counts[why]+=1
            continue
        counts["frozen_markets_with_exact_fresh_bsd_consensus_quote"]+=1
        bucket=league_performance.get(str(event.get("league_name") or "")+"|"+str(chosen.get("key")))
        ok,reason=v21_accept_priced(chosen,tracker,bucket)
        guard=post_price_value_guard(chosen)
        if ok and guard.get("passed") and chosen["bookmaker_odds"]>=1.20:
            counts["passes_v21_and_value_guard_in_research"]+=1
        else:
            counts["v21_or_value_guard_veto"]+=1
            # Classify the exact policy blocker, never the club/event/quote.
            if not ok:
                counts["v21_reason:"+str(reason)]+=1
            elif not guard.get("passed"):
                counts["value_guard_reason:"+str(guard.get("reason"))]+=1
            else:
                counts["price_below_120"]+=1
    # The SAME real BSD production assembler is exercised on the exact
    # witnessed native IDs, with its full calibrated selection, V2.1 rules,
    # duplicate accounting and actual saved tracker. The fetcher is a local
    # immutable quote snapshot; it cannot make HTTP calls or post Telegram.
    previous=deepcopy(production_feed)
    snapshot=deepcopy(production_feed)
    fixture_ids={x["id"] for x in publisher_fixtures}
    called=set()
    def frozen_quote_fetcher(selected_event,capture_clock):
        event_id=selected_event.get("id")
        if event_id not in fixture_ids or event_id in called:
            raise AssertionError("Unexpected or duplicate production odds request")
        called.add(event_id)
        return deepcopy(quote_by_native[event_id]),{"source":"in_process_consensus_snapshot"}
    dry=native_production_assemble(
        snapshot,publisher_fixtures,available,now=at,
        calibration=calibration,policy=policy,rho=rho,
        odds_fetcher=frozen_quote_fetcher,max_odds_requests=len(publisher_fixtures),
        btts_model=btts,total_model=totals,dc_model=dc)
    if production_feed!=previous:
        raise AssertionError("Read-only public production input was modified")
    native_stats=dry.get("diagnostics",{}).get("rejections",{})
    if not isinstance(native_stats,dict):
        raise AssertionError("Native assembler missing diagnostic totals")
    projected_created=int(native_stats.get("created",0))
    if projected_created<0 or projected_created>len(publisher_fixtures):
        raise AssertionError("Invalid native assembler new selection count")
    window_count=sum(at<aware_time(x["event_date"])<=at+timedelta(days=2)
                     for x in publisher_fixtures)
    if projected_created>window_count:
        raise AssertionError("Native assembler created a pick outside 48h window")
    return {
        "native_full_assembler_canary":{
            "executed":True,
            "native_event_ids_verified_in_process":len(publisher_fixtures),
            "events_within_native_48h_window":window_count,
            "actual_publication_window_exercised":window_count>0,
            "empty_window_is_not_publication_path_validation":window_count==0,
            "in_memory_quote_fetches":len(called),
            "projected_new_rows_not_published":projected_created,
            "existing_production_input_unchanged":True,
            "odds_api_calls_from_assembler":0,
            "site_or_telegram_publications":0,
            "production_enabled":False,
            "bookmaker_selection_codes_verified":0,
            "no_event_names_ids_or_odds_exported":True,
        },
        "real_market_selection_validation_executed":True,
        "fit_all_native_models_and_calibration":True,
        "sufficient_licensed_cc0_training_history":True,
        "production_tracker_supplied_readonly":True,
        "source_fixture_ids_or_raw_odds_exported":False,
        "match_selection_frozen_before_real_consensus_pricing":True,
        "historical_kickoffs_are_date_only":True,
        "independent_bookmaker_offer_executable":False,
        "bookmaker_selection_codes_verified":0,
        "production_authorized":False,
        "telegram_posts":0,
        "aggregate":dict(sorted(counts.items())),
    }
