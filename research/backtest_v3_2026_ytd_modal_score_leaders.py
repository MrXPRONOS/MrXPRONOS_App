#!/usr/bin/env python3
"""2026 YTD daily *best fixture per genuine modal score* Hybrid V3 study.

For each calendar day, group fixtures by their actual ORIGINAL modal V3
score, then pick the highest-probability match from each score group.
Scores the model never predicts as its top score are not forced. One match
cannot represent more than one score group on the same day.
Only then compare each selected probability to the actual settled score.

No modification to production or the encrypted historical corpus. No ROI.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

START = date(2026, 1, 1)
END = date(2026, 11, 3)
HISTORICAL_CUTOFF = date(2026, 10, 24)
MODEL = "machine_learning_v3_hybrid"
SCORES = [f"{h}:{a}" for h in range(11) for a in range(11)]
CSV_FIELDS = (
    "day", "score", "match_id", "league", "home", "away",
    "probability", "modal_score", "actual_score", "hit",
    "history_latest_day", "model_fit_latest_day",
)


def percent(num, den):
    return round(num * 100.0 / den, 4) if den else None


def summarize(rows, *, count_all_matches):
    """Scores are separate daily competitions, not a global Top5."""
    if not rows:
        raise ValueError("Cannot report a backtest without settled selections")
    per_score = defaultdict(list)
    per_day = defaultdict(list)
    unique = set()
    for row in rows:
        d = date.fromisoformat(row["day"])
        if not START <= d <= END:
            raise ValueError("Selection from outside 2026 year-to-date interval")
        if row["score"] not in SCORES:
            raise ValueError("Out-of-range exact score")
        if row["score"] != row["modal_score"]:
            raise ValueError("Research must only select genuine first-ranked V3 scores")
        if row["hit"] != int(row["score"] == row["actual_score"]):
            raise ValueError("Inconsistent selected-score settlement")
        if (not 0 < row["probability"] <= 1 or
                date.fromisoformat(row["history_latest_day"]) >= d or
                date.fromisoformat(row["model_fit_latest_day"]) >= d):
            raise ValueError("Invalid probability or future-data leakage")
        k = row["day"], row["score"]
        if k in unique:
            raise ValueError("More than one selected fixture per day / exact score")
        unique.add(k)
        per_score[row["score"]].append(row)
        per_day[row["day"]].append(row)
    expected_days = [(START + timedelta(days=x)).isoformat() for x in range((END-START).days+1)]
    if set(per_day) != set(expected_days):
        raise ValueError("Missing an authenticated 2026 UTC day")
    for day, picks in per_day.items():
        if len({r["match_id"] for r in picks}) != len(picks):
            raise ValueError("Same fixture reused for two distinct score predictions")
    # Theoretical 11x11 scores are included in the ranking as 0-selection
    # categories when they were NEVER the leading forecast on any match.
    summary = {}
    for score in SCORES:
        group = per_score[score]
        hits = sum(int(r["hit"]) for r in group)
        probabilities = [r["probability"] for r in group]
        expected_hits = sum(probabilities)
        summary[score] = {
            "days_selected": len(group),
            "days_missing_or_zero_probability": len(expected_days) - len(group),
            "hits": hits,
            "hit_rate_percent": percent(hits, len(group)),
            "average_model_probability_percent": percent(expected_hits, len(group)),
            "expected_hits_from_model": round(expected_hits, 5),
            "hit_minus_expected": round(hits-expected_hits, 5),
            "times_this_score_was_also_modal": sum(r["modal_score"] == score for r in group),
        }
    daily = {}
    for day in expected_days:
        group = per_day[day]
        daily[day] = {
            "scores_selected": len(group),
            "hits": sum(int(r["hit"]) for r in group),
            "distinct_matches_selected": len({r["match_id"] for r in group}),
        }
    ordered = sorted(SCORES, key=lambda score: (
        -summary[score]["hits"],
        -summary[score]["hit_rate_percent"] if summary[score]["hit_rate_percent"] is not None else 0,
        score))
    all_hits = sum(x["hits"] for x in summary.values())
    # Keep month-by-month comparisons without claiming any betting ROI.
    monthly = {}
    for month in sorted({d[:7] for d in expected_days}):
        dates = [d for d in expected_days if d.startswith(month)]
        picks = [r for d in dates for r in per_day[d]]
        wins = sum(int(r["hit"]) for r in picks)
        monthly[month] = {
            "days": len(dates),
            "selections": len(picks),
            "hits": wins,
            "hit_rate_percent": percent(wins, len(picks)),
            "days_with_at_least_one_hit": sum(daily[d]["hits"] > 0 for d in dates),
            "days_without_hit": sum(daily[d]["hits"] == 0 for d in dates),
            "distinct_modal_score_types": len({r["score"] for r in picks}),
        }
    winning_days = sum(x["hits"] > 0 for x in daily.values())
    return {
        "version": "v3_2026_ytd_modal_top_per_exact_score_v1",
        "model": MODEL,
        "evaluation_start": START.isoformat(),
        "evaluation_end": END.isoformat(),
        "selection_rule": "for_each_day_and_genuinely_modal_v3_score_select_highest_probability_match_in_that_score_group",
        "score_domain": "0:0_through_10:10_possible_but_only_observed_modal_scores_selected",
        "one_match_may_be_selected_for_multiple_scores": False,
        "scores_actually_predicted_as_modal_in_month": sum(bool(per_score[k]) for k in SCORES),
        "score_1_1_included_in_research": True,
        "no_production_policy_changed": True,
        "verified_settled_football_matches_evaluated": count_all_matches,
        "days_with_completed_history": len(expected_days),
        "score_categories_theoretical": len(SCORES),
        "score_categories": sum(bool(per_score[k]) for k in SCORES),
        "total_selections_across_independent_scores": len(rows),
        "total_hits_across_independent_scores": all_hits,
        "overall_hits_over_selections_percent": percent(all_hits, len(rows)),
        "not_a_real_betting_roi": True,
        "no_verified_bookmaker_score_odds": True,
        "by_score": summary,
        "scores_ranked_by_hits": ordered,
        "by_month": monthly,
        "days_with_at_least_one_hit": winning_days,
        "days_without_hit": len(expected_days)-winning_days,
        "by_day": daily,
    }


def prepare_history(site_root, model_root):
    from single_ml_v2_git import key_from_environment, seal, open_sealed
    from single_ml_v2_multisource import certified_rows, check_ml_loader
    from single_ml_v2 import load_matches
    from single_ml_v2_data import day_snapshot
    from sportdata_api import fetch_games
    from run_exact_scores_v3_daily import historical_daily_rows, DAILY_HISTORY_SUBDIR

    key = key_from_environment()
    verified = certified_rows(key)
    history = check_ml_loader(verified)
    print("YTD_2026_SCORE_STUDY_ARCHIVE", len(history), flush=True)
    # Oct 25 through Nov 3 are authenticated daily snapshots from main.
    # If a day is missing it must be certified from SportData; failure stops
    # the study instead of using fabricated matches or partial days.
    extra, counts = historical_daily_rows(
        site_root / DAILY_HISTORY_SUBDIR, END,
        fetcher=fetch_games, normalizer=day_snapshot,
        sealer=seal, opener=open_sealed, key=key,
    )
    if not extra or len(counts) != (END - HISTORICAL_CUTOFF).days:
        raise RuntimeError("October 25-Nov 3 authenticated daily evidence missing")
    with tempfile.TemporaryDirectory(prefix="mrx-v3-2026-certified-") as td:
        source = Path(td) / "authenticated_completed.json"
        source.write_text(json.dumps(extra, ensure_ascii=False), encoding="utf8")
        newer = load_matches(str(source), END)
    if len(newer) != len(extra):
        raise RuntimeError("Original match loader rejected authenticated October fixtures")
    history = sorted([*history, *newer], key=lambda m: (m.day, m.key))
    if not history or history[-1].day != END:
        raise RuntimeError("November 3 historical cutoff not reached")
    if len({m.key for m in history}) != len(history):
        raise RuntimeError("Duplicate historical match ID")
    print("YTD_2026_SCORE_STUDY_HISTORY", len(history), "through", str(history[-1].day), flush=True)
    return history


def run(site_root, model_root, output_dir):
    started = time.monotonic()
    if END >= datetime.now(timezone.utc).date():
        raise RuntimeError("Every selected 2026 day must be completed before retrospective evaluation")
    site_root = Path(site_root).resolve()
    model_root = Path(model_root).resolve()
    output_dir = Path(output_dir).resolve()
    if not (model_root / "research/single_ml_v2.py").is_file():
        raise RuntimeError("Native Hybrid V3 research source unavailable")
    old_cwd = Path.cwd()
    sys.path.insert(0, str(model_root))
    sys.path.insert(0, str(model_root / "research"))
    sys.path.insert(0, str(site_root / "scripts"))
    try:
        os.chdir(model_root)
        from single_ml_v2 import backtest
        history = prepare_history(site_root, model_root)
        # Jan-Nov 3 2026 is evaluated chronologically: native V3
        # calibrates only on prior completed days, with no future results.
        # Each forecast is generated before the match outcome is ingested.
        with tempfile.TemporaryDirectory(prefix="mrx-v3-2026-ytd-backtest-") as td:
            results = backtest(
                history, date(2026, 1, 1), END, str(Path(td) / "full_year_to_date"),
                max_eval=0, retrain_days=30, auto_tune=False, v3_models=True,
                production_v3_only=True, daily_score_study_start=START,
                daily_score_study_end=END,
            )
        if results.get("status") != "v3_daily_score_research_complete":
            raise RuntimeError("Native V3 did not complete daily per-score evaluation")
        leaders = results["score_daily_leaders"]
        report = summarize(leaders, count_all_matches=results["evaluated_matches"])
        report["elapsed_seconds"] = round(time.monotonic()-started, 2)
        report["original_training_start"] = history[0].day.isoformat()
        report["historical_matches_in_memory"] = len(history)
        report["historical_cutoff"] = history[-1].day.isoformat()

        output_dir.mkdir(parents=True, exist_ok=True)
        summary_file = output_dir / "2026-ytd-score-leaders-summary.json"
        daily_file = output_dir / "2026-ytd-score-leaders-daily.csv"
        compact_file = output_dir / "2026-ytd-score-leaders-ranking.csv"
        summary_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        with daily_file.open("w", newline="", encoding="utf8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in sorted(leaders, key=lambda r: (r["day"], int(r["score"].split(":")[0]), int(r["score"].split(":")[1]))):
                writer.writerow({k: row[k] for k in CSV_FIELDS})
        with compact_file.open("w", newline="", encoding="utf8") as fh:
            writer = csv.writer(fh)
            writer.writerow(("score", "days_selected", "hits", "hit_rate_percent",
                             "average_model_probability_percent",
                             "expected_hits_from_model", "times_this_score_was_also_modal"))
            for score in report["scores_ranked_by_hits"]:
                x = report["by_score"][score]
                writer.writerow((score, x["days_selected"], x["hits"], x["hit_rate_percent"],
                                 x["average_model_probability_percent"],
                                 x["expected_hits_from_model"], x["times_this_score_was_also_modal"]))
        sample = {score:report["by_score"][score] for score in ("0:0","1:0","1:1","2:0","2:1","3:1","0:1","1:2","2:2")}
        print("YTD_2026_V3_SCORE_STUDY_RESULT", json.dumps({
            "days": report["days_with_completed_history"],
            "winning_days": report["days_with_at_least_one_hit"],
            "monthly": report["by_month"],
            "matches_evaluated": report["verified_settled_football_matches_evaluated"],
            "selected": len(leaders), "modal_score_types": report["score_categories"],
            "hits": report["total_hits_across_independent_scores"],
            "sample": sample, "elapsed_seconds": report["elapsed_seconds"],
        },ensure_ascii=False),flush=True)
        return report
    finally:
        os.chdir(old_cwd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site")
    ap.add_argument("--model-root", default="model")
    ap.add_argument("--output-dir", default="/tmp/mrx-v3-2026-ytd-score-study")
    args = ap.parse_args()
    run(args.site_root, args.model_root, args.output_dir)


if __name__ == "__main__":
    main()
