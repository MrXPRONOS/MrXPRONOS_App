#!/usr/bin/env python3
"""Experimental prematch probability baseline: NEVER publish betting picks.

Consumes only verified, point-in-time, per-fixture routed goal-rate evidence.
Runs optional chronological diagnostic on cross-checked historical scores.
Probability formulas are uncalibrated and MUST NOT be used as VIP signals.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from math import exp, factorial, log
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.football_history_features import form, eligible_history


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def pmf(lmbd: float, k: int) -> float:
    return exp(-lmbd) * lmbd**k / factorial(k)


def baseline(m: dict) -> dict:
    """Fixed, UNTUNED Poisson baseline, deliberately no bookmaker prices."""
    home_rate = .5 * (m["home_goals_for"] + m["away_goals_against"])
    away_rate = .5 * (m["away_goals_for"] + m["home_goals_against"])
    lh = clamp(home_rate, .2, 3.5)
    la = clamp(away_rate, .2, 3.5)
    hg, ag = [pmf(lh, i) for i in range(13)], [pmf(la, i) for i in range(13)]
    home = sum(hg[i] * ag[j] for i in range(13) for j in range(i))
    draw = sum(hg[i] * ag[i] for i in range(13))
    away = sum(hg[i] * ag[j] for j in range(13) for i in range(j))
    z = home + draw + away
    if z <= 0:
        raise ValueError("Invalid Poisson normalization")
    home, draw, away = home/z, draw/z, away/z
    total = lh + la
    under25 = sum(pmf(total, i) for i in range(3))
    btts = (1 - exp(-lh)) * (1 - exp(-la))
    return {
        "expected_goals": {"home": round(lh, 4), "away": round(la, 4)},
        "probabilities_uncalibrated": {
            "home": round(home, 6), "draw": round(draw, 6), "away": round(away, 6),
            "1x": round(home+draw, 6), "x2": round(draw+away, 6), "12": round(home+away, 6),
            "over_2_5": round(1-under25, 6), "under_2_5": round(under25, 6),
            "btts_yes": round(btts, 6), "btts_no": round(1-btts, 6),
        },
        "calibration_verified": False,
        "betting_signal": False,
    }


def predict_research(routed: list[dict]) -> tuple[list[dict], dict]:
    outcome = []
    missed = {}
    for match in routed:
        family = (match.get("families") or {}).get("goals") or {}
        if family.get("status") != "ready":
            reason = family.get("reason", "goals_not_available")
            missed[reason] = missed.get(reason, 0) + 1
            continue
        try:
            report = baseline(family["metrics"])
        except (KeyError, TypeError, ValueError, OverflowError):
            missed["invalid_goal_evidence"] = missed.get("invalid_goal_evidence", 0) + 1
            continue
        outcome.append({
            "fixture_key": match.get("fixture_key"),
            "statistics_provider": family["provider"],
            "provider_fixture_id": family["provider_fixture_id"],
            "sample_matches": family["samples"],
            "research_model": "simple_poisson_untrained_v1",
            "not_validated_for_publication": True,
            **report,
        })
    return outcome, {
        "daily_fixtures": len(routed),
        "probability_profiles_generated": len(outcome),
        "unanalysable_reasons": missed,
        "production_outputs_written": False,
        "telegram_posts": 0,
        "ready_for_betting": False,
    }


def chronological_backtest(history: list[dict]) -> dict:
    """No lookahead: each historical game uses earlier DAYS only."""
    scored = []
    for row in history:
        if not eligible_history(row):
            continue
        try:
            today = date.fromisoformat(str(row["date"]))
        except (TypeError, ValueError):
            continue
        league = row["competition"]
        left = form(row["home_team"], league, today, history)
        right = form(row["away_team"], league, today, history)
        if not left or not right:
            continue
        m = {
            "home_goals_for": left["goals_for_per_match"],
            "home_goals_against": left["goals_against_per_match"],
            "away_goals_for": right["goals_for_per_match"],
            "away_goals_against": right["goals_against_per_match"],
        }
        p = baseline(m)["probabilities_uncalibrated"]
        h, a = row["home_score"], row["away_score"]
        actual = "home" if h > a else "away" if h < a else "draw"
        y_btts = int(h > 0 and a > 0)
        y_over = int(h+a >= 3)
        scored.append((
            -log(max(1e-9, p[actual])),
            (p["home"]-int(actual == "home"))**2 +
            (p["draw"]-int(actual == "draw"))**2 +
            (p["away"]-int(actual == "away"))**2,
            (p["btts_yes"]-y_btts)**2,
            (p["over_2_5"]-y_over)**2,
        ))
    n = len(scored)
    return {
        "chronologically_evaluable_games": n,
        "min_sample_satisfied": n >= 200,
        "holdout_benchmark_ready": False,  # Still needs BSD-only comparison and calibration.
        "one_x_two_logloss": round(sum(x[0] for x in scored)/n, 5) if n else None,
        "one_x_two_brier": round(sum(x[1] for x in scored)/n, 5) if n else None,
        "btts_brier": round(sum(x[2] for x in scored)/n, 5) if n else None,
        "over_2_5_brier": round(sum(x[3] for x in scored)/n, 5) if n else None,
        "leakage_rule": "strictly earlier historical UTC dates",
        "production_activation_allowed": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--routed", required=True, help="Research-only routing report")
    p.add_argument("--out", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--history", help="Optional verified historical input for chronological diagnostics")
    args = p.parse_args()
    routed = json.loads(Path(args.routed).read_text(encoding="utf-8"))
    if not isinstance(routed, list):
        p.error("--routed must be a list")
    prediction_rows, report = predict_research(routed)
    if args.history:
        history = json.loads(Path(args.history).read_text(encoding="utf-8"))
        if not isinstance(history, list):
            p.error("--history must be a list")
        report["chronological_diagnostics"] = chronological_backtest(history)
    for path, rows in ((args.out, prediction_rows), (args.report, report)):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
