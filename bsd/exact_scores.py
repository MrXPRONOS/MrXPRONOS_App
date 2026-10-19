#!/usr/bin/env python3
"""MR XPRONOS — exact-score research engine (BSD V2, shadow-only).

As-of features come from V2History; a match enters history only 4h after
kick-off. Fit Dixon-Coles rho on 2024 (train/validation), tune small goal
rate multipliers on 2025, then test ONCE on held-out 2026 fixtures.
No bookmaker prices, guaranteed returns, publishing or Telegram sends.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bsd_v2_core import V2History, estimate_goals, fixture_datetime, outcome_scores, score_matrix


def year_sample(index, year, cap):
    """Chronological, uniformly spaced fixture sample, not chosen by result."""
    fixtures = [e for _, e in index.global_games
                if fixture_datetime(e).year == year]
    fixtures.sort(key=lambda e: (fixture_datetime(e), str(e["id"])))
    if cap > 0 and len(fixtures) > cap:
        fixtures = [fixtures[int(i * len(fixtures) / cap)] for i in range(cap)]
    return fixtures


def feature_rows(index, year, cap):
    rows = []
    skipped = Counter()
    for event in year_sample(index, year, cap):
        feature, reason = estimate_goals(event, index)
        score = outcome_scores(event)
        if feature is None or score is None:
            skipped[reason if feature is None else "missing_final_score"] += 1
            continue
        rows.append((feature["home"], feature["away"], score))
    return rows, dict(skipped)


def matrix_for(home, away, *, rho=0.0, scale_home=1.0, scale_away=1.0):
    return score_matrix(
        max(0.1, min(5.0, home * scale_home)),
        max(0.1, min(5.0, away * scale_away)),
        rho=rho,
        max_goals=12,
    )


def top_scores(matrix, count=3):
    return sorted(matrix.items(), key=lambda item: (-item[1], item[0]))[:count]


def score_metrics(rows, *, rho=0.0, scale_home=1.0, scale_away=1.0):
    if not rows:
        return {"evaluated": 0, "top1_hits": 0, "top3_hits": 0,
                "top1_rate": None, "top3_rate": None, "log_loss": None,
                "multiclass_brier": None}
    hits1 = hits3 = 0
    nll = brier = 0.0
    for home, away, actual in rows:
        probs = matrix_for(home, away, rho=rho,
                           scale_home=scale_home, scale_away=scale_away)
        top3 = top_scores(probs)
        hits1 += int(top3[0][0] == actual)
        hits3 += int(actual in (score for score, _ in top3))
        actual_p = probs.get(actual, 0.0)
        # A score above 12 gets a conservative epsilon: record, never discard.
        nll -= math.log(max(actual_p, 1e-12))
        brier += sum(p * p for p in probs.values()) - 2 * actual_p + 1
    n = len(rows)
    return {"evaluated": n, "top1_hits": hits1, "top3_hits": hits3,
            "top1_rate": round(hits1 / n, 5),
            "top3_rate": round(hits3 / n, 5),
            "log_loss": round(nll / n, 5),
            "multiclass_brier": round(brier / n, 5)}


def fit_rho_2024(rows):
    """Fit on first 70% of 2024; validate rho on final 30%."""
    if len(rows) < 80:
        return 0.0, {"eligible": len(rows), "reason": "too_few_2024_matches"}
    cut = int(len(rows) * .7)
    train, valid = rows[:cut], rows[cut:]
    options = (-.12, -.08, -.04, 0.0, .04, .08, .12)
    scored = [(score_metrics(train, rho=rho)["log_loss"], rho) for rho in options]
    best = min(scored)[1]
    baseline = score_metrics(valid, rho=0.0)["log_loss"]
    candidate = score_metrics(valid, rho=best)["log_loss"]
    chosen = best if candidate < baseline - .0005 else 0.0
    return chosen, {
        "train": len(train), "validation": len(valid),
        "candidate_rho": best, "chosen_rho": chosen,
        "validation_poisson_log_loss": baseline,
        "validation_dc_log_loss": candidate,
    }


def fit_goal_scales_2025(rows, rho):
    """Tune only with 2025. 2026 is forbidden until parameters are frozen."""
    if len(rows) < 60:
        return 1.0, 1.0, {"eligible": len(rows), "reason": "too_few_2025_matches"}
    baseline = score_metrics(rows, rho=rho)["log_loss"]
    candidates = [(score_metrics(rows, rho=rho, scale_home=h, scale_away=a)["log_loss"], h, a)
                  for h in (.90, 1.0, 1.10)
                  for a in (.90, 1.0, 1.10)]
    loss, h, a = min(candidates, key=lambda x: (x[0], abs(x[1] - 1) + abs(x[2] - 1)))
    if baseline - loss < .002:
        h, a, loss = 1.0, 1.0, baseline
    return h, a, {
        "tuning_sample": len(rows), "baseline_log_loss": baseline,
        "chosen_log_loss": loss, "scale_home": h, "scale_away": a,
    }


def train_and_backtest(events, *, max_2024=650, max_2025=900, max_2026=1200):
    index = V2History(events)
    sample24, rejected24 = feature_rows(index, 2024, max_2024)
    sample25, rejected25 = feature_rows(index, 2025, max_2025)
    # IMPORTANT: Parameter selection ends HERE; 2026 outcomes remain untouched.
    rho, rho_meta = fit_rho_2024(sample24)
    h, a, scale_meta = fit_goal_scales_2025(sample25, rho)
    sample26, rejected26 = feature_rows(index, 2026, max_2026)
    base = score_metrics(sample26)
    trained = score_metrics(sample26, rho=rho, scale_home=h, scale_away=a)
    return {
        "format": "mrx-exact-score-evaluation-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "historical_shadow_backtest", "published": False,
        "experimental": True, "prices_used": False,
        "training_year": 2024, "tuning_year": 2025, "unseen_test_year": 2026,
        "history_unique_finished": len(index.global_games),
        "sample_counts": {"2024": len(sample24), "2025": len(sample25), "2026": len(sample26)},
        "rejected_for_insufficient_data": {"2024": rejected24, "2025": rejected25, "2026": rejected26},
        "training": {"rho": rho_meta, "goal_rate_scales": scale_meta},
        "parameters": {"rho": rho, "scale_home": h, "scale_away": a},
        "test_2026": {"poisson_baseline": base, "trained_model": trained},
        "warning": ("Retrospective research only; the archive may have been revised. "
                    "No prospective verification, no odds or profit claims. "
                    "2026 score labels are never used to train parameters."),
    }


def make_preview(feed, parameters, *, clock=None, max_fixtures=100):
    """Read existing BSD publication feed; DO NOT modify it or alter its picks."""
    clock = clock or datetime.now(timezone.utc)
    matches = feed.get("matches") if isinstance(feed, dict) else []
    result = []
    for e in (matches if isinstance(matches, list) else []):
        try:
            kickoff = fixture_datetime(e)
        except (TypeError, ValueError, OverflowError):
            continue
        if kickoff <= clock:
            continue
        features = e.get("estimated_goals") or {}
        home, away = features.get("home"), features.get("away")
        try:
            home, away = float(home), float(away)
            if not all(math.isfinite(x) and .1 <= x <= 5 for x in (home, away)):
                continue
            scores = top_scores(matrix_for(home, away, **parameters))
        except (ValueError, TypeError, OverflowError):
            continue
        result.append({
            "id": e.get("id"), "home_team": e.get("home_team"),
            "away_team": e.get("away_team"), "kickoff_utc": kickoff.isoformat(),
            "expected_goals": {"home": home, "away": away},
            "top3": [{"score": f"{s[0]}-{s[1]}", "probability": round(p, 6)}
                     for s, p in scores],
        })
        if len(result) >= max_fixtures:
            break
    return {
        "format": "mrx-exact-score-preview-v1",
        "generated_at_utc": clock.isoformat(),
        "experimental": True, "published": False,
        "feed_limited_to_existing_bsd_selections": True, "matches": result,
    }


def main():
    parser = argparse.ArgumentParser(description="Exact-score training & shadow backtest")
    parser.add_argument("--history", default="bsd/all_matches_bsd.json")
    parser.add_argument("--feed", default="data.json")
    parser.add_argument("--out-dir", default="tmp/exact-scores")
    parser.add_argument("--max-2024", type=int, default=650)
    parser.add_argument("--max-2025", type=int, default=900)
    parser.add_argument("--max-2026", type=int, default=1200)
    args = parser.parse_args()
    if min(args.max_2024, args.max_2025, args.max_2026) <= 0:
        parser.error("Each year sample must be positive")
    raw_path = Path(args.history)
    if not raw_path.is_file():
        parser.error("Private BSD history missing; restore it with BSD_HISTORY_KEY first")
    history = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(history, list):
        parser.error("Expected BSD history JSON array")
    report = train_and_backtest(history, max_2024=args.max_2024,
                                max_2025=args.max_2025, max_2026=args.max_2026)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    model = {"version": "mrx-exact-score-v1", "parameters": report["parameters"],
             "trained_years": [2024, 2025], "test_year": 2026}
    (out / "model.json").write_text(json.dumps(model, indent=2), encoding="utf-8")
    fp = Path(args.feed)
    if fp.is_file():
        feed = json.loads(fp.read_text(encoding="utf-8"))
        preview = make_preview(feed, report["parameters"])
        (out / "preview.json").write_text(json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8")
        print("EXACT_SCORE_PREVIEW", json.dumps({"upcoming": len(preview["matches"])}))
    print("EXACT_SCORE_EVALUATION", json.dumps({
        "unique_history": report["history_unique_finished"],
        "sample_counts": report["sample_counts"],
        "parameters": report["parameters"],
        "baseline": report["test_2026"]["poisson_baseline"],
        "trained": report["test_2026"]["trained_model"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
