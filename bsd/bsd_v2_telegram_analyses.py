#!/usr/bin/env python3
"""Separate Safe and Cotes 1,50+ INFORMATIONAL Telegram distribution.

Unlike the Pro/VIP recommender, this reads only market_odds_analyses and
uses distinct Cloudflare D1 ledger kind. No ineligible market becomes a
recommendation or an offered bookmaker quote. A manual run defaults to
the designated test channel, while cron/push use configured production.
"""
from __future__ import annotations
import argparse,json,os,sys
from datetime import datetime,timedelta,timezone
from html import escape
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
import requests

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"scripts"))
from telegram_rich import post_photo
from telegram_ledger_gateway import Ledger
from bsd_v2_public_tiers import tier_for_record,SAFE,COTES15,public_category_title
from bsd_v2_tier_visual import render_analysis
from bsd_h2h import _utc

KIND="bsd_v2_market_analysis_indicative"
URL="https://mrxpronos.github.io/MrXPRONOS_App/pronos.html"
VALID_STATUS=("upcoming","notstarted")
MAX_POSTS_PER_CHANNEL_RUN=8

def valid_analysis(row,now,*,min_minutes=60,max_minutes=120):
    if not isinstance(row,dict) or tier_for_record(row) not in (SAFE,COTES15):
        return False
    if not all((
        row.get("analysis_only") is True,
        row.get("analysis_telegram_opt_in") is True,
        row.get("do_not_send_to_telegram") is True, # legacy recommendation route stays disabled
        row.get("not_an_executable_bookmaker_quote") is True,
        row.get("estimated_odds") is True,
        row.get("odds_source")=="mrxpronos_model",
        row.get("price_method")=="probability_calibrated_plus_fixed_6pct",
        row.get("overround_assumption")==.06,
        row.get("recommendation_eligible") is False,
        row.get("prediction_eligible") is False,
        row.get("status") in VALID_STATUS,
    )):return False
    p=row.get("model_probability")
    odds=row.get("odds")
    if type(p) not in (float,int) or type(odds) not in (float,int) or (
        not isfinite(p) or not isfinite(odds) or not 0<p<1 or
        abs(odds-round(1/(p*1.06),3))>.002):
        return False
    try: kickoff=_utc(str(row["event_date"]))
    except (ValueError,TypeError,KeyError):return False
    delta=(kickoff-now).total_seconds()/60
    return min_minutes<=delta<max_minutes

def due(analyses,now,**kwargs):
    if not isinstance(analyses,list):return []
    selected=[row for row in analyses if valid_analysis(row,now,**kwargs)]
    return sorted(selected,key=lambda x:(x["event_date"],tier_for_record(x),x["id"]))

def _safe(value,max_len=90):
    return escape(" ".join(str(value or "Football").split())[:max_len],quote=False)

def _kick(value):
    return _utc(str(value)).strftime("%d/%m à %Hh%M") + " UTC"

def _odds(value):
    price=float(value)
    digits=3 if 1.50<price<1.505 or 1.30<price<1.305 else 2
    return f"{price:.{digits}f}".replace(".",",")

def caption(row):
    tier=tier_for_record(row)
    if tier not in (SAFE,COTES15):raise ValueError("Unknown indicative category")
    if not valid_analysis(row,datetime.now(timezone.utc),min_minutes=-600,max_minutes=10080):
        # For offline previews validation can use a time anchored on kickoff.
        _kickoff=_utc(str(row["event_date"]))-timedelta(minutes=90)
        if not valid_analysis(row,_kickoff):
            raise ValueError("Cannot caption unverified market analysis")
    return "\n".join((
        f"<b>⚽ {public_category_title(tier)} · MR XPRONOS</b>",
        "<i>Analyse indicative avant-match, pas un pronostic Ultra Safe.</i>",
        "",
        f"<b>{_safe(row.get('home_team'),52)} – {_safe(row.get('away_team'),52)}</b>",
        "<blockquote>"
        f"🎯 {_safe(row.get('market_label'),102)}\n"
        f"📊 Cote théorique : <b>{_odds(row['odds'])}</b>\n"
        f"📈 Probabilité estimée : <b>{row['model_probability']*100:.1f} %</b>"
        "</blockquote>",
        f"🕒 <i>{_kick(row['event_date'])}</i>",
        "<i>Cette cote vient du modèle : elle n'est pas proposée par un bookmaker. Résultat non garanti.</i>",
        "",
        "<i>🔞 18+ · Jouez avec modération.</i>",
    ))

def action_buttons():
    return {"inline_keyboard":[
        [{"text":"Voir Ultra Safe, Safe et Cotes 1,50+","url":URL}],
    ]}

def send_one(session,token,chat,row):
    with TemporaryDirectory() as tmp:
        image=render_analysis(row,Path(tmp)/"analyse.png")
        return post_photo(session,token,chat,image,caption(row),
                          action_buttons(),timeout=60)

def process(payload,now,*,session,token,chat_ids,ledger):
    if payload.get("source")!="bsd" or payload.get("model_version")!="bsd-v2-isolated":
        raise ValueError("Invalid source feed")
    generated=_utc(str(payload.get("generated_at") or ""))
    if now-generated>timedelta(hours=36) or generated-now>timedelta(hours=2):
        raise ValueError("Stale or future generated data")
    rows=due(payload.get("market_odds_analyses"),now)
    report={"eligible":len(rows),"sent":0,"already_claimed":0,"errors":0,
            "safe_sent":0,"cotes15_sent":0}
    for chat in dict.fromkeys(chat_ids):
        delivered=0
        for row in rows:
            if delivered>=MAX_POSTS_PER_CHANNEL_RUN:break
            ref=str(chat)+":"+str(row["id"])
            day=str(row.get("date") or row["event_date"][:10])
            try:
                if not ledger.claim(KIND,ref,day):
                    report["already_claimed"]+=1
                    continue
                message_id=send_one(session,token,chat,row)
                ledger.mark(KIND,ref,day,message_id=message_id)
                delivered+=1
                report["sent"]+=1
                report[tier_for_record(row)+"_sent"]+=1
            except Exception as exc:
                # Ambiguous provider failures retain the atomic claim: no
                # automatic second send to the same channel.
                report["errors"]+=1
                print("INDICATIVE_TELEGRAM_ERROR",type(exc).__name__)
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",default="data.json")
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    payload=json.loads(Path(args.data).read_text(encoding="utf-8"))
    now=datetime.now(timezone.utc)
    if args.dry_run:
        print("INDICATIVE_DRY_RUN",json.dumps({
            "total":len(due(payload.get("market_odds_analyses"),now)),
            "tiers":{tier:sum(tier_for_record(x)==tier for x in due(payload.get("market_odds_analyses"),now))
                     for tier in (SAFE,COTES15)}},ensure_ascii=False))
        return
    token=(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat=(os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:raise RuntimeError("Telegram production settings missing")
    others=(os.getenv("TELEGRAM_ANALYSIS_CHAT_IDS") or "").split(",")
    chats=[chat]+[x.strip() for x in others if x.strip() and x.strip()!=chat]
    result=process(payload,now,session=requests.Session(),token=token,
                   chat_ids=chats,ledger=Ledger())
    print("BSD_INDICATIVE_TELEGRAM",json.dumps(result,ensure_ascii=False))
    if result["errors"]:raise SystemExit("Telegram indicative delivery had errors")

if __name__=="__main__":
    main()
