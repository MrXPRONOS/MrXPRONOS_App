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
from bsd_v2_telegram_ledger import SINGLE,COMBO,selection_for_result,normalized_ref,pending_records

def sent_records(session,base,key,limit=500,max_pages=30):
    return pending_records(session,base,key,KIND,limit=limit,max_pages=max_pages)


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
        if now<ko+timedelta(hours=4):return None
        actual=_utc(event["event_date"])
        # Official event ID establishes identity. Retain safeguards for large
        # unexpected shifts, but do not block legitimate rescheduling.
        if abs((actual-ko).total_seconds())>30*86400:return None
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

def claim_settlement(session,base,key,row,*,kind):
    """Atomically reserve a single validation attempt to avoid winner duplicates."""
    if row.get("settlement_status") not in (None,"pending"):
        return False
    resp=session.patch(base.rstrip("/")+"/rest/v1/telegram_sent",
        headers={**headers(key),"Prefer":"return=representation"},
        params={"id":"eq."+str(row["id"]),"kind":"eq."+kind,
                "validation_sent":"eq.false","settlement_status":"eq.pending"},
        json={"settlement_status":"sending",
              "settlement_claimed_at":datetime.now(timezone.utc).isoformat()},
        timeout=30)
    resp.raise_for_status()
    data=resp.json()
    return isinstance(data,list) and len(data)==1

def finalize_settlement(session,base,key,row,*,kind,status,message_id=None,details=""):
    payload={"validation_sent":True,"settlement_status":status,
             "validated_at":datetime.now(timezone.utc).isoformat(),
             "validation_details":details}
    if message_id is not None:payload["validation_message_id"]=message_id
    resp=session.patch(base.rstrip("/")+"/rest/v1/telegram_sent",
        headers=headers(key),params={"id":"eq."+str(row["id"]),"kind":"eq."+kind,
                                     "settlement_status":"eq.sending"},
        json=payload,timeout=30)
    resp.raise_for_status()

def manual_review(session,base,key,row,*,kind,reason):
    resp=session.patch(base.rstrip("/")+"/rest/v1/telegram_sent",
        headers=headers(key),params={"id":"eq."+str(row["id"]),"kind":"eq."+kind,
                                     "settlement_status":"eq.sending"},
        json={"settlement_status":"manual_review","validation_details":str(reason)[:200]},
        timeout=30)
    resp.raise_for_status()

def mark_verified(session,base,key,row_id):
    resp=session.patch(base.rstrip("/")+"/rest/v1/telegram_sent",
        headers=headers(key),params={"id":"eq."+str(row_id),
        "kind":"eq."+KIND,"validation_sent":"eq.false"},
        json={"validation_sent":True},timeout=30)
    resp.raise_for_status()

def _selected_match(row,matches):
    frozen=selection_for_result(row.get("selection_snapshot"))
    if frozen:return frozen
    parsed=normalized_ref(row)
    if parsed is None:return None
    _chat,ident,key=parsed
    match=matches.get("bsd:"+ident)
    if not match:return None
    if key:
        choices=match.get("predictions") or []
        pick=next((p for p in choices if isinstance(p,dict) and p.get("selection_key")==key),None)
        return {**match,"prediction":pick} if pick else None
    return match

def _reason(match,event,now):
    if not event:return "official_result_unavailable"
    if str(event.get("status") or "").lower()!="finished":
        return "official_not_finished"
    try:
        start=_utc(match["event_date"])
        if now<start+timedelta(hours=4):return "verification_wait"
        if abs((_utc(event["event_date"])-start).total_seconds())>30*86400:
            return "kickoff_mismatch_review"
    except (ValueError,KeyError,TypeError):return "invalid_kickoff"
    return "unsupported_market_or_score"

def validate(data,rows,events,now,session,token,base,key,dry_run=False):
    matches={str(m.get("id")):m for m in data.get("matches",[])
             if isinstance(m,dict) and m.get("source")=="bsd"}
    report=Counter()
    for row in rows:
        parsed=normalized_ref(row)
        if parsed is None:
            report["invalid_ledger_ref"]+=1;continue
        chat,ident,_market=parsed
        match=_selected_match(row,matches)
        if not match:
            report["missing_original_selection"]+=1;continue
        if row.get("delivery_status") not in ("sent","legacy",None):
            report["delivery_not_confirmed"]+=1;continue
        if row.get("settlement_status") not in ("pending",None):
            report["manual_review_or_in_progress"]+=1;continue
        result=verdict(match,events.get(ident),now)
        if result is None:
            report[_reason(match,events.get(ident),now)]+=1
            report["pending"]+=1
            continue
        won,home,away=result
        if dry_run:
            report["would_win" if won else "would_lose"]+=1
            continue
        if not claim_settlement(session,base,key,row,kind=KIND):
            report["already_claimed"]+=1;continue
        try:
            if won:
                ticket={**match,"home_score":home,"away_score":away,"status":"finished"}
                message_id=post_gain(session,token,chat,ticket)
                finalize_settlement(session,base,key,row,kind=KIND,status="won",
                                    message_id=message_id,details=f"{home}:{away}")
                report["wins_sent"]+=1
            else:
                finalize_settlement(session,base,key,row,kind=KIND,status="lost",
                                    details=f"{home}:{away}")
                report["losses_silent"]+=1
        except Exception as exc:
            report["settlement_errors"]+=1
            print("BSD_SETTLE_ERROR",ident,type(exc).__name__,str(exc)[:180])
            # A sendPhoto HTTP timeout might mean Telegram accepted the win.
            # Never blindly retry after an uncertain delivery.
            try:manual_review(session,base,key,row,kind=KIND,reason=exc)
            except Exception:report["manual_review_save_errors"]+=1
    return dict(report)

def validate_combos(rows,events,now,session,token,base,key,dry_run=False):
    """Settle both original combo legs; never reward partial two-leg wins."""
    from bsd_v2_captions import combo_caption
    report=Counter()
    for row in rows:
        stored=row.get("selection_snapshot")
        if (not isinstance(stored,dict) or stored.get("type")!="combo"
                or len(stored.get("legs") or [])!=2):
            report["legacy_combo_no_snapshot"]+=1
            continue
        if row.get("delivery_status") not in ("sent","legacy",None):
            report["delivery_not_confirmed"]+=1;continue
        if row.get("settlement_status") not in ("pending",None):
            report["manual_review_or_in_progress"]+=1;continue
        results=[]
        reasons=[]
        for leg in stored["legs"]:
            if not selection_for_result(leg):
                reasons.append("invalid_snapshot");continue
            event_id=str(leg.get("id","")).removeprefix("bsd:")
            result=verdict(leg,events.get(event_id),now)
            if result is None:reasons.append(_reason(leg,events.get(event_id),now))
            else:results.append((leg,result))
        if reasons:
            report["pending"]+=1
            for reason in reasons:report["combo_"+reason]+=1
            continue
        won=all(r[0] for _,r in results)
        if dry_run:
            report["would_win" if won else "would_lose"]+=1;continue
        if not claim_settlement(session,base,key,row,kind=COMBO):
            report["already_claimed"]+=1;continue
        try:
            if won:
                chat=str(row.get("ref_id") or "").split(":combo:")[0]
                if not chat:raise ValueError("Missing original Telegram chat")
                combo={"id":stored["id"],"legs":[{**leg,"home_score":r[1],
                        "away_score":r[2],"status":"finished"} for leg,r in results],
                        "combined_odds":stored.get("combined_odds"),"date":row.get("ref_date")}
                with tempfile.TemporaryDirectory() as directory:
                    from bsd_v2_combo_card import render_combo
                    from bsd_v2_telegram_banner import attach_banner
                    image=attach_banner(render_combo(combo,Path(directory)/"win_combo.png",win=True))
                    with image.open("rb") as pic:
                        resp=session.post("https://api.telegram.org/bot"+token+"/sendPhoto",
                            data={"chat_id":chat,
                                  "caption":"✅ COMBINÉ GAGNANT · MR XPRONOS\n"
                                            "Deux sélections gagnantes, résultats vérifiés.",
                                  "parse_mode":PARSE_MODE,"reply_markup":json.dumps(action_buttons())},
                            files={"photo":pic},timeout=60)
                    resp.raise_for_status()
                    payload=resp.json()
                    if not payload.get("ok"):raise RuntimeError("Telegram combo win rejected")
                    msg=payload["result"]["message_id"]
                finalize_settlement(session,base,key,row,kind=COMBO,status="won",message_id=msg)
                report["combos_wins_sent"]+=1
            else:
                finalize_settlement(session,base,key,row,kind=COMBO,status="lost")
                report["combos_losses_silent"]+=1
        except Exception as exc:
            report["settlement_errors"]+=1
            print("BSD_COMBO_SETTLE_ERROR",type(exc).__name__,str(exc)[:160])
            try:manual_review(session,base,key,row,kind=COMBO,reason=exc)
            except Exception:report["manual_review_save_errors"]+=1
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
    combo_rows=pending_records(session,base,key,COMBO)
    if not rows and not combo_rows:
        print("BSD_V2_VERIFY: no pending published coupons");return
    data,recovered=restore_published_matches(data,rows)
    match_index={str(m.get("id")):m for m in data.get("matches",[]) if isinstance(m,dict)}
    now=datetime.now(timezone.utc)
    days=set()
    for row in [*rows,*combo_rows]:
        _chat,_sep,selection_ref=str(row.get("ref_id") or "").rpartition(":bsd:")
        ident=selection_ref.partition(":")[0]
        match=selection_for_result(row.get("selection_snapshot")) or match_index.get("bsd:"+ident)
        if match:
            try:
                ko=_utc(match["event_date"])
                if now>=ko+timedelta(hours=4):days.add(ko.date())
            except (TypeError,KeyError,ValueError):pass
    for row in combo_rows:
        snap=row.get("selection_snapshot") or {}
        for leg in snap.get("legs",[]):
            try:
                ko=_utc(leg["event_date"])
                if now>=ko+timedelta(hours=4):days.add(ko.date())
            except (KeyError,ValueError,TypeError):pass
    client=BSDClient(max_requests=60) if days else None
    events=official_results(client,days) if client else {}
    summary=validate(data,rows,events,now,session,token,base,key,args.dry_run)
    combined=validate_combos(combo_rows,events,now,session,token,base,key,args.dry_run)
    print("BSD_V2_VERIFY:",json.dumps({**summary,"api_calls":client.requests_made if client else 0,
                                         "ledger_items":len(rows),"combo_ledger_items":len(combo_rows),
                                         "combo_report":combined,"historical_recovered":recovered}))
    if summary.get("settlement_errors") or combined.get("settlement_errors"):
        raise SystemExit("Settlement requires manual review")

if __name__=="__main__":
    main()
