#!/usr/bin/env python3
"""Validate sent BSD Telegram coupons against official final scores.

Individual coupons keep the historical H+4 safety delay.
Combined coupons are different: as soon as BOTH frozen legs are officially
finished with valid BSD scores and both original selections are winners,
a single verified combined-win card is sent to Telegram.

Supabase is the source of truth for delivery de-duplication. New combo ledger
references contain both frozen match IDs, selection keys and dates so the
validation does not depend on the current website feed. Legacy hash-only combo
rows are reconstructed only from committed historical data.json versions.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from bsd_api import BSDClient
from bsd_h2h import _utc, _valid_score
from bsd_markets import candidates_from_goals, realized
from bsd_v2_card import render as render_card
from bsd_v2_combo_card import render_combo
from bsd_v2_captions import gain_caption, combo_gain_caption
from bsd_v2_combos import (
    build_combos, combo_id_for_legs, parse_combo_ledger_ref,
)
from bsd_v2_night import is_night_match, night_date
from bsd_v2_telegram import KIND, COMBO_KIND, headers, action_buttons
from bsd_v2_verify_history import restore_published_matches
from telegram_rich import post_photo

COMBO_VALIDATION_KIND="bsd_v2_combo_validation"


def _ledger_rows(session,base,key,kind,*,since_days=10,limit=500,max_pages=12):
    since=(datetime.now(timezone.utc)-timedelta(days=since_days)).date().isoformat()
    all_rows=[]
    for page in range(max_pages):
        response=session.get(base.rstrip("/")+"/rest/v1/telegram_sent",
            headers=headers(key),params={
                "select":"id,ref_id,ref_date,validation_sent",
                "kind":"eq."+kind,
                "ref_date":"gte."+since,
                "order":"ref_date.asc,id.asc",
                "limit":limit,"offset":page*limit},timeout=30)
        response.raise_for_status()
        rows=response.json()
        if not isinstance(rows,list):
            raise RuntimeError("Malformed Telegram ledger page")
        all_rows.extend(rows)
        if len(rows)<limit:
            return all_rows
    raise RuntimeError("Telegram ledger exceeds safe pagination limit")


def sent_records(session,base,key,limit=500,max_pages=12):
    """Pending individual selections only."""
    rows=_ledger_rows(session,base,key,KIND,limit=limit,max_pages=max_pages)
    return [row for row in rows if row.get("validation_sent") is False]


def combo_records(session,base,key,limit=500,max_pages=12):
    """All uncompleted combined coupons, including legacy rows marked true.

    Older code incorrectly created combo rows with validation_sent=True from the
    moment they were sent. A separate completion ledger lets us safely recover
    those rows once without ever double-posting a verified win.
    """
    combos=_ledger_rows(session,base,key,COMBO_KIND,limit=limit,max_pages=max_pages)
    completed=_ledger_rows(session,base,key,COMBO_VALIDATION_KIND,
                           limit=limit,max_pages=max_pages)
    done={str(row.get("ref_id") or "") for row in completed}
    return [row for row in combos if str(row.get("ref_id") or "") not in done]


def official_results(client,days):
    records={}
    for day in sorted(days):
        page=client.list_events(day,day,max_pages=12,ttl=0)
        if not page.complete:
            raise RuntimeError("Incomplete BSD results "+str(day))
        for item in page.events:
            if isinstance(item,dict) and item.get("id") is not None:
                records[str(item["id"])]=item
    return records


def verdict(match,event,now):
    """Individual coupon verdict; keeps historical H+4 safety delay."""
    if not event or str(event.get("status") or "").lower()!="finished":
        return None
    try:
        ko=_utc(match["event_date"])
        if ko!=_utc(event["event_date"]) or now<ko+timedelta(hours=4):
            return None
    except (ValueError,KeyError,TypeError):
        return None
    h,a=_valid_score(event.get("home_score")),_valid_score(event.get("away_score"))
    if h is None or a is None:
        return None
    candidates={c.key:c for c in candidates_from_goals(1.4,1.1)}
    market=candidates.get(match.get("prediction",{}).get("selection_key"))
    if market is None:
        return None
    return bool(realized(market,h,a)),h,a


def _leg_verdict(leg,event):
    """Immediate official leg verdict for combined coupons.

    No H+4 delay: BSD must explicitly report finished, kickoff must match,
    score must be valid, and the exact frozen market key is evaluated.
    """
    if not isinstance(event,dict) or str(event.get("status") or "").lower()!="finished":
        return None
    try:
        if _utc(leg["event_date"])!=_utc(event["event_date"]):
            return None
    except (ValueError,KeyError,TypeError):
        return None
    h,a=_valid_score(event.get("home_score")),_valid_score(event.get("away_score"))
    if h is None or a is None:
        return None
    candidates={c.key:c for c in candidates_from_goals(1.4,1.1)}
    market=candidates.get((leg.get("prediction") or {}).get("selection_key"))
    if market is None:
        return None
    return bool(realized(market,h,a)),h,a


def combo_verdict(combo,events):
    """Return None while unresolved, otherwise (won, frozen legs with scores).

    A losing leg is sufficient to settle the whole combo as lost. A WIN is
    returned only when both legs are officially finished and both are winners.
    """
    legs=combo.get("legs") or []
    if len(legs)!=2:
        return None
    checked=[]
    for leg in legs:
        ident=str(leg.get("source_event_id") or str(leg.get("id","")).removeprefix("bsd:"))
        result=_leg_verdict(leg,events.get(ident))
        if result is None:
            checked.append(None)
            continue
        won,h,a=result
        scored={**leg,"home_score":h,"away_score":a,"status":"finished","is_finished":True}
        if not won:
            return False,legs
        checked.append(scored)
    if any(row is None for row in checked):
        return None
    return True,checked


def post_gain(session,token,chat,match):
    with tempfile.TemporaryDirectory() as directory:
        image=render_card(match,Path(directory)/"gain.png",win=True)
        from bsd_v2_telegram_banner import attach_banner
        image=attach_banner(image)
        return post_photo(session,token,chat,image,gain_caption(match),
                          action_buttons(),timeout=60)


def post_combo_gain(session,token,chat,combo):
    with tempfile.TemporaryDirectory() as directory:
        image=render_combo(combo,Path(directory)/"combo-gain.png",
                           session=session,win=True)
        from bsd_v2_telegram_banner import attach_banner
        image=attach_banner(image)
        return post_photo(session,token,chat,image,combo_gain_caption(combo),
                          action_buttons(),timeout=60)


def mark_verified(session,base,key,row_id):
    response=session.patch(base.rstrip("/")+"/rest/v1/telegram_sent",
        headers=headers(key),params={"id":"eq."+str(row_id),
        "kind":"eq."+KIND,"validation_sent":"eq.false"},
        json={"validation_sent":True},timeout=30)
    response.raise_for_status()


def _record_combo_completion(session,base,key,row):
    """Write completion marker first; then mark the source row if applicable.

    The separate marker is what prevents duplicate verified-win posts,
    including for legacy source rows that already had validation_sent=True.
    """
    ref=str(row.get("ref_id") or "")
    date=str(row.get("ref_date") or "")
    response=session.post(base.rstrip("/")+"/rest/v1/telegram_sent",
        params={"on_conflict":"kind,ref_id,ref_date"},
        headers=headers(key),
        json={"kind":COMBO_VALIDATION_KIND,"ref_id":ref,
              "ref_date":date,"validation_sent":True},timeout=30)
    response.raise_for_status()
    if row.get("validation_sent") is False:
        patch=session.patch(base.rstrip("/")+"/rest/v1/telegram_sent",
            headers=headers(key),params={
                "id":"eq."+str(row["id"]),
                "kind":"eq."+COMBO_KIND,
                "validation_sent":"eq.false"},
            json={"validation_sent":True},timeout=30)
        patch.raise_for_status()


def _select_original_market(match,key):
    candidates=[]
    primary=match.get("prediction")
    if isinstance(primary,dict):
        candidates.append(primary)
    for pick in match.get("predictions") or []:
        if isinstance(pick,dict):
            candidates.append(pick)
    selected=next((p for p in candidates if p.get("selection_key")==key),None)
    return {**match,"prediction":selected} if selected is not None else None


def _restore_new_combo(data,parsed):
    """Recover exact self-described legs from current or committed feed history."""
    pseudo=[]
    for leg in parsed["legs"]:
        suffix=":"+leg["selection_key"]
        pseudo.append({"ref_id":parsed["chat"]+":"+leg["id"]+suffix,
                       "ref_date":leg["date"]})
    restored,_=restore_published_matches(data,pseudo)
    index={(str(m.get("id")),str(m.get("date"))):m
           for m in restored.get("matches",[]) if isinstance(m,dict)}
    legs=[]
    for spec in parsed["legs"]:
        match=index.get((spec["id"],spec["date"]))
        if match is None:
            return None
        selected=_select_original_market(match,spec["selection_key"])
        if selected is None:
            return None
        legs.append(selected)
    try:
        if combo_id_for_legs(legs)!=parsed["combo_id"]:
            return None
    except ValueError:
        return None
    odds=1.0
    for leg in legs:
        try:
            odds*=float((leg.get("prediction") or {})["odds"])
        except (KeyError,TypeError,ValueError):
            return None
    return {"id":parsed["combo_id"],"type":"combiné","status":"upcoming",
            "event_date":legs[0]["event_date"],"date":legs[0]["date"],
            "legs":legs,"combined_odds":round(odds,5)}


def _historical_combo_candidates(snapshot):
    """Rebuild exactly the same day/night grouping used for Telegram delivery."""
    matches=[m for m in snapshot.get("matches",[]) if isinstance(m,dict)]
    for combo in build_combos([m for m in matches if not is_night_match(m)]):
        yield combo
    groups=defaultdict(list)
    for match in matches:
        day=night_date(match.get("event_date"))
        if day is not None:
            groups[str(day)].append(match)
    for rows in groups.values():
        for combo in build_combos(rows):
            yield combo


def _restore_legacy_combo(combo_id, data, repository=None, max_versions=350):
    """Recover old hash-only combos only from immutable committed feed history."""
    for combo in _historical_combo_candidates(data):
        if combo.get("id")==combo_id:
            return combo
    root=Path(repository or Path(__file__).resolve().parent.parent)
    try:
        listing=subprocess.run(
            ["git","log","--since=14 days ago",f"--max-count={max_versions}",
             "--format=%H","--","data.json"],
            cwd=root,capture_output=True,text=True,check=True,timeout=30)
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        return None
    for commit in listing.stdout.splitlines():
        if len(commit)!=40:
            continue
        try:
            raw=subprocess.run(["git","show",f"{commit}:data.json"],
                cwd=root,capture_output=True,text=True,check=True,timeout=15)
            snapshot=json.loads(raw.stdout)
        except (OSError,ValueError,subprocess.CalledProcessError,
                subprocess.TimeoutExpired):
            continue
        for combo in _historical_combo_candidates(snapshot):
            if combo.get("id")==combo_id:
                return combo
    return None


def combo_from_ledger(row,data):
    parsed=parse_combo_ledger_ref(row.get("ref_id"))
    if parsed is None:
        return None,None
    if parsed["legacy"]:
        combo=_restore_legacy_combo(parsed["combo_id"],data)
    else:
        combo=_restore_new_combo(data,parsed)
    return parsed,combo


def validate(data,rows,events,now,session,token,base,key,dry_run=False):
    matches={str(m.get("id")):m for m in data.get("matches",[])
             if isinstance(m,dict) and m.get("source")=="bsd"}
    report=Counter()
    for row in rows:
        ref=str(row.get("ref_id") or "")
        chat,sep,selection_ref=ref.rpartition(":bsd:")
        ident,extra_sep,selection_key=selection_ref.partition(":")
        if not sep or not chat or not ident.isdigit():
            report["invalid_ledger_ref"]+=1
            continue
        match=matches.get("bsd:"+ident)
        if not match:
            report["missing_site_match"]+=1
            continue
        if extra_sep:
            selected=_select_original_market(match,selection_key)
            if selected is None:
                report["missing_original_market"]+=1
                continue
            match=selected
        result=verdict(match,events.get(ident),now)
        if result is None:
            report["pending"]+=1
            continue
        won,home,away=result
        if dry_run:
            report["would_win" if won else "would_lose"]+=1
            continue
        if won:
            match_for_image={**match,"home_score":home,"away_score":away,
                             "status":"finished","is_finished":True}
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


def validate_combos(data,rows,events,session,token,base,key,dry_run=False):
    report=Counter()
    for row in rows:
        parsed,combo=combo_from_ledger(row,data)
        if parsed is None:
            report["combo_invalid_ledger_ref"]+=1
            continue
        if combo is None:
            report["combo_missing_historical_definition"]+=1
            continue
        result=combo_verdict(combo,events)
        if result is None:
            report["combo_pending"]+=1
            continue
        won,legs=result
        if dry_run:
            report["combo_would_win" if won else "combo_would_lose"]+=1
            continue
        if won:
            verified={**combo,"legs":legs,"status":"finished","verified":True}
            try:
                post_combo_gain(session,token,parsed["chat"],verified)
            except Exception as exc:
                report["combo_delivery_errors"]+=1
                print("BSD_COMBO_WIN_SEND_ERROR",combo["id"],
                      type(exc).__name__,str(exc)[:160])
                continue
            _record_combo_completion(session,base,key,row)
            report["combo_wins_sent"]+=1
        else:
            _record_combo_completion(session,base,key,row)
            report["combo_losses_silent"]+=1
        if parsed.get("legacy"):
            report["combo_legacy_recovered"]+=1
    return dict(report)


def _days_for_individuals(rows,data,now):
    index={str(m.get("id")):m for m in data.get("matches",[]) if isinstance(m,dict)}
    days=set()
    for row in rows:
        _chat,_sep,selection_ref=str(row.get("ref_id") or "").rpartition(":bsd:")
        ident=selection_ref.partition(":")[0]
        match=index.get("bsd:"+ident)
        if not match:
            continue
        try:
            ko=_utc(match["event_date"])
            if now>=ko+timedelta(hours=4):
                days.add(ko.date())
        except (TypeError,KeyError,ValueError):
            pass
    return days


def _days_for_combos(rows,data):
    days=set()
    definitions=[]
    for row in rows:
        parsed,combo=combo_from_ledger(row,data)
        definitions.append((row,parsed,combo))
        if combo is None:
            continue
        for leg in combo.get("legs") or []:
            try:
                days.add(_utc(leg["event_date"]).date())
            except (TypeError,KeyError,ValueError):
                pass
    return days,definitions


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--feed",default="data.json")
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()

    data=json.loads(Path(args.feed).read_text(encoding="utf-8"))
    if data.get("source")!="bsd":
        raise RuntimeError("Site feed not BSD")

    token=os.getenv("TELEGRAM_BOT_TOKEN")
    base=os.getenv("SUPABASE_URL")
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not base or not key or (not token and not args.dry_run):
        raise RuntimeError("Missing credentials")

    session=requests.Session()
    rows=sent_records(session,base,key)
    combo_rows=combo_records(session,base,key)
    if not rows and not combo_rows:
        print("BSD_V2_VERIFY: no pending published coupons")
        return

    data,recovered=restore_published_matches(data,rows)
    now=datetime.now(timezone.utc)
    days=_days_for_individuals(rows,data,now)
    combo_days,_definitions=_days_for_combos(combo_rows,data)
    days.update(combo_days)

    client=BSDClient(max_requests=120) if days else None
    events=official_results(client,days) if client else {}

    singles=validate(data,rows,events,now,session,token,base,key,args.dry_run)
    combos=validate_combos(data,combo_rows,events,session,token,base,key,args.dry_run)
    summary={**singles,**combos,
             "api_calls":client.requests_made if client else 0,
             "ledger_items":len(rows),
             "combo_ledger_items":len(combo_rows),
             "historical_recovered":recovered}
    print("BSD_V2_VERIFY:",json.dumps(summary))
    if summary.get("delivery_errors") or summary.get("combo_delivery_errors"):
        raise SystemExit("Winning card delivery failed")


if __name__=="__main__":
    main()
