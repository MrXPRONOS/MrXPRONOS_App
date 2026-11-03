#!/usr/bin/env python3
"""Research-only paired ranking A (modal probability) vs B (fixed group mass).

B changes ONLY the daily order of fixtures, not the original Hybrid V3 exact
score nor its mapped experimental 3-score group. Prematch group masses are
exported from the model's 11x11 grid before adding same-day match results.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from ml_v2_topk import _check_row, _safe_output
from ml_v3_topk_full_2026 import WINDOWS, days_in_period
from ml_v3_grouped_top1_top2 import GROUPS, SCORE_TO_GROUP, settle
from ml_v3_group_probability import FROZEN_GROUPS
from single_ml_v3 import HYBRID_NAME

if GROUPS != FROZEN_GROUPS:
    raise RuntimeError("Frozen three-score proxy definitions drifted")
KS = (1, 2, 3, 5)
ARMS = ("A_MODAL", "B_GROUP_MASS")
VERSION = "research_group_rank_modal_vs_groupmass_v1_20261103"
BOOTSTRAPS = 3000
SEED = 20261103
FIXED_PRIMARY_A = {
    1: (59, 112), 2: (117, 220), 3: (175, 336), 5: (260, 527),
}


def load_pairs(predictions, masses, *, start, end):
    """Exact one-to-one provenance match on all Hybrid V3 fixtures."""
    if (start, end) not in WINDOWS:
        raise ValueError("Only the ten frozen historical periods are allowed")
    found = {}
    with open(predictions, encoding="utf8", newline="") as fh:
        reader = csv.DictReader(fh)
        need = {"model", "date", "id", "predicted_score", "actual_score",
                "top_probability", "model_fit_latest_day", "history_latest_day", "hit"}
        if not need.issubset(set(reader.fieldnames or [])):
            raise ValueError("Missing historical exact-score prediction schema")
        for raw in reader:
            if raw["model"] != HYBRID_NAME:
                continue
            row = _check_row(raw, start=start, end=end, allowed_models=(HYBRID_NAME,))
            if row is None:
                continue
            key = (row["date"], row["id"])
            if key in found:
                raise ValueError("Duplicate Hybrid V3 historical fixture")
            found[key] = row

    probabilities = {}
    with open(masses, encoding="utf8", newline="") as fh:
        reader = csv.DictReader(fh)
        need = {"date", "id", "predicted_score", "modal_probability", "group",
                "group_probability", "history_latest_day", "model_fit_latest_day"}
        fields = set(reader.fieldnames or [])
        if not need.issubset(fields):
            raise ValueError("Missing native Hybrid V3 group-grid probability fields")
        if any((field.startswith("actual") or field in ("hit", "win", "label", "result"))
               for field in fields):
            raise ValueError("Outcome labels are forbidden in PREMATCH probability feature CSV")
        for raw in reader:
            day, ident = raw["date"], raw["id"]
            if not start <= day <= end:
                raise ValueError("Group-mass file escapes historical calendar window")
            key = (day, ident)
            if key in probabilities:
                raise ValueError("Duplicate native grid probability for fixture")
            if not raw["predicted_score"] or not ident:
                raise ValueError("Missing probability provenance")
            try:
                modal = float(raw["modal_probability"])
                mass = float(raw["group_probability"])
            except (TypeError, ValueError) as exc:
                raise ValueError("Non-numeric group probability") from exc
            if (not math.isfinite(modal) or not math.isfinite(mass)
                    or not 0 < modal <= 1 or not 0 <= mass <= 1 + 1e-10):
                raise ValueError("Invalid native grid probability bounds")
            if (not raw["history_latest_day"] or not raw["model_fit_latest_day"]
                    or raw["history_latest_day"] >= day
                    or raw["model_fit_latest_day"] >= day):
                raise ValueError("Group-mass export contains future-dated model or history")
            expected = SCORE_TO_GROUP.get(raw["predicted_score"], "")
            if raw["group"] != expected:
                raise ValueError("Group reassigned after score prediction")
            if expected:
                if mass + 1e-10 < modal:
                    raise ValueError("A group cannot have less mass than its modal score")
            elif mass != 0:
                raise ValueError("Unmapped modal scores must abstain with zero group mass")
            probabilities[key] = (raw, modal, mass)

    if not found or set(found) != set(probabilities):
        raise ValueError("Group probability and historical prediction fixtures differ")
    byday = defaultdict(list)
    for key, row in found.items():
        raw, modal, mass = probabilities[key]
        if (raw["predicted_score"] != row["predicted_score"]
                or abs(modal - row["confidence"]) > 1e-6):
            raise ValueError("Native grid modal probability disagrees with exact score")
        if (raw["history_latest_day"] >= row["date"]
                or raw["model_fit_latest_day"] >= row["date"]):
            raise ValueError("Future-dated probability export")
        # The probability export contains zero result information. Actual
        # score is consumed only in settlement AFTER ranking has finished.
        row = dict(row)
        row["group"] = raw["group"]
        row["group_probability"] = mass
        byday[row["date"]].append(row)
    return byday


def rank_candidates(rows):
    """Freeze ranking BEFORE labels. Stable fixture-ID ties in both arms."""
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicated daily fixture in rank candidates")
    a = sorted(rows, key=lambda r: (-r["confidence"], r["id"]))
    b = sorted(rows, key=lambda r: (
        -(r["group_probability"] if r["group"] else -1.),
        -r["confidence"], r["id"]))
    return {"A_MODAL": a, "B_GROUP_MASS": b}


def settle_day(top):
    events = [settle(row["predicted_score"], row["actual_score"]) for row in top]
    mapped = [s for s in events if s["covered"]]
    exact = sum(s["exact"] for s in events)
    grouped = sum(s["win"] for s in events)
    if grouped < sum(s["exact"] for s in mapped):
        raise ValueError("Grouped hit cannot exclude covered exact score")
    if any(s["win"] and not s["result_1x2_win"] for s in events):
        raise ValueError("Grouped hit disagrees with 1X2")
    counts = Counter(s["group"] for s in mapped)
    hits = Counter(s["group"] for s in mapped if s["win"])
    return {
        "exact_hits": exact, "grouped_hits": grouped,
        "covered": len(mapped), "abstentions": len(top) - len(mapped),
        "exact_ge1": int(exact >= 1), "exact_ge2": int(exact >= 2),
        "group_ge1": int(grouped >= 1), "group_ge2": int(grouped >= 2),
        "group_ge3": int(grouped >= 3),
        "expected_group_wins": round(sum(r["group_probability"] for r in top), 10),
        "by_group": {name: {"selected": counts[name], "hits": hits[name]} for name in GROUPS},
    }


def month(predictions, masses, *, start, end):
    all_days = days_in_period(start, end)
    candidates = load_pairs(predictions, masses, start=start, end=end)
    daily = {str(k): [] for k in KS}
    cohort = []
    for day in all_days:
        choices = candidates[day]
        if len(choices) < 20:
            raise ValueError(f"{day}: fewer than 20 eligible prematch fixtures")
        ranked = rank_candidates(choices)
        cohort.append({"day": day, "candidates": len(choices)})
        for k in KS:
            left, right = ranked["A_MODAL"][:k], ranked["B_GROUP_MASS"][:k]
            same = len({r["id"] for r in left} & {r["id"] for r in right})
            daily[str(k)].append({
                "day": day, "k": k, "candidates": len(choices),
                "selection_overlap": same, "changed_slots": k - same,
                # Original model score and group are never modified.
                "A_MODAL": settle_day(left),
                "B_GROUP_MASS": settle_day(right),
            })
    result = {
        "version": VERSION, "research_only": True, "period": [start, end],
        "model": HYBRID_NAME, "ks": list(KS), "days": all_days,
        "grouping": {n: list(scores) for n, scores in GROUPS.items()},
        "A": "Unmodified per-day modal-score confidence descending; ID tie-break",
        "B": "Group mass of original modal score's fixed three-score group descending; modal-confidence, ID ties",
        "new_group_prediction": False,
        "experimental_not_official_1xbet_groups": True,
        "no_bookmaker_historical_odds_or_roi": True,
        "cohort": cohort, "daily": daily,
    }
    validate_month(result)
    return result


def validate_month(report):
    p = tuple(report.get("period") or ())
    if p not in WINDOWS or report.get("version") != VERSION or report.get("model") != HYBRID_NAME:
        raise ValueError("Unexpected experiment B version, model or history")
    if report.get("grouping") != {n: list(v) for n, v in GROUPS.items()}:
        raise ValueError("Research groups changed after preregistration")
    days = days_in_period(*p)
    if report.get("days") != days or [r["day"] for r in report.get("cohort", [])] != days:
        raise ValueError("Missing evaluation days")
    if set(report["daily"]) != {str(k) for k in KS}:
        raise ValueError("Incomplete Top K report")
    for k in KS:
        rows = report["daily"][str(k)]
        if [r["day"] for r in rows] != days:
            raise ValueError("Missing Top K calendar date")
        for i, row in enumerate(rows):
            if (row["k"] != k or row["candidates"] != report["cohort"][i]["candidates"]
                    or row["candidates"] < 20
                    or not 0 <= row["selection_overlap"] <= k
                    or row["changed_slots"] + row["selection_overlap"] != k):
                raise ValueError("Invalid common cohort/selection overlap")
            for arm in ARMS:
                r = row[arm]
                if (r["covered"] + r["abstentions"] != k
                        or not 0 <= r["exact_hits"] <= k
                        or not 0 <= r["grouped_hits"] <= r["covered"] <= k
                        or not 0 <= r["expected_group_wins"] <= k + 1e-8):
                    raise ValueError("Invalid coverage, hits or prematch group expected wins")
                groups = r["by_group"]
                if set(groups) != set(GROUPS):
                    raise ValueError("Invalid group names")
                if sum(g["selected"] for g in groups.values()) != r["covered"]:
                    raise ValueError("Incorrect group allocation counts")
                if sum(g["hits"] for g in groups.values()) != r["grouped_hits"]:
                    raise ValueError("Incorrect grouped-score wins")
                for key, count, n in (
                    ("exact_ge1", r["exact_hits"], 1), ("exact_ge2", r["exact_hits"], 2),
                    ("group_ge1", r["grouped_hits"], 1), ("group_ge2", r["grouped_hits"], 2),
                    ("group_ge3", r["grouped_hits"], 3),
                ):
                    if r[key] != int(count >= n):
                        raise ValueError("Incorrect daily hit thresholds")


def aggregate(days, k):
    if not days:
        raise ValueError("Empty daily results")
    n = len(days)
    result = {}
    for arm in ARMS:
        rows = [d[arm] for d in days]
        wins = sum(r["grouped_hits"] for r in rows)
        exact = sum(r["exact_hits"] for r in rows)
        covered = sum(r["covered"] for r in rows)
        result[arm] = {
            "days": n, "selection_slots": k * n,
            "exact_hits": exact,
            "exact_hit_pct": round(100 * exact / (k * n), 4),
            "grouped_hits": wins,
            "group_hit_pct": round(100 * wins / (k * n), 4),
            "group_hit_covered_pct": round(100 * wins / covered, 4) if covered else None,
            "covered": covered, "abstentions": k * n - covered,
            "days_exact_ge1": sum(r["exact_ge1"] for r in rows),
            "days_group_ge1": sum(r["group_ge1"] for r in rows),
            "days_group_ge2": sum(r["group_ge2"] for r in rows),
            "days_group_ge3": sum(r["group_ge3"] for r in rows),
            "sum_predicted_group_hits": round(sum(r["expected_group_wins"] for r in rows), 4),
            "break_even_flat_decimal_odds_theoretical": round(covered / wins, 4) if wins else None,
            "groups": {g: {
                "selected": sum(r["by_group"][g]["selected"] for r in rows),
                "hits": sum(r["by_group"][g]["hits"] for r in rows),
            } for g in GROUPS},
        }
    return {
        "A_MODAL": result["A_MODAL"], "B_GROUP_MASS": result["B_GROUP_MASS"],
        "delta_B_minus_A_group_hits": result["B_GROUP_MASS"]["grouped_hits"] - result["A_MODAL"]["grouped_hits"],
        "delta_B_minus_A_exact_hits": result["B_GROUP_MASS"]["exact_hits"] - result["A_MODAL"]["exact_hits"],
        "delta_B_minus_A_group_pp": round(100 * (result["B_GROUP_MASS"]["grouped_hits"] - result["A_MODAL"]["grouped_hits"]) / (k * n), 4),
        "delta_B_minus_A_exact_pp": round(100 * (result["B_GROUP_MASS"]["exact_hits"] - result["A_MODAL"]["exact_hits"]) / (k * n), 4),
        "delta_B_minus_A_days_group_ge1": result["B_GROUP_MASS"]["days_group_ge1"] - result["A_MODAL"]["days_group_ge1"],
        "selected_overlap_slots": sum(d["selection_overlap"] for d in days),
        "changed_selection_slots": sum(d["changed_slots"] for d in days),
        "selection_overlap_pct": round(100 * sum(d["selection_overlap"] for d in days) / (k * n), 4),
    }


def pooled_confidence(days, k, *, samples=BOOTSTRAPS):
    """Descriptive paired calendar-day bootstrap; not an untouched confirmation."""
    n = len(days)
    rng = np.random.default_rng(SEED + 100 * k + n)
    pair_group = np.asarray([d["B_GROUP_MASS"]["grouped_hits"] - d["A_MODAL"]["grouped_hits"] for d in days])
    pair_exact = np.asarray([d["B_GROUP_MASS"]["exact_hits"] - d["A_MODAL"]["exact_hits"] for d in days])
    pair_days = np.asarray([d["B_GROUP_MASS"]["group_ge1"] - d["A_MODAL"]["group_ge1"] for d in days])
    results = []
    # Use small batches to bound peak memory on hosted GitHub runners.
    for arr, denom in ((pair_group, k), (pair_exact, k), (pair_days, 1)):
        batch = []
        for _ in range(0, samples, 300):
            size = min(300, samples - len(batch))
            picks = rng.integers(n, size=(size, n))
            batch.extend((100. * arr[picks].mean(axis=1) / denom).tolist())
        results.append([round(float(v), 4) for v in np.quantile(batch, [0.025, 0.975])])
    return {
        "group_pp_paired_day_bootstrap_95": results[0],
        "exact_pp_paired_day_bootstrap_95": results[1],
        "days_group_ge1_pp_paired_day_bootstrap_95": results[2],
        "note": "Exploratory descriptive interval; 2026 data previously inspected, not an independent unseen test.",
    }


def pool(paths):
    if len(paths) != len(WINDOWS):
        raise ValueError("Exactly ten historical periods expected")
    periods = {}
    for path in paths:
        value = json.loads(Path(path).read_text(encoding="utf8"))
        validate_month(value)
        pair = tuple(value["period"])
        if pair in periods:
            raise ValueError("Duplicate evaluation month")
        periods[pair] = value
    if set(periods) != set(WINDOWS):
        raise ValueError("Missing frozen 2026 calendar period")
    ordered = [periods[k] for k in WINDOWS]
    primary = [d for month in ordered[:9] for k in [1] for d in month["daily"]["1"]]
    if len(primary) != 273 or len(ordered[9]["days"]) != 24:
        raise ValueError("Invalid Jan-Sep primary and Oct partial day lengths")
    def summarize(window):
        return {str(k): {
            **aggregate([d for month in window for d in month["daily"][str(k)]], k),
            "paired_95_intervals": pooled_confidence([d for month in window for d in month["daily"][str(k)]], k),
        } for k in KS}
    p = summarize(ordered[:9])
    # Hard fail if A no longer reproduces our already verified same-configuration
    # Jan-Sep research counts: ensures new export and feature code did not
    # silently change previously reported baseline.
    for k, expected in FIXED_PRIMARY_A.items():
        observed = (p[str(k)]["A_MODAL"]["exact_hits"], p[str(k)]["A_MODAL"]["grouped_hits"])
        if observed != expected:
            raise ValueError(f"Baseline A mismatch for Top {k}: {observed} != {expected}")
    return {
        "version": VERSION, "research_only": True,
        "source_cutoff": "2026-10-24", "primary_period": "Jan-Sep 2026 (273 full days)",
        "primary": p, "october_partial_1_to_24": summarize(ordered[9:]),
        "all_available_2026_descriptive": summarize(ordered),
        "monthly": [
            {"month": m["period"][0][:7], "october_partial": i == 9,
             "topk": {str(k): aggregate(m["daily"][str(k)], k) for k in KS}}
            for i, m in enumerate(ordered)
        ],
        "limitations": "Historical exploratory 2026 ranking (data seen previously); fixed experimental groups not actual 1xBet markets; no bookmaker historical odds, no ROI. Paired intervals cannot substitute untouched future validation.",
    }


def main():
    p = argparse.ArgumentParser()
    cmd = p.add_subparsers(dest="command", required=True)
    mo = cmd.add_parser("month")
    for arg in ("predictions", "masses", "start", "end", "out"):
        mo.add_argument("--" + arg, required=True)
    ag = cmd.add_parser("pool")
    ag.add_argument("--inputs", nargs="+", required=True)
    ag.add_argument("--out", required=True)
    args = p.parse_args()
    if args.command == "month":
        report = month(args.predictions, args.masses, start=args.start, end=args.end)
        _safe_output(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
        print("GROUP_RANK_B_MONTH", json.dumps({
            "period": report["period"], "days": len(report["days"]),
            "top3": aggregate(report["daily"]["3"], 3),
            "top5": aggregate(report["daily"]["5"], 5),
        }), flush=True)
    else:
        report = pool(args.inputs)
        _safe_output(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
        print("GROUP_RANK_B_FULL_2026", json.dumps({
            "primary": report["primary"],
            "october_partial_1_to_24": report["october_partial_1_to_24"],
            "limitations": report["limitations"],
        }), flush=True)


if __name__ == "__main__":
    main()
