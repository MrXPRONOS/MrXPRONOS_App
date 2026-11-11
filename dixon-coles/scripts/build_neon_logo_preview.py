"""Create a clearly labelled visual-only neon demo using authentic ESPN crests.

Do not invent club identities or substitute letters. Scores are fictional
layout samples only and MUST be labelled DEMONSTRATION before any sharing.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from dcscore.daily_espn import ESPNProvider, ALLOWED
from dcscore.logo_policy import valid_logo_url

DEMO_SCORES = ("1-2", "2-1", "0-1", "2-0", "5-0",
               "2-0", "2-1", "1-0", "2-1", "1-1")


def _team_crest(team: dict) -> str | None:
    url = team.get("logo")
    if not url:
        for entry in team.get("logos") or ():
            if isinstance(entry, dict) and entry.get("href"):
                url = entry["href"]
                break
    return url if valid_logo_url(url) else None


def parse_preview_event(event: Any) -> dict | None:
    """Only real two-team fixtures with both authenticated crest URLs."""
    try:
        if not isinstance(event, dict):
            return None
        eid = str(event["id"])
        if not eid.isdigit():
            return None
        game = event["competitions"][0]
        teams = game["competitors"]
        if len(teams) != 2:
            return None
        home = next(c["team"] for c in teams if c.get("homeAway") == "home")
        away = next(c["team"] for c in teams if c.get("homeAway") == "away")
        home_name = str(home["displayName"]).strip()
        away_name = str(away["displayName"]).strip()
        if not home_name or not away_name or home_name == away_name:
            return None
        hcrest = _team_crest(home)
        acrest = _team_crest(away)
        if not hcrest or not acrest:
            return None
        return {"id": eid,
                "headline": f"{home_name} - {away_name}",
                "home_logo_url": hcrest,
                "away_logo_url": acrest}
    except (KeyError, TypeError, ValueError, IndexError, StopIteration, AttributeError):
        return None


def make_crest_demo(target: date, *, provider=None) -> dict:
    provider = provider or ESPNProvider()
    seen = set()
    fixtures = []
    # Real matches from a narrowly bounded calendar window; only scores are demo.
    for day in (target, target - timedelta(days=1), target + timedelta(days=1)):
        for league in ALLOWED:
            try:
                events = provider._fetch(league, day.strftime("%Y%m%d"))
            except Exception as exc:
                print("DEMO_CREST_SOURCE_UNAVAILABLE", league, day, type(exc).__name__, flush=True)
                continue
            for event in events:
                row = parse_preview_event(event)
                if not row or (league, row["id"]) in seen:
                    continue
                seen.add((league, row["id"]))
                fixtures.append(row)
            if len(fixtures) >= 10:
                break
        if len(fixtures) >= 10:
            break
    if len(fixtures) < 10:
        raise ValueError(f"Vrais écussons insuffisants : {len(fixtures)}/10. Aucun logo fictif autorisé.")
    clips = []
    for i, row in enumerate(fixtures[:10]):
        clips.append({
            "headline": row["headline"],
            "display_score": DEMO_SCORES[i],  # DISPLAY ONLY / NOT A PREDICTION
            "home_logo_url": row["home_logo_url"],
            "away_logo_url": row["away_logo_url"],
        })
    return {"date_local_africa_lome": target.isoformat(),
            "clips": clips, "demo_only": True,
            "disclaimer": "DEMONSTRATION: FICTITIOUS SCORES, REAL TEAMS AND CRESTS"}
