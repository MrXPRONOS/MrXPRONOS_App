#!/usr/bin/env python3
"""REAL daily Hybrid V3 prematch forecast, using certified V3 research engine.

2024-2026 fully certified research history ends 2026-10-24. From 2026-10-25
onwards, only the DAILY refreshed encrypted BSD archive on the production
checkout supplies finished results, strictly no later than yesterday UTC.
The original single_ml_v2.backtest replays historical state, fits REAL
HistGradientBoosting V3 and calibrates V3 hybrid. Future fixtures are never
trained on or settled. Public publishing is a separate validated step.

No production Pro/VIP model, bet placement, Telegram or bookmaker odds.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from single_ml_v2_git import key_from_environment
from single_ml_v2_multisource import CUTOFF, certified_rows, check_ml_loader
from single_ml_v2 import Match, backtest

# main checkout bsd modules are supplied via PYTHONPATH by GitHub Actions.
from bsd_api import BSDClient
from bsd_archive import MATCHES_FILE, STATE_FILE
from bsd_h2h import _utc, _team_id, _valid_score

MODEL = "machine_learning_v3_hybrid"
MIN_RECENT = 40


def label(row, side):
    value = row.get(side + "_team")
    if isinstance(value,dict):
        value = value.get("name")
    if not isinstance(value,str) or not value.strip():
        value = row.get(side+"_team_name")
    return value.strip() if isinstance(value,str) else ""


def competition(row):
    for field in ("league_name","competition_name","tournament_name"):
        value = row.get(field)
        if isinstance(value,str) and value.strip():
            return value.strip()
    value = row.get("league")
    if isinstance(value,dict):
        value = value.get("name")
    return value.strip() if isinstance(value,str) and value.strip() else ""


def archive_tail(events, *, asof):
    """Normalize only SETTLED post-cutoff BSD fixtures; reject same-day labels."""
    if not isinstance(events,list):
        raise ValueError("BSD archive has no finished match list")
    by_id = {}
    invalid = 0
    for event in events:
        if not isinstance(event,dict) or event.get("id") is None:
            continue
        try:
            time = _utc(str(event.get("event_date") or ""))
        except (ValueError,TypeError,OverflowError):
            invalid += 1
            continue
        d = time.date()
        if d <= CUTOFF or d >= asof.date():
            continue
        if str(event.get("status") or "").lower() != "finished":
            continue
        gh,ga = _valid_score(event.get("home_score")),_valid_score(event.get("away_score"))
        home,away,league = label(event,"home"),label(event,"away"),competition(event)
        if (gh is None or ga is None or gh>10 or ga>10
                or not home or not away or home==away or not league):
            invalid += 1
            continue
        eid = str(event["id"])
        mid = "bsd-tail:"+eid
        item = Match(mid,d,league,home,away,gh,ga)
        if mid in by_id and by_id[mid] != item:
            raise ValueError("Contradictory BSD fixture with same event id")
        by_id[mid] = item
    rows = sorted(by_id.values(),key=lambda m:(m.day,m.key))
    if len(rows) < MIN_RECENT:
        raise ValueError("BSD post-cutoff finished history has too few authentic fixtures")
    if (asof.date()-rows[-1].day).days>3:
        raise ValueError("BSD finished football history too stale for daily forecasting")
    print("V3_RECENT_BSD_AUDIT",json.dumps({
        "post_cutoff_finished":len(rows),"latest":str(rows[-1].day),
        "invalid_ignored":invalid,"source":"encrypted_production_BSD_archive",
        "future_or_same_day_labels_excluded":True,
    }),flush=True)
    return rows


def fixtures_today(client, *, asof):
    """Read BSD scheduled football fixtures with FULL pagination and valid UTC times."""
    day = asof.date()
    page=client.list_events(day,day,max_pages=25,page_size=200,ttl=0)
    if not page.complete:
        raise ValueError("Incomplete BSD scheduled match pagination; do not publish guesses")
    found={}
    counts={"total":len(page.events),"future":0,"excluded":0}
    for event in page.events:
        if not isinstance(event,dict) or event.get("id") is None:
            counts["excluded"]+=1
            continue
        if str(event.get("status") or "").lower() not in ("notstarted","upcoming","scheduled"):
            counts["excluded"]+=1
            continue
        try:
            start=_utc(str(event.get("event_date") or ""))
        except (ValueError,TypeError,OverflowError):
            counts["excluded"]+=1
            continue
        if start.date()!=day or start <= asof + timedelta(minutes=5):
            counts["excluded"]+=1
            continue
        home,away,league=label(event,"home"),label(event,"away"),competition(event)
        if not (home and away and league and home!=away):
            counts["excluded"]+=1
            continue
        mid="bsd-upcoming:"+str(event["id"])
        record={
            "id":mid,"home":home,"away":away,"league":league,
            "kickoff_utc":start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if mid in found and found[mid]!=record:
            raise ValueError("BSD future fixture ID has conflicting kickoff or team")
        found[mid]=record
    counts["future"]=len(found)
    print("V3_BSD_SCHEDULE_AUDIT",json.dumps({
        **counts,"complete":page.complete,"reported":page.total_reported,
        "pages":page.pages_fetched,"no_result_in_future_fixtures":True
    }),flush=True)
    return sorted(found.values(),key=lambda x:(x["kickoff_utc"],x["id"]))


def load_verified_recent(*, asof):
    if not MATCHES_FILE.is_file() or not STATE_FILE.is_file():
        raise ValueError("Encrypted main BSD archive must be restored before forecast")
    state=json.loads(STATE_FILE.read_text(encoding="utf8"))
    if state.get("provider")!="BSD":
        raise ValueError("Wrong authenticated BSD archive provider")
    refreshed=state.get("last_daily_refresh")
    if not isinstance(refreshed,str):
        raise ValueError("Missing BSD last daily refresh provenance")
    stamp=_utc(refreshed)
    if stamp>asof+timedelta(minutes=5) or (asof-stamp)>timedelta(hours=52):
        raise ValueError("Production BSD archive older than 52 hours; fail closed")
    events=json.loads(MATCHES_FILE.read_text(encoding="utf8"))
    return archive_tail(events,asof=asof)


def generate_daily(*, out, max_bsd_requests=40):
    asof=datetime.now(timezone.utc)
    if asof.date() <= CUTOFF:
        raise ValueError("Prospective generation requires date after frozen 2026 archive")
    recent=load_verified_recent(asof=asof)
    # Fetch today before training, then revalidate exact kickoff against
    # ACTUAL publication time after expensive retrospective V3 fitting.
    client=BSDClient(max_requests=max_bsd_requests)
    future=fixtures_today(client,asof=asof)
    if not future:
        raise ValueError("BSD source returned no genuinely upcoming fixtures; no publication")
    key=key_from_environment()
    source=certified_rows(key)
    historical=check_ml_loader(source)
    source.clear()
    del source
    old_ids={row.key for row in historical}
    if any(m.key in old_ids for m in recent):
        raise ValueError("Historical duplicate across certified research and recent BSD")
    history=sorted([*historical,*recent],key=lambda m:(m.day,m.key))
    del historical
    latest=history[-1].day
    if latest>=asof.date():
        raise ValueError("Same-day result accidentally entered training")
    begin=max(date(2026,10,1),CUTOFF-timedelta(days=23))
    if latest<begin:
        raise ValueError("No completed post-cutoff days to fit Hybrid V3")
    os.makedirs(out,exist_ok=True)
    backtest(history,begin,latest,str(out),auto_tune=False,retrain_days=30,
             max_eval=0,v3_models=True,prospective_fixtures=future)
    result=Path(out)/"v3_prospective_raw.json"
    if not result.is_file():
        raise RuntimeError("Actual Hybrid V3 prospective output absent")
    obj=json.loads(result.read_text(encoding="utf8"))
    if (obj.get("origin")!="prospective_prematch" or obj.get("model")!=MODEL
            or not isinstance(obj.get("fixtures"),list)):
        raise ValueError("Actual V3 engine returned invalid prospective forecast")
    print("DAILY_HYBRID_V3_READY",json.dumps({
        "date":obj["generated_at"][:10],"fixtures":len(obj["fixtures"]),
        "model":MODEL,"no_site_or_telegram_modified":True,
        "historical_source_frozen_to":str(CUTOFF),
        "latest_history":str(latest)
    }),flush=True)


def main():
    parser=argparse.ArgumentParser(description="Daily authentic research Hybrid V3 forecast")
    parser.add_argument("--out",default="/tmp/mrx-hybrid-v3-daily",type=Path)
    parser.add_argument("--max-bsd-requests",default=40,type=int)
    args=parser.parse_args()
    if not str(args.out.resolve()).startswith("/tmp/"):
        raise ValueError("Private, non-production intermediate forecast must remain in /tmp")
    generate_daily(out=args.out,max_bsd_requests=args.max_bsd_requests)


if __name__=="__main__":
    main()
