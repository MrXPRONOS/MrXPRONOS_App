#!/usr/bin/env python3
"""Run EXISTING BSD V2 calculation for verified future multisource fixtures.

Test messages only, labelled experimental and NOT priced betting coupons.
No change to any of the production BSD V2 formulas, parameters, ledgers,
data.json or public Telegram channel. Fully fail-closed test channel guard.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone,timedelta
from collections import Counter
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.football_match_source_router import aware_time
from scripts.football_external_bsd_v2_adapter import (
    normalize_history,adapt_daily,evaluate_existing_v2,V2History,predict_v2)
from scripts.telegram_test_guard import validate_test_channel


def audit_no_quote_gate(fixtures:list[dict],history:list[dict],*,at:datetime) -> dict:
    """Probe the ORIGINAL BSD V2 bookmaker-odds gate, without providing prices.

    This is NOT a full production eligibility check: calibration, specialist
    models, quality policies and verified bookmaker odds are not loaded here.
    Never treat a research candidate or an unquoted decision as publishable.
    """
    if at.tzinfo is None:
        raise ValueError("Timezone-aware analysis clock required")
    clock=at.astimezone(timezone.utc)
    available=[r for r in history
               if (t:=aware_time(r.get("event_date"))) is not None
               and t+timedelta(hours=4)<clock]
    index=V2History(available)
    refusals=Counter()
    market_refusals=Counter()
    for fixture in fixtures:
        market_audit=[]
        choice,reason=predict_v2(
            fixture,index,clock=clock,mode="reliability",
            odds_by_market={},require_odds=True,market_audit=market_audit)
        # This assert means missing odds can NEVER quietly turn into coupons,
        # even if future upstream V2 code changes its defaults.
        if choice is not None:
            raise AssertionError("Unquoted BSD V2 fixture passed required bookmaker-odds gate")
        refusals[str(reason or "unknown")]+=1
        market_refusals.update(
            str(row["result"]) for row in market_audit if row.get("result"))
    return {
        "fixtures_checked":len(fixtures),
        "accepted_with_no_bookmaker_quotes":0,
        "missing_or_low_odds_market_rejections":market_refusals["missing_or_low_bsd_odds"],
        "reasons":dict(sorted(refusals.items())),
        "model_market_refusals":dict(sorted(market_refusals.items())),
        "used_original_predict_v2":True,
        "actual_bookmaker_quotes_supplied":False,
        "calibration_loaded":False,
        "specialist_models_loaded":False,
        "full_publication_policy_checked":False,
        "publication_enabled":False,
    }

def audit_external_pricing_bridge(fixtures:list[dict]) -> dict:
    """Fail-closed metadata check for the EXISTING BSD production price path.

    bsd_v2_publish.fetch_event_odds requires a genuine BSD event ID; research
    fixture IDs are derived in a separate namespace. The publisher can also
    label a MODEL-ESTIMATED price, but that is not a bookmaker quote and its
    calibrated publication path is NOT reproduced or enabled by this module.
    """
    reasons=Counter()
    for item in fixtures:
        if item.get("_derived_research_id") is not True:
            reasons["missing_research_namespace_proof"]+=1
        elif not isinstance(item.get("_original_fixture_refs"),dict):
            reasons["missing_provider_reference"]+=1
        else:
            reasons["external_id_not_native_bsd_odds_id"]+=1
    return {
        "inspected_fixtures":len(fixtures),
        "native_bsd_odds_event_ids_verified":0,
        "external_to_bookmaker_event_matches_verified":0,
        "external_quote_provider_integrated":False,
        "bsd_native_odds_endpoint_called":False,
        "model_estimated_prices_possible_in_existing_publisher":True,
        "model_estimated_prices_generated_by_this_audit":False,
        "full_calibration_and_v21_publication_approved":False,
        "reasons":dict(sorted(reasons.items())),
        "publication_enabled":False,
    }


def build(fixtures:list[dict], licensed_history:list[dict], *,at:datetime,
          max_picks:int=3) -> tuple[list[str],dict]:
    if at.tzinfo is None or not 1<=max_picks<=3:
        raise ValueError("UTC aware timestamp and max 1-3 messages required")
    # A Telegram test prediction requires an independently corroborated
    # CC0 fixture identity; a league label asserted by one API is not enough.
    confirmed=[f for f in fixtures if f.get("_schedule_verified_by")=="openfootball_cc0"
               and f.get("league_conflict") is False
               and f.get("league_verified") is True]
    archived,history_quality=normalize_history(licensed_history)
    ready,readiness=adapt_daily(confirmed,archived,as_of=at)
    forecast,quality=evaluate_existing_v2(ready,archived,as_of=at)
    no_quote=audit_no_quote_gate(ready,archived,at=at)
    pricing_bridge=audit_external_pricing_bridge(ready)
    by_id={row["id"]:row for row in ready}
    result=[]
    for row in forecast:
        if row["status"]!="model_candidate":
            continue
        event=by_id.get(row["_research_id"])
        if event is None or aware_time(event["event_date"])<=at:
            continue
        # The existing BSD V2 decision was made without the complete
        # calibration, bookmaker prices and publication policies.
        # Therefore be explicit, not promotional.
        home=str(event["home_team"]["name"])
        away=str(event["away_team"]["name"])
        key=str(row.get("internal_candidate_key") or "")
        if not key: continue
        h2h=int(row["h2h"]["total_previous_meetings"])
        txt=("\U0001f9ea MR XPRONOS — CANAL TEST SEULEMENT\n"
             "Analyse expérimentale par le moteur BSD V2 (formules inchangées)\n\n"
             f"\u26bd {home} — {away}\n"
             f"\U0001f3c6 {event['league_name']}\n"
             f"\U0001f4c5 {event['event_date']} (UTC)\n"
             f"\U0001f3af Marché retenu par le noyau V2 : {key}\n"
             f"\U0001f4ca H2H historiques identifiés : {h2h}\n"
             "\n\u26a0\ufe0f Test non calibré pour publication : sans cote bookmaker"
             " ni validation complète de la politique BSD V2."
             " Pas un conseil ou coupon de pari.\n18+ \u2022 Joue responsablement.")
        result.append(txt)
        if len(result)>=max_picks:break
    report={
        "input_api_fixtures":len(fixtures),
        "calendar_corroborated_fixtures":len(confirmed),
        "qualified_external_fixtures":len(ready),
        "raw_v2_candidates":quality["v2_candidate_count"],
        "no_bookmaker_quote_gate":no_quote,
        "external_pricing_bridge":pricing_bridge,
        "messages_ready":len(result),
        "historic_matches":history_quality["usable_historic_matches"],
        "reasons":readiness["ignored"],
        "archive_sources":history_quality["distinct_sources"],
        "calibrated_production_coupons":0,
        "no_odds_invented":True,
        "production_modified":False,
        "test_only":True,
    }
    return result,report

def test_post(messages:list[str],report:dict,*,token:str,chat:str,
              get=None,post=None) -> dict:
    import requests
    if not messages:
        # One diagnostic test message so the user can verify the isolated
        # channel, WITHOUT passing an unqualified fixture off as a pronostic.
        messages=[
            "\U0001f9ea MR XPRONOS — TEST MULTISOURCE\n\n"
            "Collecte des championnats et historiques autorisés terminée.\n"
            f"Matchs avec historique compatible BSD V2 : {report['qualified_external_fixtures']}\n"
            f"Signaux de recherche du noyau V2 : {report['raw_v2_candidates']}\n"
            "Aucun pronostic conforme pour le moment : aucun signal inventé.\n"
            "Canal de test seulement — aucune publication en production."
        ]
    checker=get or requests.get
    transport=post or requests.post
    guard=validate_test_channel(chat,token,request_get=checker)
    if guard["username"]!="predict_mrxp":
        raise RuntimeError("Unapproved test channel")
    endpoint="https://api.telegram.org/bot"+token+"/sendMessage"
    successes=0
    for msg in messages[:3]:
        try:
            response=transport(endpoint,json={
                "chat_id":guard["chat_id"],"text":msg,"disable_web_page_preview":True
            },timeout=(8,20))
            response.raise_for_status()
            data=response.json()
            if not isinstance(data,dict) or data.get("ok") is not True:
                raise ValueError("Telegram returned unsuccessful result")
            successes+=1
        except (requests.RequestException,ValueError):
            # URL embeds Telegram bot token; never print it in an exception.
            raise RuntimeError("Test Telegram send failed; token redacted") from None
    return {"sent_to":"@predict_mrxp","messages_sent":successes,
            "test_channel_verified":True,"production_posts":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixtures",required=True)
    p.add_argument("--licensed-history",required=True)
    p.add_argument("--analysis-at",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--send-test",action="store_true")
    p.add_argument("--max-picks",type=int,default=3)
    a=p.parse_args()
    at=aware_time(a.analysis_at)
    if at is None:p.error("UTC aware --analysis-at required")
    if Path(a.report).resolve()==(ROOT/"data.json").resolve():
        p.error("Never replace production data.json")
    fixtures=json.loads(Path(a.fixtures).read_text(encoding="utf-8"))
    with open(a.licensed_history,encoding="utf-8") as file:
        archive=[json.loads(line) for line in file if line.strip()]
    if not isinstance(fixtures,list):p.error("Fixture input must be JSON array")
    messages,report=build(fixtures,archive,at=at,max_picks=a.max_picks)
    if a.send_test:
        token=os.environ.get("TELEGRAM_BOT_TOKEN","")
        chat=os.environ.get("TELEGRAM_TEST_CHAT_ID","")
        if not token or not chat:p.error("TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_CHAT_ID required")
        report["telegram"]=test_post(messages,report,token=token,chat=chat)
    target=Path(a.report)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("BSD_V2_MULTISOURCE_TEST",json.dumps(report,ensure_ascii=False))

if __name__=="__main__":
    main()
