#!/usr/bin/env python3
"""Independent paired evaluation of FIVE exact-score research models.

Input is a retrospective replay produced by single_ml_v2.backtest, never
claimed as frozen prekickoff predictions. Write only aggregate metrics.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from single_ml_v2_validation import metrics, bootstrap_difference
from single_ml_v2_validation import checked_date

MODELS = (
    "machine_learning",
    "machine_learning_hybrid",
    "machine_learning_lightgbm",
    "machine_learning_catboost",
    "machine_learning_direct",
)

def paired_report(path, *, test_start, test_end, min_matches=75):
    start, end = checked_date(test_start), checked_date(test_end)
    if not start <= end:
        raise ValueError("Invalid evaluation period")
    groups = defaultdict(dict)
    seen = set()
    with open(path, encoding="utf8", newline="") as stream:
        for row in csv.DictReader(stream):
            model = row.get("model")
            if model not in MODELS:
                continue
            day = checked_date(row["date"])
            if not start <= day <= end:
                continue
            key = (row["date"], row["id"])
            if (model, *key) in seen:
                raise ValueError("Duplicated model match prediction")
            seen.add((model, *key))
            history = row.get("history_latest_day")
            fitted = row.get("model_fit_latest_day")
            if not history or checked_date(history) >= day:
                raise ValueError("Leaked or unproven previous-day fixture history")
            if model.startswith("machine_learning") and (not fitted or checked_date(fitted) >= day):
                raise ValueError("Missing/invalid model cutoff")
            expected_hit = int(row["predicted_score"] == row["actual_score"])
            if int(row["hit"]) != expected_hit:
                raise ValueError("Wrong exact-score settlement")
            groups[model][key] = row
    if any(not groups[model] for model in MODELS):
        raise ValueError("Five model outputs are not all available")
    common = set.intersection(*(set(groups[name]) for name in MODELS))
    if len(common) < min_matches:
        raise ValueError(f"Insufficient five-way same-fixture cohort: {len(common)}")
    dates = sorted({key[0] for key in common})
    if len(dates) < 2:
        raise ValueError("At least 2 separate UTC evaluation dates required")
    ordered = sorted(common)
    cohort = {name: [groups[name][key] for key in ordered] for name in MODELS}
    anchor = cohort[MODELS[0]]
    report = {
        "research_only": True,
        "interpretation": "Chronological retrospective replay; NOT independently archived prematch predictions",
        "test_start": str(start), "test_end": str(end),
        "model_names": list(MODELS),
        "same_fixture_cohort_n": len(common),
        "utc_days": dates,
        "available_matches_by_model": {name: len(groups[name]) for name in MODELS},
        "metrics": {name: metrics(rows) for name, rows in cohort.items()},
        "paired_vs_histgb": {
            name: bootstrap_difference(anchor, cohort[name], resamples=500)
            for name in MODELS[1:]
        },
        "historical_odds": "No certified correct-score pre-match odds; ROI not evaluable",
    }
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--minimum", type=int, default=75)
    args = p.parse_args()
    report = paired_report(args.predictions, test_start=args.start, test_end=args.end, min_matches=args.minimum)
    destination = Path(args.out)
    if not destination.resolve().is_relative_to(Path("/tmp").resolve()):
        raise ValueError("Aggregate report may only be written to temporary runner storage")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print("FIVE_MODEL_REAL_HISTORICAL_COMPARISON", json.dumps({
        "paired_matches": report["same_fixture_cohort_n"],
        "days": len(report["utc_days"]),
        "metrics": {k: {s: v[s] for s in ("n", "exact_hits", "hit_rate_pct", "top3_hit_pct", "mean_log_loss", "expected_calibration_error")}
                    for k,v in report["metrics"].items()}
    }, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
