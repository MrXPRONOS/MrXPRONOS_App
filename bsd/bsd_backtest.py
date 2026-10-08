#!/usr/bin/env python3
"""Backtest chronologique expérimental du moteur BSD (sans API ni publication).

Attention : les données archivées peuvent être révisées a posteriori.
Les chiffres mesurent un test exploratoire et NON un résultat de paris réels.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime, timezone

from bsd_archive import MATCHES_FILE, _read_json
from bsd_predict import HistoryIndex, predict_fixture
from bsd_h2h import _valid_score, _utc


def evaluate(matches, *, year=2026, max_fixtures=250):
    index = HistoryIndex(matches)
    fixtures = []
    for item in matches:
        if not isinstance(item, dict) or item.get("status") != "finished":
            continue
        if _valid_score(item.get("home_score")) is None or _valid_score(item.get("away_score")) is None:
            continue
        try:
            kickoff = _utc(str(item.get("event_date") or ""))
        except (ValueError, TypeError):
            continue
        if kickoff.year == year:
            fixtures.append((kickoff, item))
    fixtures.sort(key=lambda row: (row[0], str(row[1].get("id"))))
    if len(fixtures) > max_fixtures:
        # Deterministic sample spread across season instead of only earliest games.
        step = len(fixtures) / max_fixtures
        fixtures = [fixtures[int(i * step)] for i in range(max_fixtures)]
    skipped = Counter()
    by_cat = Counter()
    won_by_cat = Counter()
    scored = []
    wins = 0
    for kickoff, original in fixtures:
        fixture = dict(original)
        fixture["status"] = "notstarted"
        prediction, reason = predict_fixture(fixture, index, clock=kickoff.replace(year=kickoff.year - 1))
        if prediction is None:
            skipped[reason] += 1
            continue
        hs = _valid_score(original["home_score"])
        aws = _valid_score(original["away_score"])
        choice = prediction["prediction"]["double_chance"]
        won = (hs >= aws if choice == "1X" else aws >= hs)
        wins += int(won)
        cat = prediction["category"]
        by_cat[cat] += 1
        won_by_cat[cat] += int(won)
        scored.append((prediction["prediction"]["confidence"] / 100.0, int(won)))
    total = len(scored)
    brier = sum((p - actual) ** 2 for p, actual in scored) / total if total else None
    return {
        "mode": "offline_exploratory_backtest",
        "year": year,
        "checked_fixtures": len(fixtures),
        "evaluated_predictions": total,
        "skipped": dict(skipped),
        "wins": wins,
        "hit_rate": round(wins / total, 4) if total else None,
        "brier_score": round(brier, 5) if brier is not None else None,
        "categories": {cat: {"selections": num, "wins": won_by_cat[cat],
                              "hit_rate": round(won_by_cat[cat] / num, 4)}
                       for cat, num in sorted(by_cat.items())},
        "warning": "Archive historique potentiellement révisée. Pas de validation prospective, pas de ROI sans cotes.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, choices=[2024, 2025, 2026], default=2026)
    parser.add_argument("--max-fixtures", type=int, default=250)
    opts = parser.parse_args()
    if not 1 <= opts.max_fixtures <= 5000:
        parser.error("max-fixtures doit etre 1-5000")
    matches = _read_json(MATCHES_FILE, None)
    if not isinstance(matches, list) or not matches:
        parser.error("Historique BSD absent")
    print("BSD_BACKTEST:", json.dumps(evaluate(matches, year=opts.year, max_fixtures=opts.max_fixtures), ensure_ascii=False))
