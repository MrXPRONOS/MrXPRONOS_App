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
    print("ACTUFOOT_SMOKE_TOP4",[(e["home"],e["away"],e["league"]) for e in tracked] if "tracked" in locals() else [])
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


if __name__ == "__main__":
    main()
