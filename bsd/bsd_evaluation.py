"""Offline diagnostic for a *single selected* market per completed fixture.

Comparisons are on the identical selected sample. None measure monetary ROI.
"""
from __future__ import annotations

from collections import defaultdict
from math import sqrt


def _wilson(successes, n, z=1.96):
    if n <= 0:
        return None
    p = successes / n
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n)) / denominator
    half = z * sqrt((p*(1-p) + z*z/(4*n))/n) / denominator
    return [round(max(0, center-half), 4), round(min(1, center+half), 4)]


def _summary(rows):
    n = len(rows)
    if n == 0:
        return {"selections": 0}
    wins = sum(int(row["won"]) for row in rows)
    average = sum(row["confidence"] for row in rows)/n
    brier = sum((row["confidence"] - int(row["won"]))**2 for row in rows)/n
    return {
        "selections": n,
        "wins": wins,
        "hit_rate": round(wins/n, 4),
        "wilson_95_interval": _wilson(wins, n),
        "average_predicted_probability": round(average, 4),
        "calibration_gap_percentage_points": round(100*(wins/n-average), 2),
        "brier_score": round(brier, 5),
    }


def audit_selection(rows):
    """Rows contain only pre-game forecasts and *later* verified final scores."""
    rows = list(rows)
    groupings = {}
    dimensions = {
        "by_market": lambda r: r["market_key"],
        "by_family": lambda r: r["market_family"],
        "by_category": lambda r: r["category"],
        "by_probability_band": lambda r: ("%d-%d%%" % (
            min(90, int(r["confidence"]*20)*5),
            min(100, min(90, int(r["confidence"]*20)*5)+5)
        )),
    }
    for label, classify in dimensions.items():
        groups = defaultdict(list)
        for row in rows:
            groups[classify(row)].append(row)
        groupings[label] = {str(k): _summary(v) for k,v in sorted(groups.items())}
    def fixed_baseline(row, key):
        h, a = row["home_score"], row["away_score"]
        if key == "always_1X":
            return int(h >= a)
        if key == "always_X2":
            return int(a >= h)
        if key == "always_12":
            return int(h != a)
        if key == "always_over_1_5":
            return int(h+a >= 2)
        if key == "always_under_3_5":
            return int(h+a <= 3)
        raise ValueError(key)
    baselines = {}
    for key in ("always_1X", "always_X2", "always_12",
                "always_over_1_5", "always_under_3_5"):
        successes = sum(fixed_baseline(r, key) for r in rows)
        n = len(rows)
        baselines[key] = {
            "same_fixtures": n,
            "wins": successes,
            "hit_rate": round(successes/n, 4) if n else None,
            "wilson_95_interval": _wilson(successes, n),
        }
    return {
        "selected_summary": _summary(rows),
        **groupings,
        "simple_baselines_same_fixtures": baselines,
        "caution": "Comparaisons descriptives, les scores sont revisions potentielles et aucune cote bookmaker n'est integree.",
    }
