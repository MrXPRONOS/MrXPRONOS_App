#!/usr/bin/env python3
"""Vérification réseau réelle ActuFoot. Aucune écriture D1 ni message Telegram."""
from __future__ import annotations

import sys
from datetime import datetime, time, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.actu_foot_independent import (
    enrich_espn_fixtures, selected_fixtures,
)
from scripts.football_match_lifecycle import fetch_espn_day


def main():
    # Un unique appel scoreboard de la journée, compatible avec notre budget.
    session = requests.Session()
    today = datetime.now(timezone.utc).date()
    events = fetch_espn_day(session, today, force=True)
    if not events:
        raise RuntimeError("ACTUFOOT_SMOKE_ESPN_UNAVAILABLE_OR_EMPTY")
    enriched = enrich_espn_fixtures(events)
    ranked = [x for x in enriched if x.get("home_team") and x.get("away_team")]
    if not ranked:
        raise RuntimeError("ACTUFOOT_SMOKE_INVALID_ESPN_FIXTURES")
    from scripts import football_match_lifecycle as espn
    stamp = today.strftime("%Y%m%d")
    cached = espn._ESPN_CACHE.get("scoreboard:" + stamp)
    payload = cached[1] if cached else {}
    first = events[0]
    first_raw = first.get("raw") or {}
    first_comp = (first_raw.get("competitions") or [{}])[0]
    print("ACTUFOOT_SMOKE_SCOREBOARD_KEYS",list(payload.keys()))
    print("ACTUFOOT_SMOKE_LEAGUES_SUMMARY", str(payload.get("leagues") or "")[:1000])
    print("ACTUFOOT_SMOKE_SAMPLE_KEYS",list(first_raw.keys()),list(first_comp.keys()))
    print("ACTUFOOT_SMOKE_SAMPLE_STAGE", str(first_comp.get("altGameNote") or first_comp.get("note") or first_raw.get("stage") or "")[:90])
    print("ACTUFOOT_SMOKE_ESPN_FIXTURES", len(events))
    print("ACTUFOOT_SMOKE_LEAGUE_METADATA",
          sum(bool(e.get("league_name") and e["league_name"] not in ("Football","Soccer"))
              for e in enriched))
    print("ACTUFOOT_SMOKE_STAGES",
          sum(bool(e.get("round_name") or e.get("stage")) for e in enriched))
    # Simule le créneau matinal du jour, sans réservations ni Telegram.
    morning = datetime.combine(today, time(7, 0), tzinfo=timezone.utc)
    publication, tracked = selected_fixtures(events, morning)
    print("ACTUFOOT_SMOKE_PROGRAMME",
          bool(publication), "tracked", len(tracked))
    print("ACTUFOOT_SMOKE_TOP4", [(e["home"],e["away"],e["league"]) for e in tracked])
    if publication:
        if not tracked:
            raise RuntimeError("ACTUFOOT_SMOKE_PROGRAMME_WITHOUT_TRACKABLE_FIXTURES")
        # Test du moteur d'images employé réellement en production.
        from football_cards import render_card
        with TemporaryDirectory(prefix="actufoot-smoke-") as temp:
            target = Path(temp) / "programme.png"
            render_card("programme", publication.card, target)
            with Image.open(target) as visual:
                visual.verify()
            print("ACTUFOOT_SMOKE_PROGRAMME_RENDERED", target.stat().st_size)
    else:
        print("ACTUFOOT_SMOKE_NO_ELIGIBLE_UPCOMING_PRIORITY_FIXTURES")
    # Contrôle réel du cycle LIVE sur une rencontre effectivement démarrée.
    # Aucun envoi Telegram, aucune ligne D1 ni récupération multi-fournisseur.
    from scripts.actu_foot_independent import live_signals, event_priority, normalize_espn_summary
    from scripts.football_match_lifecycle import (
        fetch_espn_summary, parse_espn_summary_match,
    )
    started = sorted(
        [e for e in enriched if str(e.get("state") or "") in ("in", "post")],
        key=event_priority, reverse=True,
    )
    if not started:
        print("ACTUFOOT_SMOKE_NO_LIVE_OR_FINISHED_MATCH_ON_DATE")
        return
    match = started[0]
    summary = fetch_espn_summary(session, str(match["id"]), force=True)
    if not summary:
        raise RuntimeError("ACTUFOOT_SMOKE_LIVE_SUMMARY_UNAVAILABLE")
    parsed = parse_espn_summary_match(summary)
    if not parsed or str(parsed.get("id")) != str(match["id"]):
        raise RuntimeError("ACTUFOOT_SMOKE_LIVE_SUMMARY_ID_MISMATCH")
    plan_row = {
        "id": str(match["id"]),
        "home": match["home_team"], "away": match["away_team"],
        "league": match.get("league_name") or "",
        "event_date": match.get("event_date"),
        "home_logo": match.get("home_logo") or "",
        "away_logo": match.get("away_logo") or "",
        "rank": 1,
    }
    if parsed.get("home_team") != plan_row["home"] or parsed.get("away_team") != plan_row["away"]:
        raise RuntimeError("ACTUFOOT_SMOKE_LIVE_SUMMARY_TEAM_MISMATCH")
    hdr = summary.get("header") if isinstance(summary.get("header"),dict) else {}
    comp = (hdr.get("competitions") or [{}])[0]
    print("ACTUFOOT_SMOKE_LIVE_SUMMARY_KEYS",list(summary.keys()))
    print("ACTUFOOT_SMOKE_LIVE_DETAILS_COUNT",len(summary.get("details") or []))
    print("ACTUFOOT_SMOKE_LIVE_HEADER_COMP_KEYS",list(comp.keys()))
    print("ACTUFOOT_SMOKE_LIVE_HEADER_DETAILS_COUNT",len(comp.get("details") or []))
    print("ACTUFOOT_SMOKE_LIVE_HEADER_FIRST_DETAIL",str((comp.get("details") or [{}])[0])[:600])
    print("ACTUFOOT_SMOKE_LIVE_SCORING_PLAYS_COUNT",len(summary.get("scoringPlays") or []))
    print("ACTUFOOT_SMOKE_LIVE_FIRST_DETAIL",str((summary.get("details") or [{}])[0])[:800])
    summary = normalize_espn_summary(summary)
    signals = live_signals(plan_row, parsed, summary, datetime.now(timezone.utc))
    print("ACTUFOOT_SMOKE_LIVE_MATCH", match["home_team"],match["away_team"],
          "status", parsed["state"], "score",
          parsed.get("home_score"), parsed.get("away_score"))
    print("ACTUFOOT_SMOKE_LIVE_EVENTS",
          [signal.get("kind") for signal in signals][:20])
    goals = [signal for signal in signals if signal.get("kind") == "goal"]
    if goals:
        from scripts import football_channel as channel
        from football_cards import render_card
        publication = channel.lifecycle_publication(goals[0])
        if publication is None or not publication.card:
            raise RuntimeError("ACTUFOOT_SMOKE_LIVE_GOAL_PUBLICATION_INVALID")
        with TemporaryDirectory(prefix="actufoot-goal-smoke-") as temp:
            target = Path(temp) / "goal.png"
            render_card(publication.category, publication.card, target)
            with Image.open(target) as visual:
                visual.verify()
            print("ACTUFOOT_SMOKE_GOAL_RENDERED",target.stat().st_size)




if __name__ == "__main__":
    main()
