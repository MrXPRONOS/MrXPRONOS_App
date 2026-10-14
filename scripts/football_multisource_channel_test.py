#!/usr/bin/env python3
"""Run EXISTING BSD V2 calculation for verified future multisource fixtures.

Test messages only, labelled experimental and NOT priced betting coupons.
No change to any of the production BSD V2 formulas, parameters, ledgers,
data.json or public Telegram channel. Fully fail-closed test channel guard.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.football_match_source_router import aware_time
from scripts.football_external_bsd_v2_adapter import (
    normalize_history,adapt_daily,evaluate_existing_v2)
from scripts.telegram_test_guard import validate_test_channel

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
