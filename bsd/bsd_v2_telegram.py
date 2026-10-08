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
from bsd_v2_card import render as render_card

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
        p=m.get("prediction") or {}
        odds=p.get("odds")
        valid_price=(isinstance(odds,(int,float)) and not isinstance(odds,bool)
                     and 1.20<=odds<=100 and p.get("odds_source") in
                     ("bsd_consensus","bsd_bookmaker"))
        if (min_minutes<=delta<max_minutes and valid_price
                and p.get("selection_key") and p["selection_key"]!="UNDER_45"):
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


def release_failed_claim(session,base,key,match,chat_id):
    # Autorise le réessai lors du prochain cron si Telegram a rejeté l'envoi.
    # Un timeout après acceptation par Telegram reste intrinsèquement ambigu.
    params={"kind":"eq."+KIND,"ref_id":"eq."+chat_id+":"+str(match["id"]),
            "ref_date":"eq."+match["date"]}
    h=headers(key)
    r=session.delete(base.rstrip("/")+"/rest/v1/telegram_sent",
                     params=params,headers=h,timeout=30)
    r.raise_for_status()


def send_one(session,token,chat_id,match):
    # Telegram envoie la photo générée depuis le PNG du ballon et des données BSD.
    # Pas de capture de ticket de bookmaker et aucune cote inventée.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        image=render_card(match,Path(directory)/"coupon.png")
        caption=("⚽ Pronostic BSD V2 : "+str(match["home_team"])+" vs "+
                 str(match["away_team"])+"\n"+
                 str(match["prediction"].get("type") or "")+
                 "\nSimulation 500 000 F · aucun pari placé · 18+")
        markup={"inline_keyboard":[[{"text":"Voir les pronostics","url":URL}]]}
        with open(image,"rb") as pic:
            r=session.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id":chat_id,"caption":caption,
                      "reply_markup":json.dumps(markup)},
                files={"photo":pic},timeout=60)
    r.raise_for_status()
    data=r.json()
    if not data.get("ok"):raise RuntimeError("Telegram photo not accepted")
    return data["result"]["message_id"]

def process(data,now,*,session,token,chat_ids,supabase_url,supabase_key):
    if data.get("source")!="bsd" or data.get("model_version")!="bsd-v2-isolated":
        raise ValueError("Production JSON is not BSD V2")
    selections=due(data["matches"],now)
    report={"due":len(selections),"sent":0,"already_claimed":0,"errors":0}
    for match in selections:
        for chat in chat_ids:
            claimed=False
            try:
                claimed=claim(session,supabase_url,supabase_key,match,chat)
                if not claimed:
                    report["already_claimed"]+=1
                    continue
                send_one(session,token,chat,match)
                report["sent"]+=1
                time.sleep(.3)
            except Exception as e:
                report["errors"]+=1
                print("TELEGRAM_BSD_ERROR:",match["id"],type(e).__name__,str(e)[:180])
                if claimed:
                    try:
                        release_failed_claim(session,supabase_url,supabase_key,match,chat)
                    except Exception as release_error:
                        print("TELEGRAM_BSD_RELEASE_ERROR:",type(release_error).__name__)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",default="data.json")
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    data=json.loads(Path(args.data).read_text(encoding="utf-8"))
    now=datetime.now(timezone.utc)
    if data.get('source') != 'bsd' or data.get('model_version') != 'bsd-v2-isolated':
        raise RuntimeError('Le fichier de pronostics du site ne provient pas de BSD V2')
    generated = _utc(str(data.get('generated_at') or ''))
    if now - generated > timedelta(hours=36):
        raise RuntimeError('Pronostics BSD V2 trop anciens: Telegram ne diffuse pas un ancien fichier')
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
