#!/usr/bin/env python3
"""Licensed OpenFootball -> ORIGINAL BSD V2 full-model offline calibration/replay.

No network, bookmaker API, production writes or Telegram. Historical fixtures
have DAY precision; evaluation is prior-day only and NEVER a real-odds backtest.
Do not call this evidence approval for a production publication.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
if str(ROOT/"bsd") not in sys.path:sys.path.insert(0,str(ROOT/"bsd"))

from scripts.football_external_bsd_v2_adapter import normalize_history,adapt_daily
from scripts.football_match_source_router import aware_time
from bsd_v2_core import V2History,fit_rho_2024,predict_v2,fixture_datetime
from bsd_v2_btts import fit_btts_model
from bsd_v2_over_under import fit_total_model
from bsd_v2_double_chance import fit_model as fit_dc_model
from bsd_v2_policies import fit_policy
from bsd_v2_estimated_odds import price_selected_market,ESTIMATED_SOURCE
from bsd_v2_guardrails import v21_accept_priced,post_price_value_guard,V21_EXCLUDED_KEYS
from bsd_markets import candidates_from_goals,realized
from bsd_v2_publish import assemble as original_v2_production_assemble

EXCLUDED_SELECTIONS=frozenset({"UNDER_45","12"})

def model_index_partition(archive:list[dict], *, cutoff:datetime, analysis_at:datetime):
    if cutoff.tzinfo is None or analysis_at.tzinfo is None or cutoff>=analysis_at:
        raise ValueError("Require ordered, timezone-aware cutoff and analysis_at")
    training,observed=[],[]
    for e in archive:
        stamp=aware_time(e.get("event_date"))
        if stamp is None:
            continue
        settled=stamp+timedelta(hours=4)
        if settled < cutoff:
            training.append(e)
        if settled < analysis_at:
            observed.append(e)
    return training,observed

def replay(licensed_history:list[dict], confirmed_fixtures:list[dict],
           *,at:datetime, cutoff:datetime, max_holdout:int=150, existing_feed:dict|None=None)->dict:
    if not 1<=max_holdout<=200:
        raise ValueError("max_holdout must be 1..200")
    if at.tzinfo is None or cutoff.tzinfo is None or at<=cutoff:
        raise ValueError("A future analysis_at after the fit cutoff is required")
    if cutoff.year<=2025:
        raise ValueError("2024/2025 fit periods require cutoff in 2026 or later")
    archive,raw_stats=normalize_history(licensed_history)
    training,observed=model_index_partition(archive,cutoff=cutoff,analysis_at=at)
    index=V2History(training)
    observed_index=V2History(observed)
    if not training or not observed:
        raise ValueError("Empty licensed training/observed index")
    rho,rho_info=fit_rho_2024(index)
    btts,btts_info=fit_btts_model(index,rho=rho)
    totals,totals_info=fit_total_model(index,rho=rho)
    dc,dc_info=fit_dc_model(index,rho=rho)
    calibration,policy,cal_info=fit_policy(
        index,rho=rho,btts_model=btts,total_model=totals,dc_model=dc)
    fitted=(
        rho_info.get("training",0)>=100 and
        rho_info.get("validation",0)>=50 and
        btts_info.get("trained",0)>=100 and
        btts_info.get("validated",0)>=50 and
        totals_info.get("trained",0)>=100 and
        totals_info.get("validated",0)>=50 and
        dc_info.get("trained",0)>=100 and
        dc_info.get("validated",0)>=50 and
        cal_info.get("training_eligible",0)>0 and
        cal_info.get("validation_eligible",0)>0
    )
    def inference(event,clock,history_index):
        return predict_v2(
            event,history_index,clock=clock,calibration=calibration,
            quality_policy=policy,rho=rho,btts_model=btts,
            total_model=totals,dc_model=dc,mode="reliability",
            odds_by_market={},require_odds=False,
            excluded_keys=EXCLUDED_SELECTIONS)

    # Historical days have no authenticated kickoff time. A replay uses the
    # match calendar DAY at 23:59 and only results settled BEFORE that day.
    # Frozen calibration uses pre-cutoff data; historical selection itself
    # reads an immutable V2History with its own time-aware prior lookup.
    holdout=sorted(
        (e for e in observed if cutoff<=fixture_datetime(e)<at),
        key=lambda e:(str(e["event_date"]),str(e["id"])))
    if len(holdout)>max_holdout:
        holdout=[holdout[int(i*len(holdout)/max_holdout)] for i in range(max_holdout)]
    statuses=Counter()
    wins=0
    brier_total=0.
    prices=Counter()
    market_template={c.key:c for c in candidates_from_goals(1.4,1.2)}
    prior_day_indexes={}
    for event in holdout:
        stamp=fixture_datetime(event)
        replay_clock=stamp-timedelta(days=1)
        # Actual match kickoffs are unknown: freeze availability at the
        # PREVIOUS calendar day's end, not at simulated 23:59 match time.
        # A result must have settled by replay_clock, with 4h grace.
        key=replay_clock.date().isoformat()
        if key not in prior_day_indexes:
            prior=[row for row in observed if
                   (seen:=aware_time(row.get("event_date"))) is not None
                   and seen+timedelta(hours=4)<replay_clock]
            prior_day_indexes[key]=V2History(prior)
        pseudo=dict(event,status="notstarted")
        prediction,reason=inference(pseudo,replay_clock,prior_day_indexes[key])
        if prediction is None:
            statuses["abstained:"+str(reason)]+=1
            continue
        selection=prediction["prediction"]
        key=str(selection.get("key") or "")
        if key not in market_template:
            statuses["missing_market_definition"]+=1
            continue
        score=realized(market_template[key],int(event["home_score"]),int(event["away_score"]))
        probability=selection["probability"]
        wins+=score
        brier_total+=(probability-score)**2
        statuses["qualified_without_price"]+=1
        price=price_selected_market(selection,{},now=stamp-timedelta(days=1))
        if price is None:
            prices["not_estimated"]+=1
        elif price.get("odds_source")==ESTIMATED_SOURCE:
            # Model prices are NOT independently quoted or bookmaker odds.
            allowed,reason=v21_accept_priced(price,tracker={},league_market=None)
            guarded=post_price_value_guard(price)
            prices["indicative_v21_pass" if allowed and guarded.get("passed") else
                   "indicative_v21_veto"]+=1
        else:
            raise AssertionError("Unexpected real bookmaker price without quotes")
    n=statuses["qualified_without_price"]
    selected=[f for f in confirmed_fixtures if
              f.get("_schedule_verified_by")=="openfootball_cc0" and
              f.get("league_verified") is True and not f.get("league_conflict")]
    upcoming,upcoming_report=adapt_daily(selected,observed,as_of=at)
    future=Counter()
    for event in upcoming:
        prediction,reason=inference(event,at,observed_index)
        if prediction is None:
            future["abstained:"+str(reason)]+=1
            continue
        future["calibrated_model_candidate"]+=1
        selected_market=prediction["prediction"]
        price=price_selected_market(selected_market,{},now=at)
        if price is None:
            future["no_model_price"]+=1
            continue
        if price["odds_source"]!=ESTIMATED_SOURCE:
            raise AssertionError("Bookmaker quote invented")
        ok,why=v21_accept_priced(price,tracker={},league_market=None)
        guard=post_price_value_guard(price)
        if ok and guard.get("passed"):
            future["indicative_model_quote_passes_base_v21_only"]+=1
        else:
            future["indicative_model_quote_vetoed"]+=1

    # Execute the actual production policy ASSEMBLER in memory, without ANY
    # external bookmaker fetcher, Telegram, file writing or publish entrypoint.
    # Synthetic external fixtures are NEVER sent to real BSD odds endpoints.
    # A produced row in this isolated output would be a MODEL-estimated
    # prediction only; neither a verified bookmaker quote nor publish approval.
    source_history_count=len(observed)
    source_fixture_count=len(upcoming)
    if existing_feed is not None:
        if (not isinstance(existing_feed,dict) or existing_feed.get("source")!="bsd"
            or not isinstance(existing_feed.get("matches"),list)
            or not isinstance(existing_feed.get("performance_tracker",{}),dict)):
            raise ValueError("Invalid current public BSD feed; refuse implied tracker")
    existing=deepcopy(existing_feed) if existing_feed is not None else {"matches":[],"performance_tracker":{}}
    initial_existing=deepcopy(existing)
    original_selections={
        str(row["id"]):(row.get("prediction") or {}).get("selection_key")
        for row in existing.get("matches",[]) if isinstance(row,dict) and row.get("id") is not None
    }
    dry_output=original_v2_production_assemble(
        existing,upcoming,observed,now=at,
        calibration=calibration,policy=policy,rho=rho,
        odds_fetcher=None,max_odds_requests=0,
        btts_model=btts,total_model=totals,dc_model=dc)
    if len(observed)!=source_history_count or len(upcoming)!=source_fixture_count:
        raise AssertionError("Production assembly unexpectedly mutated source inputs")
    if existing != initial_existing:
        raise AssertionError("Native assembler mutated the original feed snapshot in memory")
    published_rows=dry_output.get("matches") or []
    if not isinstance(published_rows,list):
        raise AssertionError("Production assembler returned invalid matches array")
    new_rows=0
    unchanged_saved=0
    for row in published_rows:
        pred=row.get("prediction") or {}
        prior_key=original_selections.get(str(row.get("id")))
        if str(row.get("id")) in original_selections:
            if pred.get("selection_key")!=prior_key:
                raise AssertionError("Original published selection was altered")
            unchanged_saved+=1
            continue
        new_rows+=1
        if pred.get("odds_source")!=ESTIMATED_SOURCE or pred.get("estimated_odds") is not True:
            raise AssertionError("New external research fixture has imaginary bookmaker quote")
        if row.get("source_event_id") is None:
            raise AssertionError("Dry-run produced a new match without an event id")
    assembled_stats=dry_output.get("diagnostics",{}).get("rejections",{})
    if int(assembled_stats.get("odds_attempts",0))!=0:
        raise AssertionError("Odds API attempted in isolated dry-run")
    if int(assembled_stats.get("created",0))!=new_rows:
        raise AssertionError("V2 assembler's created count differs from new model-only rows")
    production_assembler_dry_run={
        "original_bsd_v2_publish_assemble_executed":True,
        "input_synthetic_fixture_count":len(upcoming),
        "model_only_rows_generated_in_memory":new_rows,
        "existing_rows_retained_with_unchanged_selections":unchanged_saved,

        "no_actual_bookmaker_quotes_used":True,
        "no_api_or_telegram_network_access":True,
        "max_odds_requests":0,
        "existing_publication_tracker_supplied":existing_feed is not None,
        "existing_production_snapshot_left_untouched":True,
        "model_only_prices_not_bookmaker_value":True,
        "production_ledger_or_files_updated":False,
        "synthetic_fixture_ids_not_authorized_for_publishing":True,
        "production_release_authorized":False,
        "rejection_reasons":dict(sorted((str(k),int(v)) for k,v in assembled_stats.items()
                                         if isinstance(v,int))),
    }

    # Keep only aggregate diagnostics; no event identity, teams or selections.
    return {
        "research_only":True,
        "production_publication_authorized":False,
        "all_native_bsd_v2_fit_functions_used":True,
        "full_calibration_and_specialists_executed":True,
        "training_sufficiency_requirements_met":bool(fitted),
        "training_periods":{"rho_and_specialists":"2024",
                            "market_calibration":"2025 Jan-Aug",
                            "market_quality_validation":"2025 Sep-Dec",
                            "holdout":"2026 results available before analysis_at"},
        "fit_cutoff_utc":cutoff.isoformat(),
        "analysis_at_utc":at.isoformat(),
        "historical_results_available":len(observed),
        "training_results_before_cutoff":len(training),
        "rho":rho_info,
        "btts":btts_info,
        "totals":totals_info,
        "double_chance":dc_info,
        "market_calibration":cal_info,
        "holdout_evaluation":{
            "matches_examined":len(holdout),
            "selected_without_market_quotes":n,
            "wins_of_selected_unpriced_markets":wins,
            "hit_rate":round(wins/n,4) if n else None,
            "selected_market_brier":round(brier_total/n,5) if n else None,
            "rejections":dict(sorted(statuses.items())),
            "pricing":dict(sorted(prices.items())),
            "date_only_prior_day_replay":True,
            "strict_pre_day_data_availability_enforced":True,
            "not_a_verified_kickoff_or_odds_backtest":True,
            "not_independently_confirmed_return_or_profit":True,
        },
        "upcoming_research":{
            "confirmed_fixtures":len(selected),
            "history_eligible":len(upcoming),
            "adapted":upcoming_report["ignored"].get("adapted_external",0),
            "results":dict(sorted(future.items())),
            "official_bookmaker_quotes_loaded":False,
            "production_tracker_loaded":existing_feed is not None,
            "full_publication_policy_validated":False,
        },
        "native_assembler_dry_run":production_assembler_dry_run,
        "license_scope":"openfootball_CC0_only",
        "raw_or_private_events_exported":False,
        "telegram_posts":0,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--licensed-history",required=True)
    p.add_argument("--fixtures",required=True)
    p.add_argument("--at",required=True)
    p.add_argument("--fit-cutoff",default="2026-01-01T00:00:00+00:00")
    p.add_argument("--max-holdout",type=int,default=150)
    p.add_argument("--existing-feed",help="Read-only published BSD feed including performance tracker")
    p.add_argument("--report",required=True)
    a=p.parse_args()
    dest=Path(a.report).resolve()
    if dest==(ROOT/"data.json").resolve():
        p.error("Production feed forbidden")
    lines=Path(a.licensed_history).read_text(encoding="utf-8").splitlines()
    raw=[json.loads(x) for x in lines if x.strip()]
    fixtures=json.loads(Path(a.fixtures).read_text(encoding="utf-8"))
    clock=aware_time(a.at);cutoff=aware_time(a.fit_cutoff)
    if clock is None or cutoff is None or not isinstance(fixtures,list):
        p.error("Invalid fixtures or timezone")
    prior=json.loads(Path(a.existing_feed).read_text(encoding="utf-8")) if a.existing_feed else None
    report=replay(raw,fixtures,at=clock,cutoff=cutoff,max_holdout=a.max_holdout,existing_feed=prior)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BSD_V2_FULL_MODEL_CALIBRATED_RESEARCH",json.dumps(report,ensure_ascii=False))

if __name__=="__main__":
    main()
