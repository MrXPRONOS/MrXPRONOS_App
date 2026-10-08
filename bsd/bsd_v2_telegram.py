#!/usr/bin/env python3
"""BSD V2 -> Telegram hourly: send every eligible prediction 60-120min before KO.

Only confirmed site BSD V2 predictions are eligible. Existing telegram_sent
unique (kind,ref_id,ref_date) used as durable ledger. No ongoing match sent.
"""
import argparse,json,os,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
import requests
from bsd_h2h import _utc

KIND="bsd_v2_hourly"
URL="https://mrxpronos.github.io/MrXPRONOS_App/pronos.html"

def due(matches,now,min_minutes=60,max_minutes=120):
    selected=[]
    for m in matches:
        if not isinstance(m,dict) or m.get("source")!="bsd":continue
        if str(m.get("status","")).lower() not in ("notstarted","upcoming"):continue
        try:dt=_utc(str(m.get("event_date") or ""))
        except (ValueError,TypeError):continue
        delta=(dt-now).total_seconds()/60
        if min_minutes<=delta<max_minutes and m.get("prediction",{}).get("selection_key"):
            selected.append(m)
    return sorted(selected,key=lambda m:(m["event_date"],str(m["id"])))


def headers(key):
    return {"apikey":key,"Authorization":"Bearer "+key,
            "Content-Type":"application/json",
            "Prefer":"return=representation,resolution=ignore-duplicates"}


def claim(session,base,key,match,chat_id):
    # One row per channel+match, anchored in the existing unique index.
    # Only the insert winner will send. This is at-most-once for this channel,
    # with a possible missed delivery if the runner crashes after claiming.
    event_id=str(match["id"])
    ref=chat_id+":"+event_id
    date=match["date"]
    payload={"kind":KIND,"ref_id":ref,"ref_date":date,"validation_sent":False}
    r=session.post(base.rstrip("/")+"/rest/v1/telegram_sent",
                   params={"on_conflict":"kind,ref_id,ref_date"},
                   headers=headers(key),json=payload,timeout=30)
    r.raise_for_status()
    rows=r.json()
    return isinstance(rows,list) and len(rows)>0


def send_one(session,token,chat_id,match):
    dt=_utc(match["event_date"])
    p=match["prediction"]
    text=(
        "⚽ PRONOSTIC MR XPRONOS\n\n"
        f"🏆 {match.get('league') or 'Football'}\n"
        f"⚽ {match['home_team']} vs {match['away_team']}\n"
        f"🕒 Début : {dt:%d/%m/%Y %H:%M} UTC\n"
        f"🎯 Pronostic : {p.get('type') or p.get('label')}\n"
        f"📊 Probabilité estimée : {p.get('confidence')} %\n\n"
        "18+ • Pariez avec modération."
    )
    data={"chat_id":chat_id,"text":text,"disable_web_page_preview":True,
          "reply_markup":json.dumps({"inline_keyboard":[[{"text":"Voir les pronostics","url":URL}]]})}
    r=session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   data=data,timeout=40)
    r.raise_for_status()
    payload=r.json()
    if not payload.get("ok"):raise RuntimeError("Telegram response not ok")
    return payload["result"]["message_id"]


def process(data,now,*,session,token,chat_ids,supabase_url,supabase_key):
    if data.get("source")!="bsd" or data.get("model_version")!="bsd-v2-isolated":
        raise ValueError("Production JSON is not BSD V2")
    selections=due(data["matches"],now)
    report={"due":len(selections),"sent":0,"already_claimed":0,"errors":0}
    for match in selections:
        for chat in chat_ids:
            try:
                if not claim(session,supabase_url,supabase_key,match,chat):
                    report["already_claimed"]+=1
                    continue
                send_one(session,token,chat,match)
                report["sent"]+=1
                time.sleep(.3)
            except Exception as e:
                report["errors"]+=1
                print("TELEGRAM_BSD_ERROR:",match["id"],type(e).__name__,str(e)[:180])
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",default="data.json")
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    data=json.loads(Path(args.data).read_text(encoding="utf-8"))
    now=datetime.now(timezone.utc)
    if args.dry_run:
        print("BSD_TELEGRAM_DRY_RUN:",json.dumps([{"id":m["id"],"kickoff":m["event_date"]}
          for m in due(data["matches"],now)]))
        return
    token=os.getenv("TELEGRAM_BOT_TOKEN")
    chat=os.getenv("TELEGRAM_CHAT_ID")
    sb_url=os.getenv("SUPABASE_URL")
    sb_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not all((token,chat,sb_url,sb_key)):raise RuntimeError("Missing Telegram or Supabase secrets")
    report=process(data,now,session=requests.Session(),token=token,
                   chat_ids=[chat],supabase_url=sb_url,supabase_key=sb_key)
    print("BSD_V2_TELEGRAM:",json.dumps(report))
    if report["errors"]:raise SystemExit("Telegram delivery errors; investigate ledger")


if __name__=="__main__":
    main()
