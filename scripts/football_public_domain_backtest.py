#!/usr/bin/env python3
"""Chronological public-domain backtest, independent of BSD and bookmakers.

Two fixed, uncalibrated baselines (rolling team Poisson vs rolling league
frequencies) are evaluated on exactly the same held-out matches. Data must
have been known on a strictly earlier UTC day. No training or publishing.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from math import log
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.football_history_shadow import canonical_team
from scripts.football_history_features import competition
from scripts.football_public_domain_prematch import historical_index, team_form
from scripts.football_prematch_probability_shadow import baseline


def clean_results(rows: list[dict]) -> list[dict]:
    unique = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("source") != "openfootball" or row.get("status") != "finished":
            continue
        try:
            league = competition(str(row["league"]))
            day = date.fromisoformat(row["match_date"])
            home, away = canonical_team(row["home_team"]), canonical_team(row["away_team"])
            h, a = row["home_score"], row["away_score"]
        except (KeyError, TypeError, ValueError):
            continue
        if not league or not home or not away or home == away:
            continue
        if type(h) is not int or type(a) is not int or not (0 <= h <= 30 and 0 <= a <= 30):
            continue
        key = (league, day, home, away)
        if key not in unique:
            unique[key] = {"league": league, "day": day, "home": home, "away": away, "h": h, "a": a}
        elif unique[key] is not None and (unique[key]["h"], unique[key]["a"]) != (h, a):
            unique[key] = None
    return sorted((r for r in unique.values() if r is not None), key=lambda x: (x["day"], x["league"], x["home"], x["away"]))


def league_prior(rows: list[dict], league: str, day: date, min_matches: int = 30) -> dict | None:
    prior = [r for r in rows if r["league"] == league and r["day"] < day]
    if len(prior) < min_matches:
        return None
    n = len(prior)
    # Laplace smoothing fixed ex ante, no parameter selection on holdout.
    h = (1+sum(x["h"] > x["a"] for x in prior)) / (n+3)
    d = (1+sum(x["h"] == x["a"] for x in prior)) / (n+3)
    a = (1+sum(x["h"] < x["a"] for x in prior)) / (n+3)
    b = (1+sum(x["h"] > 0 and x["a"] > 0 for x in prior)) / (n+2)
    o = (1+sum(x["h"]+x["a"] >= 3 for x in prior)) / (n+2)
    return {"home": h, "draw": d, "away": a, "btts_yes": b, "over_2_5": o}


def metric_values(probs: dict, result: dict) -> dict:
    actual = "home" if result["h"] > result["a"] else "away" if result["h"] < result["a"] else "draw"
    y_btts = int(result["h"] > 0 and result["a"] > 0)
    y_over = int(result["h"] + result["a"] >= 3)
    return {
        "1x2_brier": sum((probs[k] - int(actual == k))**2 for k in ("home","draw","away")),
        "1x2_logloss": -log(max(1e-9, min(1, probs[actual]))),
        "btts_brier": (probs["btts_yes"] - y_btts)**2,
        "over25_brier": (probs["over_2_5"] - y_over)**2,
    }


def evaluate(rows: list[dict], *, holdout_share: float = 0.3,
             min_games: int = 5) -> dict:
    if not (0.2 <= holdout_share <= 0.5):
        raise ValueError("holdout_share out of bounds")
    all_matches = clean_results(rows)
    days = sorted({r["day"] for r in all_matches})
    if len(days) < 20:
        return {"usable_matches": len(all_matches), "test_matches": 0,
                "reason": "not_enough_distinct_dates",
                "production_activation_allowed": False}
    pivot = days[int(len(days)*(1-holdout_share))]
    index, quality = historical_index(rows)
    test = [r for r in all_matches if r["day"] >= pivot]
    total_by_league = defaultdict(lambda: {"evaluated": 0, "skipped": Counter()})
    errors = defaultdict(list)
    for match in test:
        league = match["league"]
        prior = league_prior(all_matches, league, match["day"])
        left = team_form(index, league, match["home"], match["day"], min_games=min_games)
        right = team_form(index, league, match["away"], match["day"], min_games=min_games)
        if not prior or not left or not right:
            total_by_league[league]["skipped"]["insufficient_prior"] += 1
            continue
        metrics = {
            "home_goals_for": left["gf"], "home_goals_against": left["ga"],
            "away_goals_for": right["gf"], "away_goals_against": right["ga"],
        }
        candidate = baseline(metrics)["probabilities_uncalibrated"]
        for metric, value in metric_values(candidate, match).items():
            errors[("model", metric)].append(value)
        for metric, value in metric_values(prior, match).items():
            errors[("league_prior", metric)].append(value)
        total_by_league[league]["evaluated"] += 1
    n = len(errors[("model", "1x2_brier")])
    values = {}
    for market in ("1x2_brier","1x2_logloss","btts_brier","over25_brier"):
        if n:
            model = sum(errors[("model", market)]) / n
            naive = sum(errors[("league_prior", market)]) / n
            values[market] = {
                "team_model": round(model, 6),
                "league_prior": round(naive, 6),
                "improvement_positive": round(naive-model, 6),
                "outperforms_prior_on_holdout": model < naive,
            }
        else:
            values[market] = None
    return {
        "source": "openfootball_public_domain_only",
        "source_confirmation": "single_unverified_source",
        "history_unique_matches": len(all_matches),
        "holdout_from": pivot.isoformat(),
        "holdout_until": days[-1].isoformat(),
        "holdout_games": len(test),
        "evaluable_games": n,
        "insufficient_evaluation_sample": n < 200,
        "test_match_coverage_pct": round(100*n/len(test), 2) if test else 0,
        "by_competition": {league: {"evaluated": val["evaluated"], "skipped": dict(val["skipped"])}
                           for league, val in sorted(total_by_league.items())},
        "scoring_metrics": values,
        "chronological_rule": "all source match outcomes strictly before each evaluation day",
        "compared_to_bsd_v2": False,
        "calibration_verified": False,
        "production_activation_allowed": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--history-jsonl", required=True)
    p.add_argument("--report", required=True)
    args = p.parse_args()
    history = []
    for line in Path(args.history_jsonl).read_text(encoding="utf-8").splitlines():
        if line.strip():
            history.append(json.loads(line))
    summary = evaluate(history)
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
