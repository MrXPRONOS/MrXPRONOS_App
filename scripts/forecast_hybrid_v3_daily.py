#!/usr/bin/env python3
"""Genuine daily prospective Hybrid V3 (same frozen 2026 research estimator).

Dependencies: main BSD API/history; research/single-ml-v2-20261024 sealed
certified 2024-2026 match archive. No future labels, no model substitution.
Site output intentionally split into separate publish_exact_scores.py step.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from itertools import groupby
from pathlib import Path

# The production runner sets PYTHONPATH to vetted, isolated research source.
import numpy as np
from bsd_api import BSDClient
from scripts.resolve_bsd_leagues import resolve_league_labels
from bsd_archive import MATCHES_FILE
from single_ml_v2_multisource import certified_rows, safe_source_identities
from single_ml_v2_git import key_from_environment
from single_ml_v2 import (FormState, Match, load_matches, FEATURE_NAMES,
                          poisson_grid, dixon_coles, estimate_dc_rho)
from single_ml_v2_tune import _validate_rows
from single_ml_v2_opponents import canonical_name
from single_ml_v2_hybrid import DEFAULT_DC_WEIGHT
from single_ml_v3 import (HYBRID_NAME, VERSION as V3_VERSION,
                          fit_hist_v3, hist_v3_grid, hybrid_v3_grid)

HISTORY_CUTOFF = date(2026, 10, 24)
TRAIN_CUTOFF = date(2025, 12, 31)
HISTORIC_FIT_ASOF = date(2026, 1, 1)
MINIMUM_LEAD = timedelta(minutes=20)
MAX_STALE_HISTORY = timedelta(days=4)
MIN_FIT_ROWS = 350
STATUS_UPCOMING = {"notstarted", "upcoming", "scheduled", "not_started", "not started"}


@dataclass(frozen=True)
class TargetFixture:
    # NO observed score attributes: impossible to use result as target feature.
    key: str
    day: date
    league: str
    home: str
    away: str
    home_id: str | None = None
    away_id: str | None = None
    competition_id: str | None = None


def parse_iso(value):
    if not isinstance(value, str) or not value.strip() or "T" not in value:
        raise ValueError("Event has no precise kickoff datetime")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Timezone-free kickoffs are unsafe")
    return stamp.astimezone(timezone.utc)


def proper_name(value):
    if isinstance(value, dict):
        value = value.get("name") or value.get("short_name")
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not (2 <= len(value) <= 120) or value.casefold() in (
        "equipe", "équipe", "team", "home", "away", "football", "soccer", "tbd", "-"):
        return ""
    return value


def competition(row):
    for field in ("league_name", "competition_name", "tournament_name", "league", "competition"):
        name = proper_name(row.get(field))
        if name:
            return name
    return ""


def namespace_id(raw):
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = int(raw)
        if value > 0 and str(value) == str(raw).strip():
            return "bsd_" + str(value)
    except (TypeError, ValueError):
        pass
    return None


def extract_fixture(event, *, now):
    if not isinstance(event, dict) or str(event.get("status") or "").lower().strip() not in STATUS_UPCOMING:
        return None
    if (event.get("home_score") is not None or event.get("away_score") is not None
        or event.get("actual_score") is not None or event.get("is_finished") is True):
        return None
    try:
        stamp = parse_iso(event.get("event_date"))
    except (TypeError, ValueError, OverflowError):
        return None
    if stamp.date() != now.date() or stamp <= now + MINIMUM_LEAD:
        return None
    home = proper_name(event.get("home_team"))
    away = proper_name(event.get("away_team"))
    league = competition(event)
    key = event.get("id")
    if key is None or not str(key).strip() or not home or not away or not league or home == away:
        return None
    fixture = TargetFixture(
        key="bsd:" + str(key), day=stamp.date(), league=league, home=home, away=away,
        home_id=namespace_id(event.get("home_team_id")),
        away_id=namespace_id(event.get("away_team_id")),
        competition_id=namespace_id(event.get("league_id")),
    )
    return fixture, stamp


def fixture_eligibility_diagnostics(events, *, now):
    """Aggregate diagnostic only: does NOT expose exact fixture IDs or scores."""
    statuses=Counter()
    metrics=Counter()
    for e in events:
        if not isinstance(e,dict):
            metrics["not_an_object"]+=1
            continue
        status=str(e.get("status") or "").strip().lower()
        statuses[status or "<missing>"]+=1
        try:
            stamp=parse_iso(e.get("event_date"))
        except (TypeError,ValueError,OverflowError):
            metrics["bad_kickoff"]+=1
            continue
        if stamp.date() != now.date():
            metrics["wrong_day"]+=1
            continue
        if stamp <= now+MINIMUM_LEAD:
            metrics["already_started_or_too_close"]+=1
            continue
        metrics["future_20min"]+=1
        if status not in STATUS_UPCOMING:
            metrics["future_unknown_status"]+=1
        if not competition(e):
            metrics["future_missing_competition_name"]+=1
        if not proper_name(e.get("home_team")) or not proper_name(e.get("away_team")):
            metrics["future_missing_team_name"]+=1
        if e.get("home_score") is not None or e.get("away_score") is not None:
            metrics["future_score_not_null"]+=1
        if extract_fixture(e,now=now) is not None:
            metrics["eligible"]+=1
    return {"statuses":dict(statuses),"counts":dict(metrics)}


def recent_bsd_match(raw, *, target):
    """Only official past finished fixtures; no guessed/in-progress score."""
    if not isinstance(raw, dict) or str(raw.get("status") or "").lower().strip() != "finished":
        return None
    if raw.get("id") is None:
        return None
    try:
        kickoff = parse_iso(raw.get("event_date"))
        h, a = raw.get("home_score"), raw.get("away_score")
        if type(h) not in (int, str) or type(a) not in (int, str):
            return None
        if not (str(h).isdigit() and str(a).isdigit()):
            return None
        h, a = int(h), int(a)
    except (TypeError, ValueError, OverflowError):
        return None
    if not (HISTORY_CUTOFF < kickoff.date() < target
            and kickoff < datetime.combine(target, datetime.min.time(), timezone.utc)
            and 0 <= h <= 10 and 0 <= a <= 10):
        return None
    home = proper_name(raw.get("home_team"))
    away = proper_name(raw.get("away_team"))
    league = competition(raw)
    if not home or not away or not league or home == away:
        return None
    return Match("bsd_recent:" + str(raw["id"]), kickoff.date(), league, home, away,
                 h, a, home_id=namespace_id(raw.get("home_team_id")),
                 away_id=namespace_id(raw.get("away_team_id")),
                 competition_id=namespace_id(raw.get("league_id")))


def recent_verified_matches(archive, client, *, target):
    """Use current sealed BSD history plus a bounded API catch-up window.

    If archival coverage was missing before the API catch-up window, fail
    closed rather than silently training with unobserved months.
    """
    if not isinstance(archive, list) or len(archive) < 1000:
        raise ValueError("Recent BSD archive was not authenticated/restored")
    # A normal daily archive is continuously maintained by the separate BSD
    # production workflows; only use it for POST-2026-10-24 form updates.
    collected = {}
    for raw in archive:
        item = recent_bsd_match(raw, target=target)
        if item is not None:
            collected[item.key.removeprefix("bsd_recent:")] = item
    last_archive = max((m.day for m in collected.values()), default=HISTORY_CUTOFF)
    if last_archive < target - timedelta(days=15):
        raise ValueError("Recent archived history has >14-day gap; cannot certify model form")
    # Catch up from the last archived complete day, not today, so all prior
    # dates needed by new fixtures are represented; no current-day results.
    since = max(HISTORY_CUTOFF + timedelta(days=1), last_archive)
    until = target - timedelta(days=1)
    if since <= until:
        page = client.list_events(since, until, max_pages=45, ttl=0)
        if not page.complete:
            raise RuntimeError("Recent finished-football API window is incomplete")
        for raw in page.events:
            item = recent_bsd_match(raw, target=target)
            if item is None:
                continue
            key = item.key.removeprefix("bsd_recent:")
            prior = collected.get(key)
            if prior is not None:
                if (prior.day,prior.home,prior.away,prior.hg,prior.ag,prior.league) != (
                        item.day,item.home,item.away,item.hg,item.ag,item.league):
                    raise ValueError("Recent BSD historical event changed since sealed archive")
            else:
                collected[key] = item
    recent = sorted(collected.values(), key=lambda x: (x.day, x.key))
    most_recent = max((m.day for m in recent), default=HISTORY_CUTOFF)
    if target - most_recent > MAX_STALE_HISTORY:
        raise ValueError(f"Last certified result {most_recent} too old for {target}")
    return recent, {"recent_rows":len(recent),"last_history_day":str(most_recent),
                    "archive_latest_day":str(last_archive)}


def training_and_state(certified, recent, *, asof):
    """Replicate frozen V3 2026 fit (through 2025), with past-only form updates."""
    if not certified or certified[-1].day != HISTORY_CUTOFF:
        raise ValueError("Missing certified last day of historical cohort")
    for m in recent:
        if m.day <= HISTORY_CUTOFF or m.day >= asof:
            raise ValueError("Recent results overlap historical or target day")
    ordered = sorted([*certified, *recent],key=lambda m:(m.day,m.key))
    if len({m.key for m in ordered}) != len(ordered):
        raise ValueError("Duplicated historical match ID")
    state = FormState()
    training = []
    low = []
    latest_fit = None
    for day,group in groupby(ordered,key=lambda m:m.day):
        rows = list(group)
        if day >= asof:
            raise ValueError("Future match encountered while building historical features")
        for m in rows:
            f = state.features(m)
            if m.day <= TRAIN_CUTOFF:
                training.append((f["vector"], m.hg, m.ag, m.day))
                low.append((f["h"],f["a"],m.hg,m.ag))
                latest_fit = m.day
        state.add_day(rows)
    if len(training) < MIN_FIT_ROWS or latest_fit is None:
        raise ValueError("Insufficient certified V3 pre-2026 training")
    _validate_rows(training[-65000:], asof=HISTORIC_FIT_ASOF, feature_count=len(FEATURE_NAMES))
    models = fit_hist_v3(training, asof=HISTORIC_FIT_ASOF,feature_count=len(FEATURE_NAMES))
    if models is None or latest_fit != TRAIN_CUTOFF:
        raise ValueError("Could not recreate frozen 2026 Hybrid V3 model")
    rho = estimate_dc_rho(low[-9000:])
    return state, models, rho, latest_fit, {
        "certified_2024_2026":len(certified),
        "full_past_form_rows":len(ordered),
        "frozen_training_rows":len(training),
        "fit_cutoff":str(latest_fit),
        "frozen_dc_weight":DEFAULT_DC_WEIGHT,
        "rho":float(rho),
        "model_version":V3_VERSION,
    }


def safe_target_identity(fixture, opponent_state):
    """Downgrade conflicting *prospective* provider IDs to league-local identity.

    This is the same no-fuzzy, no-leakage fallback used for historically
    ambiguous source IDs, and never changes the historical fitted model.
    """
    names = opponent_state.provider_names
    updates = {}
    for side in ("home", "away"):
        val = getattr(fixture, side + "_id")
        if val is None:
            continue
        prior = names.get(("global-provider-id", val))
        if prior is not None and prior != canonical_name(getattr(fixture, side)):
            updates[side + "_id"] = None
    if fixture.home_id is not None and fixture.home_id == fixture.away_id:
        updates["home_id"] = None
        updates["away_id"] = None
    return replace(fixture, **updates) if updates else fixture, len(updates)


def forecast_day(*, now, source_rows, recent_rows, events):
    """Pure prediction function: no network, results or output writes."""
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    if not source_rows:
        raise ValueError("No certified ML history")
    state, models, rho, fit_day, info = training_and_state(source_rows, recent_rows, asof=now.date())
    fixtures = {}
    for row in events:
        event = extract_fixture(row,now=now)
        if event is None:
            continue
        fixture,kickoff = event
        if fixture.key in fixtures:
            raise ValueError("Duplicate current match event ID")
        fixtures[fixture.key] = (fixture,kickoff)
    records=[]
    name_conflicts_downgraded = 0
    for fixture,kickoff in sorted(fixtures.values(),key=lambda r:(r[1],r[0].key)):
        fixture, downgraded = safe_target_identity(fixture, state.opponent_state)
        name_conflicts_downgraded += downgraded
        f=state.features(fixture)
        p0=poisson_grid(f["h"],f["a"])
        dc=dixon_coles(f["h"],f["a"],rho)
        hist=hist_v3_grid(models,f["vector"],p0,form_samples=f["form_samples"],p11_factor=1.)
        if hist is None:
            raise ValueError("Frozen Hist V3 model unexpectedly unavailable")
        final=hybrid_v3_grid(hist,dc,dc_weight=DEFAULT_DC_WEIGHT)
        if final.shape != (11,11) or not np.isfinite(final).all() or abs(float(final.sum())-1)>1e-6:
            raise ValueError("Invalid Hybrid V3 prospective grid")
        records.append({
            "model":HYBRID_NAME,"id":fixture.key,"home":fixture.home,"away":fixture.away,
            "league":fixture.league, "kickoff_utc":kickoff.isoformat().replace("+00:00","Z"),
            "history_latest_day":str(state.last_ingested_day),
            "model_fit_latest_day":str(fit_day),
            "grid":final.tolist(),
        })
    info["future_club_ids_downgraded_to_local"] = name_conflicts_downgraded
    return records, info


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",required=True,type=Path)
    parser.add_argument("--max-requests",type=int,default=130)
    parser.add_argument("--recent-bsd-archive",type=Path,default=Path("bsd/all_matches_bsd.json"))
    parser.add_argument("--audit-root",type=Path,default=Path("ml_core/research"))
    parser.add_argument("--history-root",type=Path,default=Path("ml_core/research/encrypted_football"))
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    if not args.history_root.is_dir():
        raise RuntimeError("Research history checkout missing; cannot substitute other model")
    key=key_from_environment()
    certified_rows_raw=certified_rows(key, root=args.history_root,audit_root=args.audit_root)
    source_rows=safe_source_identities(certified_rows_raw)
    # Use exact loader from frozen benchmark; never infer unknown sport or scores.
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf8",suffix=".json",dir="/tmp",delete=True) as fd:
        json.dump(source_rows,fd,ensure_ascii=False)
        fd.flush()
        certified=load_matches(fd.name,HISTORY_CUTOFF)
    if len(certified)!=len(source_rows):
        raise RuntimeError("Historical ML baseline loader did not accept all rows")
    current=json.loads(args.recent_bsd_archive.read_text(encoding="utf8"))
    client=BSDClient(max_requests=args.max_requests)
    client.enable_free_sources=False
    recent, freshness=recent_verified_matches(current,client,target=now.date())
    future=client.list_events(now.date(),now.date(),max_pages=20,ttl=0)
    if not future.complete:
        raise RuntimeError("Today's fixture list is incomplete: refusing to publish incomplete Top5")
    verified_events,league_audit=resolve_league_labels(future.events,current,client)
    records,details=forecast_day(now=now,source_rows=certified,recent_rows=recent,events=verified_events)
    published=datetime.now(timezone.utc).replace(microsecond=0)
    # Recheck every timestamp after potentially slow model-fitting, and do not
    # use the earlier job-start clock to certify a late forecast.
    records=[r for r in records if parse_iso(r["kickoff_utc"])>published+MINIMUM_LEAD]
    output={
        "origin":"prospective_prematch","model":HYBRID_NAME,
        "generated_at":published.isoformat().replace("+00:00","Z"),
        "fixtures":records,
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    os.chmod(args.out.parent,0o700) if str(args.out.parent).startswith("/tmp/") else None
    with args.out.open("w",encoding="utf8") as f:
        os.chmod(args.out,0o600)
        json.dump(output,f,ensure_ascii=False,separators=(",",":"))
    print("HYBRID_V3_PROSPECTIVE",json.dumps({
        "date":now.date().isoformat(),"authentic_prematch":True,
        "fixture_count":len(future.events),"eligible_grid_count":len(records),
        "fixture_screening":fixture_eligibility_diagnostics(verified_events,now=published),
        "official_league_resolution":league_audit,
        "http_calls":client.requests_made,"history":freshness,
        "engine":details,"output":str(args.out),
        "post_match_outcomes":False,"changed_prod_pro_vip":False
    }),flush=True)


if __name__=="__main__":
    main()
