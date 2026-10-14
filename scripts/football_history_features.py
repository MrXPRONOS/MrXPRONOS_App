#!/usr/bin/env python3
"""Research-only chronological form features from independently confirmed history.

No market selection, no odds, no prediction publication, and no BSD writes.
All historical observations must predate the target fixture day (UTC).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
import json
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.football_history_shadow import canonical_team, normalized

LEAGUE_ALIASES = {
    "english premier league": "premier league",
    "premier league": "premier league",
    "spanish primera division": "la liga",
    "primera division": "la liga",
    "la liga": "la liga",
    "german bundesliga": "bundesliga",
    "bundesliga": "bundesliga",
    "french ligue 1": "ligue 1",
    "ligue 1": "ligue 1",
    "serie a": "serie a",
    "bl1": "bundesliga",
    "en 1": "premier league",
    "de 1": "bundesliga",
    "es 1": "la liga",
    "it 1": "serie a",
    "fr 1": "ligue 1",
}


def competition(value: str) -> str:
    key = normalized(value)
    return LEAGUE_ALIASES.get(key, key)


def eligible_history(row: dict) -> bool:
    return (
        row.get("status") == "multi_source_agreement"
        and row.get("verified_by_sources", 0) >= 2
        and isinstance(row.get("home_score"), int)
        and isinstance(row.get("away_score"), int)
        and bool(row.get("date"))
        and bool(row.get("competition"))
        and canonical_team(str(row.get("home_team") or "")) != canonical_team(str(row.get("away_team") or ""))
    )


def form(team: str, league: str, before: date, history: list[dict], *, min_games: int = 5, last: int = 12) -> dict | None:
    key = canonical_team(team)
    league_key = competition(league)
    if not key or not league_key:
        return None
    prior = []
    for row in history:
        if not eligible_history(row) or competition(str(row["competition"])) != league_key:
            continue
        try:
            matchday = date.fromisoformat(str(row["date"]))
        except ValueError:
            continue
        if matchday >= before:
            continue  # strict, protects against same-day outcome leakage
        home, away = canonical_team(str(row["home_team"])), canonical_team(str(row["away_team"]))
        if key == home:
            gf, ga, venue = row["home_score"], row["away_score"], "home"
        elif key == away:
            gf, ga, venue = row["away_score"], row["home_score"], "away"
        else:
            continue
        extra = (row.get("source_statistics") or {}).get("football_data") or {}
        prior.append((matchday, gf, ga, venue, extra if isinstance(extra, dict) else {}))
    prior.sort(key=lambda m: m[0], reverse=True)
    prior = prior[:last]
    if len(prior) < min_games:
        return None
    n = len(prior)
    extra_features = {}
    for label, home_key, away_key in (
        ("corners", "corners_home", "corners_away"),
        ("shots", "shots_home", "shots_away"),
        ("shots_on_target", "shots_on_target_home", "shots_on_target_away"),
        ("yellow_cards", "yellow_cards_home", "yellow_cards_away"),
        ("red_cards", "red_cards_home", "red_cards_away"),
    ):
        samples = []
        for row in prior:
            stats = row[4]
            if type(stats.get(home_key)) is not int or type(stats.get(away_key)) is not int:
                continue
            if not 0 <= stats[home_key] <= 100 or not 0 <= stats[away_key] <= 100:
                continue
            this, opposing = ((stats[home_key], stats[away_key]) if row[3] == "home"
                              else (stats[away_key], stats[home_key]))
            samples.append((this, opposing))
        if len(samples) >= min_games:
            extra_features[label] = {
                "for_per_match": round(sum(a for a, _ in samples) / len(samples), 4),
                "against_per_match": round(sum(b for _, b in samples) / len(samples), 4),
                "sample_matches": len(samples),
                "source": "football_data",
                "independently_verified_statistic": False,
                "historical_final_scores_crosschecked": True,
            }
    return {
        "supplemental_statistics": extra_features,
        "sample_matches": n,
        "goals_for_per_match": round(sum(m[1] for m in prior) / n, 4),
        "goals_against_per_match": round(sum(m[2] for m in prior) / n, 4),
        "points_per_match": round(sum(3 if m[1] > m[2] else 1 if m[1] == m[2] else 0 for m in prior) / n, 4),
        "both_teams_score_rate": round(sum(m[1] > 0 and m[2] > 0 for m in prior) / n, 4),
        "over_2_5_rate": round(sum(m[1] + m[2] >= 3 for m in prior) / n, 4),
        "home_games": sum(m[3] == "home" for m in prior),
        "away_games": sum(m[3] == "away" for m in prior),
        "last_history_date": prior[0][0].isoformat(),
    }


def features(fixtures: list[dict], history: list[dict], *, min_games: int = 5) -> tuple[list[dict], dict]:
    result = []
    coverage = defaultdict(int)
    for fixture in fixtures:
        if (fixture.get("ambiguous_match") or fixture.get("scores_conflict") or fixture.get("league_conflict")):
            coverage["unsafe_fixture_identity"] += 1
            continue
        if fixture.get("status", "prematch") != "prematch":
            coverage["not_prematch"] += 1
            continue
        try:
            dt = datetime.fromisoformat(str(fixture["kickoff_utc"]).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError("kickoff timezone unavailable")
            target = dt.astimezone(timezone.utc).date()
        except (KeyError, ValueError, TypeError):
            coverage["missing_kickoff"] += 1
            continue
        # Fixture may contain different labels; never assume ambiguous competitions.
        raw_leagues = list(fixture.get("league_labels") or [])
        buckets = sorted({competition(str(x)) for x in raw_leagues if normalized(str(x))})
        if len(buckets) != 1:
            coverage["ambiguous_or_missing_league"] += 1
            continue
        league = buckets[0]
        home = form(fixture.get("home_team", ""), league, target, history, min_games=min_games)
        away = form(fixture.get("away_team", ""), league, target, history, min_games=min_games)
        if home is None or away is None:
            coverage["insufficient_verified_history"] += 1
            continue
        # Only descriptive form features: these are not calibrated probabilities.
        result.append({
            "fixture": {
                "home_team": fixture["home_team"], "away_team": fixture["away_team"],
                "kickoff_utc": fixture["kickoff_utc"], "competition": league,
            },
            "home_form": home, "away_form": away,
            "source_history_filter": ">=2 independent agreeing providers; prior UTC dates only",
            "calibrated_probability": None,
            "for_production": False,
        })
        coverage["complete_features"] += 1
    report = {
        "fixtures_input": len(fixtures),
        "features_complete": len(result),
        "coverage_reasons": dict(sorted(coverage.items())),
        "chronological_no_same_day_data": True,
        "production_model_modified": False,
        "published_predictions": 0,
    }
    return result, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, help="Canonical research-only JSON output")
    parser.add_argument("--fixtures", required=True, help="Daily research-only index JSON")
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--min-games", type=int, default=5)
    a = parser.parse_args()
    if not 5 <= a.min_games <= 30:
        parser.error("--min-games must be between 5 and 30")
    history = json.loads(Path(a.history).read_text(encoding="utf-8"))
    fixtures = json.loads(Path(a.fixtures).read_text(encoding="utf-8"))
    if not isinstance(history, list) or not isinstance(fixtures, list):
        parser.error("Expected JSON lists")
    result, report = features(fixtures, history, min_games=a.min_games)
    for path, rows in ((a.out, result), (a.report, report)):
        item = Path(path)
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
