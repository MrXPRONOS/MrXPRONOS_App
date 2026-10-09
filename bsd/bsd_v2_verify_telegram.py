#!/usr/bin/env python3
"""Check prior Telegram picks against BSD final scores, post WIN images only."""
import argparse,json,os,tempfile
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
import requests
from bsd_api import BSDClient
from bsd_h2h import _utc,_valid_score
from bsd_markets import candidates_from_goals,realized
from bsd_v2_card import render as render_card
from bsd_v2_captions import gain_caption,PARSE_MODE
from bsd_v2_telegram import KIND,URL,headers,action_buttons
from bsd_v2_verify_history import restore_published_matches

def sent_records(session,base,key,limit=500,max_pages=12):
    """Page through pending individual selections, including second picks."""
    since=(datetime.now(timezone.utc)-timedelta(days=10)).date().isoformat()
    all_rows=[]
    for page in range(max_pages):
        r=session.get(base.rstrip("/")+"/rest/v1/telegram_sent",
            headers=headers(key),params={"select":"id,ref_id,ref_date,validation_sent",
                "kind":"eq."+KIND,"validation_sent":"eq.false",
                "ref_date":"gte."+since,"order":"ref_date.asc,id.asc",
                "limit":limit,"offset":page*limit},timeout=30)
        r.raise_for_status()
        rows=r.json()
        if not isinstance(rows,list):raise RuntimeError("Malformed Telegram ledger page")
        all_rows.extend(rows)
        if len(rows)<limit:return all_rows
    raise RuntimeError("Telegram ledger exceeds safe pagination limit")


def official_results(client,days):
    records={}
    for day in sorted(days):
        page=client.list_events(day,day,max_pages=12,ttl=0)
        if not page.complete:raise RuntimeError("Incomplete BSD results "+str(day))
        for item in page.events:
            if isinstance(item,dict) and item.get("id") is not None:
                records[str(item["id"])]=item
    return records

def verdict(match,event,now):
    if not event or str(event.get("status") or "").lower()!="finished":return None
    try:
        ko=_utc(match["event_date"])
        if ko!=_utc(event["event_date"]) or now<ko+timedelta(hours=4):return None
    except (ValueError,KeyError,TypeError):return None
    h,a=_valid_score(event.get("home_score")),_valid_score(event.get("away_score"))
    if h is None or a is None:return None
    candidates={c.key:c for c in candidates_from_goals(1.4,1.1)}
    market=candidates.get(match.get("prediction",{}).get("selection_key"))
    if market is None:return None
    return bool(realized(market,h,a)),h,a

def post_gain(session,token,chat,match):
    with tempfile.TemporaryDirectory() as directory:
        image=render_card(match,Path(directory)/"gain.png",win=True)
        from bsd_v2_telegram_banner import attach_banner
        image=attach_banner(image)
        keyboard=action_buttons()
        with image.open("rb") as pic:
            resp=session.post("https://api.telegram.org/bot"+token+"/sendPhoto",
                data={"chat_id":chat,"caption":gain_caption(match),
                      "reply_markup":json.dumps(keyboard),
                      "parse_mode":PARSE_MODE},
                files={"photo":pic},timeout=60)
    resp.raise_for_status()
    j=resp.json()
    if not j.get("ok"):raise RuntimeError("Telegram gain rejected")
    return j["result"]["message_id"]

def mark_verified(session,base,key,row_id):
    resp=session.patch(base.rstrip("/")+"/rest/v1/telegram_sent",
        headers=headers(key),params={"id":"eq."+str(row_id),
        "kind":"eq."+KIND,"validation_sent":"eq.false"},
        json={"validation_sent":True},timeout=30)
    resp.raise_for_status()

def validate(data,rows,events,now,session,token,base,key,dry_run=False):
    matches={str(m.get("id")):m for m in data.get("matches",[])
             if isinstance(m,dict) and m.get("source")=="bsd"}
    report=Counter()
    for row in rows:
        ref=str(row.get("ref_id") or "")
        chat,sep,selection_ref=ref.rpartition(":bsd:")
        ident,extra_sep,selection_key=selection_ref.partition(":")
        if not sep or not chat or not ident.isdigit():
            report["invalid_ledger_ref"]+=1;continue
        match=matches.get("bsd:"+ident)
        if not match:
            report["missing_site_match"]+=1;continue
        if extra_sep:
            picks=match.get("predictions") or []
            selected=next((p for p in picks if p.get("selection_key")==selection_key),None)
            if selected is None:
                report["missing_original_market"]+=1
                continue
            match={**match,"prediction":selected}
        result=verdict(match,events.get(ident),now)
        if result is None:
            report["pending"]+=1;continue
        won,home,away=result
        if dry_run:
            report["would_win" if won else "would_lose"]+=1;continue
        if won:
            match_for_image={**match,"home_score":home,"away_score":away,"status":"finished"}
            try:
                post_gain(session,token,chat,match_for_image)
            except Exception as exc:
                report["delivery_errors"]+=1
                print("BSD_WIN_SEND_ERROR",ident,type(exc).__name__,str(exc)[:160])
                continue
            mark_verified(session,base,key,row["id"])
            report["wins_sent"]+=1
        else:
            mark_verified(session,base,key,row["id"])
            report["losses_silent"]+=1
    return dict(report)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--feed",default="data.json")
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    data=json.loads(Path(args.feed).read_text(encoding="utf-8"))
    if data.get("source")!="bsd":raise RuntimeError("Site feed not BSD")
    token=os.getenv("TELEGRAM_BOT_TOKEN")
    base=os.getenv("SUPABASE_URL")
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not base or not key or (not token and not args.dry_run):
        raise RuntimeError("Missing credentials")
    session=requests.Session()
    rows=sent_records(session,base,key)
    if not rows:
        print("BSD_V2_VERIFY: no pending published coupons");return
    data,recovered=restore_published_matches(data,rows)
    match_index={str(m.get("id")):m for m in data.get("matches",[]) if isinstance(m,dict)}
    now=datetime.now(timezone.utc)
    days=set()
    for row in rows:
        _chat,_sep,selection_ref=str(row.get("ref_id") or "").rpartition(":bsd:")
        ident=selection_ref.partition(":")[0]
        match=match_index.get("bsd:"+ident)
        if match:
            try:
                ko=_utc(match["event_date"])
                if now>=ko+timedelta(hours=4):days.add(ko.date())
            except (TypeError,KeyError,ValueError):pass
    client=BSDClient(max_requests=60) if days else None
    events=official_results(client,days) if client else {}
    summary=validate(data,rows,events,now,session,token,base,key,args.dry_run)
    print("BSD_V2_VERIFY:",json.dumps({**summary,"api_calls":client.requests_made if client else 0,
                                         "ledger_items":len(rows),"historical_recovered":recovered}))
    if summary.get("delivery_errors"):raise SystemExit("Winning card delivery failed")

if __name__=="__main__":
    main()
